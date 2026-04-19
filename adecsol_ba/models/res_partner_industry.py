# -*- coding: utf-8 -*-
# Extend res.partner.industry — Link survey templates by industry

from odoo import fields, models


class ResPartnerIndustry(models.Model):
    _inherit = "res.partner.industry"

    survey_profile_item_ids = fields.Many2many(
        "document.profile.item",
        "ba_industry_profile_item_rel",
        "industry_id",
        "profile_item_id",
        string="Default Survey Template",
        help="Default survey files will be attached "
             "when creating a survey for a customer in this industry.",
    )
