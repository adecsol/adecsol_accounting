# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    circular_type = fields.Selection(
        [
            ("tt133", "TT133"),
            ("tt99", "TT99"),
            ("tt200", "TT200"),
        ],
        string="Loại thông tư",
        default="tt200",
        required=True,
        help="Dùng để lọc mẫu báo cáo theo thông tư kế toán áp dụng.",
    )
    b03dn_cash_equiv_account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="res_company_b03dn_cash_equiv_account_rel",
        column1="company_id",
        column2="account_id",
        string="B03-DN — Tài khoản tương đương tiền (ngắn hạn)",
        help="Tài khoản loại tương đương tiền kỳ hạn ngắn được gộp vào luồng tiền "
        "(ví dụ tiểu khoản 128 dưới 3 tháng). Để trống nếu chỉ dùng 111/112/113.",
        check_company=True,
    )
