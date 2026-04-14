# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape


def _b03dn_html_has_visible_text(html_value):
    if not html_value or not str(html_value).strip():
        return False
    plain = re.sub(r"<[^>]+>", "", str(html_value))
    return bool(plain.strip())


class L10nVnB03dnTemplate(models.Model):
    _name = "l10n.vn.b03dn.template"
    _description = "B03-DN (trực tiếp) — Mẫu báo cáo"

    name = fields.Char(required=True, translate=True)
    circular_type = fields.Selection(
        [
            ("tt133", "TT133"),
            ("tt99", "TT99"),
            ("tt200", "TT200"),
        ],
        string="Loại thông tư",
        default="tt200",
        required=True,
        help="Phải khớp «Loại thông tư» trên công ty để mẫu hiển thị trên báo cáo.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        help="Để trống: dùng cho mọi công ty.",
    )
    document_dossier_id = fields.Many2one(
        "document.profile.dossier",
        string="Hồ sơ thuyết minh",
        ondelete="set null",
        help="Khi chọn: trên báo cáo HTML, cột «Thuyết minh» mở tệp có mã khớp "
        "(tham chiếu TM trùng với dòng chỉ tiêu, vd. 05 → …-05).",
    )
    cash_account_ids = fields.Many2many(
        "account.account",
        "b03dn_template_cash_account_rel",
        "template_id",
        "account_id",
        string="Tài khoản tiền & TĐT (override)",
        help="Nếu đặt, chỉ các TK này được quét. Để trống: 111/112/113 theo công ty + "
        "TK tương đương tiền trên res.company.",
        check_company=True,
    )
    line_ids = fields.One2many(
        "l10n.vn.b03dn.line",
        "template_id",
        string="Chỉ tiêu",
        copy=True,
    )
    b03dn_tag_config_alert = fields.Html(
        string="Cảnh báo cấu hình thẻ",
        compute="_compute_b03dn_tag_config_alert",
        sanitize=False,
    )

    @api.depends(
        "line_ids",
        "line_ids.display_type",
        "line_ids.tag_ids",
        "line_ids.exclude_tag_ids",
    )
    def _compute_b03dn_tag_config_alert(self):
        for tmpl in self:
            comp_lines = tmpl.line_ids.filtered(lambda l: not l.display_type)
            required_union = comp_lines.mapped("tag_ids")
            exclude_union = comp_lines.mapped("exclude_tag_ids")
            only_in_required = required_union - exclude_union
            if not only_in_required:
                tmpl.b03dn_tag_config_alert = False
                continue
            badges = Markup(", ").join(
                Markup('<span class="badge text-bg-secondary me-1">%s</span>')
                % html_escape((t.display_name or t.name or "").strip() or str(t.id))
                for t in only_in_required.sorted(key=lambda t: (t.name or "").lower())
            )
            title = html_escape(
                _(
                    "Có thẻ chỉ xuất hiện trong «Thẻ yêu cầu» mà không có trong "
                    "«Thẻ loại trừ» của bất kỳ chỉ tiêu nào trên template:"
                )
            )
            tmpl.b03dn_tag_config_alert = Markup(
                '<div class="alert alert-warning mb-3" role="alert">'
                "<p class=\"mb-2\"><strong>%s</strong></p>"
                "<p class=\"mb-0\">%s</p>"
                "</div>"
            ) % (Markup(title), badges)


class L10nVnB03dnLine(models.Model):
    _name = "l10n.vn.b03dn.line"
    _description = "B03-DN (trực tiếp) — Dòng chỉ tiêu / quy tắc"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "l10n.vn.b03dn.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    display_type = fields.Selection(
        [
            ("line_section", "Phần"),
            ("line_note", "Ghi chú"),
        ],
        default=False,
        help="Chỉ dùng cho giao diện danh sách (widget): tiêu đề phần / ghi chú; "
        "để trống = dòng chỉ tiêu tính toán (cấu hình mẫu TK / tổng / đầu kỳ / tỷ giá).",
    )

    code = fields.Char(
        size=8,
        help="Mã số chỉ tiêu (vd: 01, 20, 70). Không bắt buộc trên dòng Phần / Ghi chú.",
    )
    name = fields.Html(
        translate=True,
        help="Dòng Phần / Ghi chú có thể để trống. Dòng chỉ tiêu tính toán phải có nội dung.",
    )
    explanation_ref = fields.Char(
        string="Thuyết minh",
        translate=True,
        help="Ký hiệu thuyết minh trên B03 (nếu có).",
    )

    debit_account_patterns = fields.Char(
        string="Mẫu tài khoản Nợ",
        help="Các mẫu mã tài khoản, phân tách bằng dấu phẩy (vd. 331%, 152%). "
        "Luồng tiền ra (bên Có tiền): khớp dòng đối ứng phía Nợ (cột TK Nợ TT200; không gồm tiền).",
    )
    credit_account_patterns = fields.Char(
        string="Mẫu tài khoản Có",
        help="Các mẫu mã tài khoản, phân tách bằng dấu phẩy. "
        "Luồng tiền vào (bên Nợ tiền): khớp dòng đối ứng phía Có (cột TK Có TT200).",
    )
    exclude_account_patterns = fields.Char(
        string="Loại trừ mẫu TK đối ứng",
        help="Danh sách mã TK (phân tách bằng dấu phẩy), hỗ trợ hậu tố %% như các mẫu Nợ/Có. "
        "Nếu mã TK đối ứng (hoặc bất kỳ mã trong chuỗi đối ứng ghép) khớp một mẫu loại trừ, "
        "luật leaf này không áp dụng cho mảnh đó (có thể rơi xuống dòng chỉ tiêu khác).",
    )
    amount_multiplier = fields.Float(
        default=1.0,
        help="Nhân số sau phân bổ (thường -1 cho các khoản chi ra).",
    )
    tag_ids = fields.Many2many(
        "account.account.tag",
        "l10n_vn_b03dn_line_tag_rel",
        "line_id",
        "tag_id",
        string="Thẻ yêu cầu",
    )
    exclude_tag_ids = fields.Many2many(
        "account.account.tag",
        "l10n_vn_b03dn_line_exclude_tag_rel",
        "line_id",
        "tag_id",
        string="Thẻ loại trừ",
        help="Gán thẻ cho TK (hoặc thẻ dòng tiền B03-DN trên bút toán, tùy «Nguồn thẻ») để "
        "loại các giao dịch khớp mẫu TK nhưng không thuộc chỉ tiêu này. Cùng tập thẻ với "
        "«Thẻ yêu cầu» để đánh giá.",
    )
    tag_match_mode = fields.Selection(
        [
            ("all", "Phải có đủ các thẻ"),
            ("any", "Có ít nhất một thẻ"),
        ],
        default="any",
        required=True,
    )
    tag_source = fields.Selection(
        [
            ("counterpart_account", "Thẻ trên TK đối ứng"),
            ("cash_line", "Thẻ trên dòng tiền (B03-DN)"),
            ("either", "Ưu tiên dòng tiền, sau đó TK đối ứng"),
        ],
        default="either",
    )

    sum_expression = fields.Char(
        string="Biểu thức cộng",
        help="Ví dụ: 01+02 hoặc 20+30+40. Khi có trường này: chỉ tiêu = tổng các mã (aggregate). "
        "Không kết hợp với pattern đầu kỳ / tỷ giá / lọc dòng tiền.",
    )

    use_opening_cash_balance = fields.Boolean(
        string="Tiền & TĐT đầu kỳ",
        help="Khi bật: lấy số dư các TK tiền (theo cấu hình template) tại ngày trước kỳ báo cáo. "
        "Không dùng chung với biểu thức cộng, mẫu tỷ giá hay pattern lọc.",
    )

    fx_account_patterns = fields.Char(
        string="Mẫu TK cho bút từ tỷ giá",
        help="Khi nhập: chỉ tiêu lấy tổng biến động TK khớp mẫu trong kỳ (vd. 413%%). "
        "Không dùng chung với biểu thức cộng, đầu kỳ hay pattern lọc dòng tiền.",
    )

    extra_domain = fields.Char(
        string="Bộ lọc bổ sung (dòng bút toán)",
        help="Chuỗi domain JSON Odoo trên account.move.line, áp dụng thêm sau khi đã khớp quy tắc chi tiết.",
    )

    b03dn_report_bold_amounts = fields.Boolean(
        string="Báo cáo: in đậm số",
        compute="_compute_b03dn_report_bold_amounts",
    )

    @api.depends("display_type", "sum_expression", "use_opening_cash_balance")
    def _compute_b03dn_report_bold_amounts(self):
        for line in self:
            if line.display_type == "line_section":
                line.b03dn_report_bold_amounts = True
            elif line.display_type:
                line.b03dn_report_bold_amounts = False
            else:
                line.b03dn_report_bold_amounts = bool(
                    (line.sum_expression or "").strip()
                ) or line.use_opening_cash_balance

    def _b03dn_sum_stripped(self):
        return (self.sum_expression or "").replace(" ", "").strip()

    def _b03dn_is_aggregate_line(self):
        return bool(self._b03dn_sum_stripped()) and not self.display_type

    def _b03dn_is_opening_line(self):
        return bool(self.use_opening_cash_balance) and not self.display_type

    def _b03dn_is_fx_line(self):
        fx = (self.fx_account_patterns or "").strip()
        if not fx or self.display_type:
            return False
        return (
            not self._b03dn_is_aggregate_line()
            and not self._b03dn_is_opening_line()
        )

    def _b03dn_is_leaf_line(self):
        if (
            self.display_type
            or self._b03dn_is_aggregate_line()
            or self._b03dn_is_opening_line()
            or self._b03dn_is_fx_line()
        ):
            return False
        d_pat = (self.debit_account_patterns or "").strip()
        c_pat = (self.credit_account_patterns or "").strip()
        return bool(d_pat or c_pat or self.tag_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        dt = ctx.get("default_display_type")
        if dt in ("line_section", "line_note"):
            res["display_type"] = dt
        elif "default_display_type" in ctx and not dt:
            res["display_type"] = False
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code") is not None:
                c = (vals.get("code") or "").strip()
                vals["code"] = c or False
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals:
            v = vals["code"]
            if isinstance(v, str):
                c = v.strip()
                vals["code"] = c or False
            elif not v:
                vals["code"] = False
        return super().write(vals)

    @api.constrains(
        "display_type",
        "sum_expression",
        "use_opening_cash_balance",
        "fx_account_patterns",
        "debit_account_patterns",
        "credit_account_patterns",
        "tag_ids",
    )
    def _b03dn_line_exclusive_computation(self):
        for line in self:
            if line.display_type:
                continue
            sum_e = line._b03dn_sum_stripped()
            d_pat = (line.debit_account_patterns or "").strip()
            c_pat = (line.credit_account_patterns or "").strip()
            fx = (line.fx_account_patterns or "").strip()
            leaf = bool(d_pat or c_pat or line.tag_ids)
            modes = (
                bool(sum_e)
                + bool(line.use_opening_cash_balance)
                + bool(fx)
                + bool(leaf)
            )
            if modes == 0:
                raise ValidationError(
                    self.env._(
                        "Dòng tính toán phải có đúng một kiểu: biểu thức cộng, đầu kỳ tiền, "
                        "mẫu TK tỷ giá, hoặc lọc dòng tiền (pattern Nợ/Có và/hoặc thẻ). "
                        "(id dòng: %s)",
                        line.id,
                    )
                )
            if modes > 1:
                raise ValidationError(
                    self.env._(
                        "Chỉ được cấu hình một kiểu tính: tổng (biểu thức), đầu kỳ, tỷ giá, "
                        "hoặc lọc leaf — không trộn. (id dòng: %s)",
                        line.id,
                    )
                )

    @api.constrains("code", "display_type")
    def _b03dn_line_code_required_computing(self):
        for line in self:
            if line.display_type:
                continue
            c = (line.code or "").strip()
            if not c:
                raise ValidationError(
                    self.env._(
                        "Phải nhập mã chỉ tiêu cho dòng tính toán (id dòng: %s).",
                        line.id,
                    )
                )

    @api.constrains("name", "display_type")
    def _b03dn_name_required_for_computing_lines(self):
        for line in self:
            if line.display_type:
                continue
            if not _b03dn_html_has_visible_text(line.name):
                raise ValidationError(
                    self.env._(
                        "Phải nhập «Chỉ tiêu» (tên) cho dòng tính toán (id dòng: %s).",
                        line.id,
                    )
                )

    @api.constrains("code", "template_id")
    def _b03dn_line_code_unique_per_template(self):
        for line in self:
            c = (line.code or "").strip()
            if not c:
                continue
            n = self.search_count(
                [
                    ("template_id", "=", line.template_id.id),
                    ("id", "!=", line.id),
                    ("code", "=", c),
                ]
            )
            if n:
                raise ValidationError(
                    self.env._(
                        "Mã chỉ tiêu «%s» đã tồn tại trên template này.",
                        c,
                    )
                )
