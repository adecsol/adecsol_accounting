# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    circular_type = fields.Selection(
        related="company_id.circular_type",
        readonly=False,
    )
