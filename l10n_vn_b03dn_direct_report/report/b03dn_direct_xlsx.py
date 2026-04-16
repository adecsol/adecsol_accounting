# -*- coding: utf-8 -*-
import math
import re
from datetime import date
from html.parser import HTMLParser

from odoo import api, fields, models


class _B03dnHtmlRunParser(HTMLParser):
    """Parse short HTML into text runs with bold/italic flags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._bold = 0
        self._italic = 0
        self.runs = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in ("b", "strong"):
            self._bold += 1
        elif t in ("i", "em"):
            self._italic += 1
        elif t == "br":
            # Space instead of newline — avoid tall cells from br + text_wrap
            self.runs.append((" ", self._bold, self._italic))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("b", "strong") and self._bold:
            self._bold -= 1
        elif t in ("i", "em") and self._italic:
            self._italic -= 1

    def handle_data(self, data):
        if not data:
            return
        # Newlines/tabs from XML pretty-print → single spaces
        chunk = re.sub(r"[\n\r\t]+", " ", data)
        chunk = re.sub(r" {2,}", " ", chunk)
        if not chunk:
            return
        self.runs.append((chunk, self._bold, self._italic))


class ReportB03dnDirectXlsx(models.AbstractModel):
    _name = "report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "B03-DN — XLSX (form B 03 – DN TT200)"

    @api.model
    def _b03dn_xlsx_company_address(self, company):
        if not company:
            return "…………………………"
        parts = []
        if company.street:
            parts.append(company.street.strip())
        if company.street2:
            parts.append(company.street2.strip())
        if company.city:
            parts.append(company.city.strip())
        if company.state_id:
            parts.append((company.state_id.name or "").strip())
        return ", ".join(p for p in parts if p) or "…………………………"

    @api.model
    def _b03dn_xlsx_company_state_name(self, company):
        if not company:
            return ""
        if company.state_id:
            return (company.state_id.name or "").strip()
        partner = company.partner_id
        if partner and partner.state_id:
            return (partner.state_id.name or "").strip()
        return ""

    @api.model
    def _b03dn_xlsx_parse_date(self, val):
        if not val:
            return None
        if isinstance(val, date):
            return val
        return fields.Date.from_string(str(val)[:10])

    @api.model
    def _b03dn_merge_html_runs(self, runs):
        if not runs:
            return []
        out = []
        cur_t, cur_b, cur_i = runs[0]
        for t, b, i in runs[1:]:
            if b == cur_b and i == cur_i:
                cur_t += t
            else:
                out.append((cur_t, cur_b, cur_i))
                cur_t, cur_b, cur_i = t, b, i
        out.append((cur_t, cur_b, cur_i))
        return out

    @api.model
    def _b03dn_html_name_to_runs(self, html_value):
        if not html_value or not str(html_value).strip():
            return []
        raw = str(html_value)
        parser = _B03dnHtmlRunParser()
        parser.feed(raw)
        parser.close()
        runs = [x for x in parser.runs if x[0]]
        if not runs and raw.strip():
            plain = re.sub(r"<[^>]+>", "", raw)
            if plain.strip():
                runs = [(plain, False, False)]
        merged = self._b03dn_merge_html_runs(runs)
        return self._b03dn_xlsx_normalize_name_runs(merged)

    @api.model
    def _b03dn_xlsx_normalize_name_runs(self, merged):
        """Collapse whitespace/newlines so the line-item cell stays compact."""
        if not merged:
            return []
        cleaned = []
        for t, b, i in merged:
            t = t.replace("\n", " ").replace("\r", " ")
            t = re.sub(r" +", " ", t)
            if not t:
                continue
            cleaned.append((t, b, i))
        merged = self._b03dn_merge_html_runs(cleaned)
        if not merged:
            return []
        t0, b0, i0 = merged[0]
        merged[0] = (t0.lstrip(), b0, i0)
        t1, b1, i1 = merged[-1]
        merged[-1] = (t1.rstrip(), b1, i1)
        return [(t, b, i) for t, b, i in merged if t]

    @api.model
    def _b03dn_row_name_style_flags(self, html_value):
        """Read <b>/<strong>/<i>/<em> on ``name``.

        (bold, italic) are True only when every visible run (after merging) is bold / italic —
        i.e. the whole line label is wrapped in strong+em.

        Mixed plain and bold text returns (False, False) for code/notes/amount columns
        (only the name column keeps rich text).
        """
        runs = self._b03dn_html_name_to_runs(html_value)
        substantive = [(t, b, i) for t, b, i in runs if (t or "").strip()]
        if not substantive:
            return False, False
        bold = all(b for _, b, _ in substantive)
        italic = all(i for _, _, i in substantive)
        return bold, italic

    @api.model
    def _b03dn_effective_row_style_flags(self, line):
        """Bold/italic for code, notes, amount columns: from HTML ``name`` + report flags."""
        if not line:
            return False, False
        nb, ni = self._b03dn_row_name_style_flags(line.name)
        eff_bold = bool(line.b03dn_report_bold_amounts) or nb
        eff_italic = ni
        return eff_bold, eff_italic

    @api.model
    def _b03dn_line_name_has_visible_text(self, html_value):
        """True if any visible characters remain after stripping HTML."""
        runs = self._b03dn_html_name_to_runs(html_value)
        return any((t or "").strip() for t, _, _ in runs)

    @api.model
    def _b03dn_line_shows_money_columns(self, line):
        """Current/prior year columns: hidden for section/note lines or empty names."""
        if not line:
            return False
        if getattr(line, "display_type", None):
            return False
        return self._b03dn_line_name_has_visible_text(line.name)

    @api.model
    def _b03dn_write_line_name_cell(
        self,
        sheet,
        workbook,
        row,
        col,
        html_value,
        cell_fmt,
        frag_fmt_cache,
    ):
        """Write the line-item cell: bold/italic driven by HTML ``name`` only."""
        style_runs = []
        for text, b_tag, i_tag in self._b03dn_html_name_to_runs(html_value):
            if (
                style_runs
                and style_runs[-1][1] == b_tag
                and style_runs[-1][2] == i_tag
            ):
                style_runs[-1] = (style_runs[-1][0] + text, b_tag, i_tag)
            else:
                style_runs.append((text, b_tag, i_tag))

        if not style_runs:
            sheet.write(row, col, "", cell_fmt)
            return

        if len(style_runs) == 1:
            text0, eb, ei = style_runs[0]
            if not eb and not ei:
                sheet.write(row, col, text0, cell_fmt)
                return
            # Fully bold/italic segment: xlsxwriter write_rich_string needs >2 tokens
            # (excluding cell_format) — [fmt, str] alone is ignored → empty cell.
            sk_cell = ("name_cell_styled", eb, ei)
            if sk_cell not in frag_fmt_cache:
                fd = {
                    "font_size": 11,
                    "border": 1,
                    "text_wrap": True,
                    "valign": "vcenter",
                }
                if eb:
                    fd["bold"] = True
                if ei:
                    fd["italic"] = True
                frag_fmt_cache[sk_cell] = workbook.add_format(fd)
            sheet.write(row, col, text0, frag_fmt_cache[sk_cell])
            return

        base_key = ("name_base", False, False)
        if base_key not in frag_fmt_cache:
            frag_fmt_cache[base_key] = workbook.add_format({"font_size": 11})
        base_frag = frag_fmt_cache[base_key]

        parts = []
        for text, eb, ei in style_runs:
            if not text:
                continue
            if not eb and not ei:
                frag = base_frag
            else:
                sk = ("name", eb, ei)
                if sk not in frag_fmt_cache:
                    fd = {"font_size": 11}
                    if eb:
                        fd["bold"] = True
                    if ei:
                        fd["italic"] = True
                    frag_fmt_cache[sk] = workbook.add_format(fd)
                frag = frag_fmt_cache[sk]
            parts.extend([frag, text])

        if not parts:
            sheet.write(row, col, "", cell_fmt)
            return

        sheet.write_rich_string(row, col, *parts, cell_fmt)

    def generate_xlsx_report(self, workbook, data, objects):
        html_report = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct"]
        self = html_report._b03dn_env_with_user_lang(self)
        report = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct"]
        _ = self.env._
        data = dict(data or {})
        wizard = objects[:1]
        payload = report._b03dn_payload_merged_with_ui(wizard, data)
        divisor = report._b03dn_money_divisor_from_filters(
            payload.get("b03dn_ui_filters") or {},
        )
        company = payload.get("company")
        currency = payload.get("currency")
        rows = payload.get("rows") or []
        dec = currency.decimal_places if currency else 2
        if divisor > 1:
            dec = max(dec, 2)

        sheet = workbook.add_worksheet("B03-DN")
        last_col = 4

        f_label_addr = workbook.add_format(
            {"font_size": 11, "bold": True, "valign": "top", "text_wrap": True}
        )
        f_hdr_right_mau_frag = workbook.add_format(
            {"font_size": 11, "bold": True, "align": "right"}
        )
        f_hdr_right_tt_frag = workbook.add_format(
            {"font_size": 10, "italic": True, "align": "right"}
        )
        f_hdr_right_cell = workbook.add_format(
            {"text_wrap": True, "valign": "top", "align": "right"}
        )
        f_title = workbook.add_format(
            {
                "bold": True,
                "font_size": 14,
                "align": "center",
                "valign": "vcenter",
            }
        )
        f_subtitle = workbook.add_format(
            {"font_size": 11, "align": "center", "italic": True, "bold": True}
        )
        f_year = workbook.add_format({"font_size": 11, "align": "center"})
        f_dvt = workbook.add_format({"font_size": 11, "align": "right"})
        f_hdr = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "text_wrap": True,
                "bg_color": "#D9D9D9",
            }
        )
        f_hdr_colnum = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "bg_color": "#E7E7E7",
            }
        )
        f_cell = workbook.add_format(
            {"font_size": 11, "border": 1, "text_wrap": True, "valign": "vcenter"}
        )
        f_note = workbook.add_format({"font_size": 10, "italic": True, "text_wrap": True})
        f_note_footer = workbook.add_format(
            {
                "font_size": 10,
                "italic": True,
                "text_wrap": True,
                "valign": "top",
            }
        )
        f_sig_label = workbook.add_format(
            {"font_size": 11, "align": "center", "bold": True, "text_wrap": True}
        )
        f_sig_sub = workbook.add_format(
            {"font_size": 10, "align": "center", "italic": True}
        )
        f_sig_footer_left = workbook.add_format(
            {"font_size": 10, "align": "left", "text_wrap": True}
        )
        f_lap_ngay = workbook.add_format(
            {"font_size": 11, "align": "right", "italic": True}
        )

        sheet.set_column(0, 0, 52)
        sheet.set_column(1, 1, 7)
        sheet.set_column(2, 2, 10)
        sheet.set_column(3, 4, 18)

        addr = self._b03dn_xlsx_company_address(company)
        hdr_vals = self.env["l10n.vn.b03dn.form.header"]._values_for_company(company)
        form_title = hdr_vals["form_title"]
        tt_200_line = hdr_vals["legal_reference"]
        left_hdr = (
            _("Company: %s") % (company.name or "")
            + "\n"
            + _("Address: %s") % addr
        )
        sheet.merge_range(0, 0, 0, 2, left_hdr, f_label_addr)
        sheet.merge_range(0, 3, 0, 4, "", f_hdr_right_cell)
        sheet.write_rich_string(
            0,
            3,
            f_hdr_right_mau_frag,
            form_title,
            f_hdr_right_tt_frag,
            f"\n{tt_200_line}",
            f_hdr_right_cell,
        )
        _chars_l = 72
        _chars_r = 34
        _lines_l = sum(
            max(1, math.ceil(len(p) / _chars_l)) for p in left_hdr.split("\n")
        )
        _lines_r = 1 + max(1, math.ceil(len(tt_200_line) / _chars_r))
        _row0_h = min(95.0, max(22.0, 11.5 * max(_lines_l, _lines_r) + 5.0))
        sheet.set_row(0, _row0_h)

        sheet.merge_range(1, 0, 1, last_col, _("STATEMENT OF CASH FLOWS"), f_title)
        sheet.merge_range(
            2, 0, 2, last_col, _("(Direct method) (*)"), f_subtitle
        )

        dt_to = self._b03dn_xlsx_parse_date(payload.get("date_to"))
        df_rep = self._b03dn_xlsx_parse_date(payload.get("date_from"))
        
        b03dn_year_line = ""
        if dt_to:
            y = dt_to.year
            start_of_year = date(y, 1, 1)
            end_of_year = date(y, 12, 31)
            if df_rep == start_of_year and dt_to == end_of_year:
                b03dn_year_line = _("Year %s") % y
            else:
                from_str = df_rep.strftime('%d/%m/%Y') if df_rep else '…'
                to_str = dt_to.strftime('%d/%m/%Y')
                b03dn_year_line = _("Year %s (from %s to %s)") % (y, from_str, to_str)
        else:
            b03dn_year_line = _("Year …")
        
        sheet.merge_range(3, 0, 3, last_col, b03dn_year_line, f_year)

        dvt_label = report._b03dn_display_money_unit_caption(divisor)
        sheet.merge_range(4, 0, 4, last_col, dvt_label, f_dvt)

        sheet.set_row(1, 22)
        sheet.set_row(2, 18)

        hdr_top = 6
        headers = [
            _("Line item"),
            _("Code"),
            _("Notes"),
            _("Current year"),
            _("Prior year"),
        ]
        for col, h in enumerate(headers):
            sheet.write(hdr_top, col, h, f_hdr)
        for col in range(5):
            sheet.write(hdr_top + 1, col, str(col + 1), f_hdr_colnum)

        row_line_fmt_cache = {}

        def _line_cell_fmt(bold, italic, align="left"):
            key = ("line_cell", bold, italic, align)
            if key not in row_line_fmt_cache:
                d = {
                    "font_size": 11,
                    "border": 1,
                    "text_wrap": True,
                    "valign": "vcenter",
                    "align": align,
                }
                if bold:
                    d["bold"] = True
                if italic:
                    d["italic"] = True
                row_line_fmt_cache[key] = workbook.add_format(d)
            return row_line_fmt_cache[key]

        def _line_money_fmt(bold, italic):
            key = ("line_money", bold, italic)
            if key not in row_line_fmt_cache:
                d = {
                    "num_format": f"#,##0.{'0' * dec}",
                    "border": 1,
                    "align": "right",
                    "valign": "vcenter",
                }
                if bold:
                    d["bold"] = True
                if italic:
                    d["italic"] = True
                row_line_fmt_cache[key] = workbook.add_format(d)
            return row_line_fmt_cache[key]

        r = hdr_top + 2
        name_frag_fmts = {}
        for row in rows:
            line = row["line"]
            self._b03dn_write_line_name_cell(
                sheet,
                workbook,
                r,
                0,
                line.name,
                f_cell,
                name_frag_fmts,
            )
            code = "" if line.display_type else (line.code or "")
            amt_bold, amt_italic = self._b03dn_effective_row_style_flags(line)
            sheet.write(
                r, 1, code, _line_cell_fmt(amt_bold, amt_italic, align="center")
            )
            sheet.write(
                r,
                2,
                line.explanation_ref or "",
                _line_cell_fmt(amt_bold, amt_italic, align="center"),
            )
            show_amt = self._b03dn_line_shows_money_columns(line)
            if show_amt:
                sheet.write(
                    r,
                    3,
                    (row["amount_current"] or 0) / divisor,
                    _line_money_fmt(amt_bold, amt_italic),
                )
                sheet.write(
                    r,
                    4,
                    (row["amount_previous"] or 0) / divisor,
                    _line_money_fmt(amt_bold, amt_italic),
                )
            else:
                sheet.write_blank(
                    r, 3, None, _line_money_fmt(amt_bold, amt_italic),
                )
                sheet.write_blank(
                    r, 4, None, _line_money_fmt(amt_bold, amt_italic),
                )
            r += 1

        r += 1
        # note = (
        #     'Ghi chú: Các chỉ tiêu không có số liệu thì doanh nghiệp không phải trình bày '
        #     'nhưng không được đánh lại "Mã số" chỉ tiêu'
        # )
        # sheet.merge_range(r, 0, r, last_col, note, f_note)
        # r += 2

        dt_lap = self._b03dn_xlsx_parse_date(payload.get("signature_date")) or fields.Date.context_today(self)
        place = self._b03dn_xlsx_company_state_name(company) or "…"
        if dt_lap:
            lap_line = _("%s, %s") % (place, dt_lap.strftime("%d/%m/%Y"))
        else:
            today_lap = fields.Date.context_today(self)
            lap_line = _("%s, %s") % (place, today_lap.strftime("%d/%m/%Y"))
        sheet.merge_range(r, 0, r, last_col, lap_line, f_lap_ngay)
        r += 2

        sheet.write(r, 0, _("Prepared by"), f_sig_label)
        sheet.write(r, 2, _("Chief accountant"), f_sig_label)
        sheet.write(r, 4, _("Director"), f_sig_label)
        r += 1
        sheet.write(r, 0, _("(Signature, full name)"), f_sig_sub)
        sheet.write(r, 2, _("(Signature, full name)"), f_sig_sub)
        sheet.write(r, 4, _("(Signature, full name, stamp)"), f_sig_sub)
        r += 1
        r += 5
        sheet.merge_range(r, 0, r, last_col, _("- Professional license number;"), f_sig_footer_left)
        r += 1
        sheet.merge_range(
            r, 0, r, last_col, _("- Accounting service provider"), f_sig_footer_left
        )
        r += 1
        sheet.merge_range(
            r,
            0,
            r,
            last_col,
            _(
                "Where the preparer is an accounting firm, state the professional license number, "
                "name and address of the accounting service provider. Where the preparer is an individual, "
                "state the professional license number."
            ),
            f_note_footer,
        )

        sheet.protect()
        workbook.read_only_recommended()
        return True
