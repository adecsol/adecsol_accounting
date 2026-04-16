# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    b03dn_cash_flow_tag_ids = fields.Many2many(
        comodel_name="account.account.tag",
        relation="account_move_line_b03dn_cash_flow_tag_rel",
        column1="move_line_id",
        column2="tag_id",
        string="B03-DN — Cash flow tags (line)",
        help="Optional: tag cash lines directly; if empty, the report uses tags on the "
        "counterpart account per line configuration.",
    )
