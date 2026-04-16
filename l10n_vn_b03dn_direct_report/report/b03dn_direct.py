# -*- coding: utf-8 -*-
import json
from datetime import date

from markupsafe import Markup

from odoo import api, fields, models
from odoo.osv.expression import AND
from odoo.tools.misc import formatLang


class ReportB03dnDirect(models.AbstractModel):
    _name = "report.l10n_vn_b03dn_direct_report.b03dn_direct"
    _description = "B03-DN — QWeb report"

    @api.model
    def _b03dn_env_with_user_lang(self, target=None):
        """Return ``target`` with ``context['lang']`` when it was missing (XLSX, tests)."""
        rs = target if target is not None else self
        if rs.env.context.get("lang"):
            return rs
        lang = False
        if rs.env.uid:
            lang = rs.env["res.users"].browse(rs.env.uid).sudo().lang
        return rs.with_context(lang=lang or "en_US")

    @api.model
    def _b03dn_money_divisor_from_filters(self, filters):
        """VND / thousands / millions — aligned with l10n_vn_s01dn_report (money_unit)."""
        if not filters or not isinstance(filters, dict):
            return 1
        raw = filters.get("money_unit")
        if raw is None:
            return 1
        try:
            v = int(str(raw).strip())
        except (ValueError, TypeError):
            return 1
        if v in (1, 1000, 1000000):
            return v
        return 1

    @api.model
    def _b03dn_display_money_unit_caption(self, divisor):
        return {
            1: self.env._("Unit: VND"),
            1000: self.env._("Unit: thousands of VND"),
            1000000: self.env._("Unit: millions of VND"),
        }.get(divisor, self.env._("Unit: VND"))

    @api.model
    def _b03dn_coerce_ui_filters(self, raw):
        if raw is None:
            return None
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str):
            if not raw.strip():
                return None
            try:
                val = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
            return val if isinstance(val, dict) else None
        return None

    @api.model
    def _b03dn_payload_merged_with_ui(self, wizard, incoming):
        """Merge wizard snapshot with ``b03dn_ui_filters`` (QWeb reload / Excel). UI wins."""
        incoming = dict(incoming or {})
        Wizard = self.env["l10n.vn.b03dn.report.wizard"]
        ui = self._b03dn_coerce_ui_filters(incoming.get("b03dn_ui_filters"))
        if wizard.ids:
            base = wizard._report_payload()
        else:
            base = incoming
        bff = dict(base.get("b03dn_ui_filters") or {})
        mf = {**bff, **(ui or {})}
        need = (
            "company_id",
            "template_id",
            "date_from",
            "date_to",
            "date_from_cmp",
            "date_to_cmp",
        )
        for k in need:
            if mf.get(k) in (None, "", False) and bff.get(k) not in (None, "", False):
                mf[k] = bff[k]

        def _mf_complete(m):
            for k in need:
                v = m.get(k)
                if k in ("company_id", "template_id"):
                    try:
                        if int(v or 0) <= 0:
                            return False
                    except (TypeError, ValueError):
                        return False
                elif v in (None, "", False):
                    return False
            return True

        if _mf_complete(mf):
            return Wizard.build_payload_from_ui_filters(
                mf,
                doc_ids=list(wizard.ids) if wizard.ids else [],
            )
        return base

    @api.model
    def _b03dn_serialize_reload_options(self, docids, b03dn_ui_filters):
        """JSON for ``?options=`` — not HTML-escaped in QWeb (Markup)."""

        def convert(o):
            if isinstance(o, fields.Date):
                return fields.Date.to_string(o)
            if isinstance(o, dict):
                return {k: convert(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [convert(x) for x in o]
            return o

        payload = {
            "doc_ids": list(docids or []),
            "b03dn_ui_filters": convert(dict(b03dn_ui_filters or {})),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @api.model
    def _b03dn_filter_lists(self, company):
        companies = self.env["res.company"].search(
            [("id", "in", self.env.companies.ids)],
            order="name",
        )
        dom = []
        if company:
            ctype = company.circular_type or "tt200"
            dom = [
                "&",
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
                ("circular_type", "=", ctype),
            ]
        templates = self.env["l10n.vn.b03dn.template"].search(
            dom,
            order="name",
        )
        return companies, templates

    @api.model
    def _get_report_values(self, docids, data=None):
        self = self._b03dn_env_with_user_lang(self)
        incoming = dict(data or {})

        if not docids and incoming.get("doc_ids"):
            docids = incoming["doc_ids"]
        if isinstance(docids, str):
            try:
                docids = json.loads(docids)
            except (json.JSONDecodeError, TypeError):
                docids = []
        if not isinstance(docids, (list, tuple)):
            docids = docids and [docids] or []

        wizard = self.env["l10n.vn.b03dn.report.wizard"].browse(docids)
        data = self._b03dn_payload_merged_with_ui(wizard, incoming)

        rows = data.get("rows") or []
        aml_common = data.get("aml_domain_common") or []
        company = data.get("company")

        def domain_for_cell(domain_list):
            if domain_list in (None, False):
                return []
            if not domain_list:
                return []
            if not aml_common:
                return list(domain_list)
            # AND avoids broken composition when the domain contains leading '|' / '&'.
            return AND([domain_list, aml_common])

        currency = data.get("currency")
        money_divisor = self._b03dn_money_divisor_from_filters(
            data.get("b03dn_ui_filters"),
        )

        def format_b03dn_amount(amount, divisor=None):
            if currency is None:
                return ""
            div = float(money_divisor if divisor is None else divisor or 1.0)
            val = float(amount or 0.0) / div
            digits = currency.decimal_places
            if val < 0.0:
                return "(%s)" % formatLang(
                    self.env,
                    abs(val),
                    grouping=True,
                    digits=digits,
                )
            return formatLang(self.env, val, grouping=True, digits=digits)

        xlsx_rep = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]

        def b03dn_line_name_has_visible_text(line_rec):
            return xlsx_rep._b03dn_line_name_has_visible_text(line_rec.name)

        def b03dn_line_shows_money_columns(line_rec):
            return xlsx_rep._b03dn_line_shows_money_columns(line_rec)

        def b03dn_row_row_classes(line_rec):
            """CSS classes for ``<tr>``: bold/italic cols 2–5 from HTML name + ``b03dn_report_bold_amounts``."""
            eb, ei = xlsx_rep._b03dn_effective_row_style_flags(line_rec)
            parts = []
            if eb:
                parts.append("b03dn-row-bold")
            if ei:
                parts.append("b03dn-row-italic")
            return " ".join(parts)

        def b03dn_chi_tieu_td_class(line_rec):
            """Classes for the line-item cell: avoid bold on ``td`` when ``name`` already wraps ``<strong>``."""
            eb, ei = xlsx_rep._b03dn_effective_row_style_flags(line_rec)
            nb, ni = xlsx_rep._b03dn_row_name_style_flags(line_rec.name)
            parts = ["b03dn-chi-tieu"]
            if eb and not nb:
                parts.append("b03dn-chi-tieu-row-bold")
            if ei and not ni:
                parts.append("b03dn-chi-tieu-row-italic")
            return " ".join(parts)

        companies, templates = self._b03dn_filter_lists(company)
        ui_f = data.get("b03dn_ui_filters") or {}
        c_sel = ui_f.get("company_id") or (company.id if company else False)
        t_sel = ui_f.get("template_id") or (
            data.get("template").id if data.get("template") else False
        )
        reload_json = self._b03dn_serialize_reload_options(
            docids,
            ui_f,
        )

        dt_lap = data.get("signature_date") or fields.Date.context_today(self)
        if isinstance(dt_lap, str):
            dt_lap = fields.Date.from_string(dt_lap[:10])
        place_lap = xlsx_rep._b03dn_xlsx_company_state_name(company) or "…"
        b03dn_lap_place_text = f"{place_lap}, "
        _ = self.env._
        if dt_lap and isinstance(dt_lap, date):
            b03dn_lap_date_text = _("dated %s") % dt_lap.strftime("%d/%m/%Y")
        else:
            today_lap = fields.Date.context_today(self)
            b03dn_lap_date_text = _("dated %s") % today_lap.strftime("%d/%m/%Y")

        df_rep = data.get("date_from")
        dt_rep = data.get("date_to")
        if isinstance(df_rep, str):
            df_rep = fields.Date.from_string(df_rep[:10])
        if isinstance(dt_rep, str):
            dt_rep = fields.Date.from_string(dt_rep[:10])

        b03dn_year_line = ""
        if dt_rep:
            y = dt_rep.year
            start_of_year = date(y, 1, 1)
            end_of_year = date(y, 12, 31)
            if df_rep == start_of_year and dt_rep == end_of_year:
                b03dn_year_line = _("Year %s") % y
            else:
                from_str = df_rep.strftime('%d/%m/%Y') if df_rep else '…'
                to_str = dt_rep.strftime('%d/%m/%Y')
                b03dn_year_line = _("Year %s (from %s to %s)") % (y, from_str, to_str)
        else:
            b03dn_year_line = _("Year …")

        hdr_vals = self.env["l10n.vn.b03dn.form.header"]._values_for_company(company)

        tmpl = data.get("template")
        dossier = tmpl.document_dossier_id if tmpl else False
        Dossier = self.env["document.profile.dossier"]
        b03dn_document_dossier_id = dossier.id if dossier else 0

        def b03dn_tm_attachment_id(line_rec):
            if not dossier or not line_rec or line_rec.display_type:
                return False
            return Dossier.profile_attachment_id_for_reference(
                dossier,
                line_rec.explanation_ref,
            )

        def b03dn_tm_expected_file_code(line_rec):
            """Derived file code from dossier + set format + notes column (e.g. …01 + 20 → …01-20)."""
            if not dossier or not line_rec or line_rec.display_type:
                return ""
            return (dossier.expected_code_for_reference(line_rec.explanation_ref) or "").strip()

        def b03dn_tm_is_hyperlink(line_rec):
            if not dossier or not line_rec or line_rec.display_type:
                return False
            if not (line_rec.explanation_ref or "").strip():
                return False
            return bool(b03dn_tm_expected_file_code(line_rec))

        b03dn_report_i18n_json = Markup(
            json.dumps(
                {
                    "datedFormat": _("dated %s"),
                    "unitVnd": _("Unit: VND"),
                    "unit1000": _("Unit: thousands of VND"),
                    "unit1m": _("Unit: millions of VND"),
                },
                ensure_ascii=False,
            )
        )
        b03dn_title_pick_signature_date = _("Click to pick signature date")
        b03dn_title_pick_date = _("Click to pick date")

        return {
            "doc_ids": docids,
            "docs": wizard,
            "company": company,
            "currency": currency,
            "date_from": data.get("date_from"),
            "date_to": data.get("date_to"),
            "date_from_cmp": data.get("date_from_cmp"),
            "date_to_cmp": data.get("date_to_cmp"),
            "template": data.get("template"),
            "rows": rows,
            "aml_domain_common": aml_common,
            "domain_for_cell": domain_for_cell,
            "format_b03dn_amount": format_b03dn_amount,
            "b03dn_money_unit": money_divisor,
            "b03dn_money_unit_select_value": str(money_divisor),
            "b03dn_money_unit_label": self._b03dn_display_money_unit_caption(
                money_divisor,
            ),
            "b03dn_line_name_has_visible_text": b03dn_line_name_has_visible_text,
            "b03dn_line_shows_money_columns": b03dn_line_shows_money_columns,
            "b03dn_row_row_classes": b03dn_row_row_classes,
            "b03dn_chi_tieu_td_class": b03dn_chi_tieu_td_class,
            "b03dn_report_reload_json": Markup(reload_json),
            "b03dn_filter_companies": companies,
            "b03dn_filter_templates": templates,
            "b03dn_selected_company_id": c_sel,
            "b03dn_selected_template_id": t_sel,
            "b03dn_ui_filter_date_from": ui_f.get("date_from") or "",
            "b03dn_ui_filter_date_to": ui_f.get("date_to") or "",
            "b03dn_ui_filter_date_from_cmp": ui_f.get("date_from_cmp") or "",
            "b03dn_ui_filter_date_to_cmp": ui_f.get("date_to_cmp") or "",
            "b03dn_ui_filter_company_id": ui_f.get("company_id"),
            "b03dn_ui_filter_template_id": ui_f.get("template_id"),
            "b03dn_ui_filter_signature_date": ui_f.get("signature_date") or "",
            "b03dn_company_address": xlsx_rep._b03dn_xlsx_company_address(company),
            "b03dn_company_state_name": xlsx_rep._b03dn_xlsx_company_state_name(
                company,
            ),
            "b03dn_lap_place_text": b03dn_lap_place_text,
            "b03dn_lap_date_text": b03dn_lap_date_text,
            "b03dn_today_iso": fields.Date.context_today(self).strftime("%Y-%m-%d"),
            "b03dn_year_line": b03dn_year_line,
            "b03dn_form_title": hdr_vals["form_title"],
            "b03dn_form_legal_reference": hdr_vals["legal_reference"],
            "b03dn_document_dossier_id": b03dn_document_dossier_id,
            "b03dn_tm_attachment_id": b03dn_tm_attachment_id,
            "b03dn_tm_expected_file_code": b03dn_tm_expected_file_code,
            "b03dn_tm_is_hyperlink": b03dn_tm_is_hyperlink,
            "b03dn_report_i18n_json": b03dn_report_i18n_json,
            "b03dn_title_pick_signature_date": b03dn_title_pick_signature_date,
            "b03dn_title_pick_date": b03dn_title_pick_date,
        }
