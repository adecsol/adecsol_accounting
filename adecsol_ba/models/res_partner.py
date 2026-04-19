# -*- coding: utf-8 -*-
# C.2 — Validate res.partner Master Data

import re

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("vat")
    def _check_vat_vietnam(self):
        """Validate Vietnamese Tax ID (MST): 10 or 13 digits, optionally dash-separated."""
        vn_pattern = re.compile(r"^\d{10}(-\d{3})?$")
        for rec in self:
            if rec.vat and rec.country_id and rec.country_id.code == "VN":
                clean_vat = rec.vat.replace(" ", "")
                if not vn_pattern.match(clean_vat):
                    raise ValidationError(
                        _("Invalid Vietnamese Tax ID: '%(vat)s'. "
                          "Tax ID must have 10 or 13 digits (10-3). "
                          "Example: 0301234567 or 0301234567-001.",
                          vat=rec.vat)
                    )

    @api.constrains("email")
    def _check_email_format(self):
        """Basic email format validation."""
        email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        for rec in self:
            if rec.email and not email_pattern.match(rec.email):
                raise ValidationError(
                    _("Invalid email format: '%(email)s'.", email=rec.email)
                )
