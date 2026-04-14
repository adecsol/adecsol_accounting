# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class L10nVnB03dnFormHeader(models.Model):
    """Tiêu đề góc phải trên báo cáo: «Mẫu số B 03 – DN» và dòng tham chiếu thông tư."""

    _name = "l10n.vn.b03dn.form.header"
    _description = "B03-DN — Tiêu đề mẫu biểu"
    _order = "circular_type"

    name = fields.Char(
        string="Mô tả",
        required=True,
        translate=True,
    )
    circular_type = fields.Selection(
        [
            ("tt133", "TT133"),
            ("tt99", "TT99"),
            ("tt200", "TT200"),
        ],
        string="Loại thông tư",
        required=True,
    )
    form_title = fields.Char(
        string="Mẫu số (dòng 1)",
        required=True,
        translate=True,
        default="Mẫu số B 03 – DN",
        help="Ví dụ: «Mẫu số B 03 – DN».",
    )
    legal_reference = fields.Text(
        string="Tham chiếu thông tư (dòng 2)",
        required=True,
        translate=True,
        default="(Ban hành theo Thông tư số 200/2014/TT-BTC vào ngày 22/12/2014 của Bộ Tài chính)",
        help="Dòng trong ngoặc dưới mẫu số, ví dụ căn cứ thông tư ban hành.",
    )

    _sql_constraints = [
        (
            "l10n_vn_b03dn_form_header_circular_type_unique",
            "unique(circular_type)",
            "Mỗi loại thông tư chỉ được một bản ghi cấu hình tiêu đề mẫu biểu.",
        ),
    ]

    @api.model
    def _default_header_values(self):
        return {
            "form_title": _("Mẫu số B 03 – DN"),
            "legal_reference": _(
                "(Ban hành theo Thông tư số 200/2014/TT-BTC vào ngày 22/12/2014 của Bộ Tài chính)"
            ),
        }

    @api.model
    def _values_for_company(self, company):
        """Hai dòng tiêu đề theo thông tư của công ty (hoặc mặc định).

        Dùng sudo() khi đọc: báo cáo lấy `company` từ bộ lọc (có thể khác công ty
        active trên user); record rule theo user.company_id thì search trần sẽ
        không trả đúng bản ghi → QWeb luôn rơi về mặc định.
        """
        if not company:
            return self._default_header_values()
        rec = self.sudo().search(
            [("circular_type", "=", company.circular_type)],
            limit=1,
        )
        if rec:
            return {
                "form_title": rec.form_title or "",
                "legal_reference": rec.legal_reference or "",
            }
        return self._default_header_values()
