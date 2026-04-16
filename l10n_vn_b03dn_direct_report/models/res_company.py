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
        string="Circular type",
        default="tt200",
        required=True,
        help="Used to filter report templates by the applicable accounting circular.",
    )
    b03dn_cash_equiv_account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="res_company_b03dn_cash_equiv_account_rel",
        column1="company_id",
        column2="account_id",
        string="B03-DN — Cash-equivalent accounts (short-term)",
        help="Short-term cash-equivalent accounts included in cash flows "
        "(e.g. sub-account 128 under 3 months). Leave empty if you only use 111/112/113.",
        check_company=True,
    )
