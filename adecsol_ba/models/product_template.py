# -*- coding: utf-8 -*-
# C.2 — Validate product.template Master Data

import re

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("hs_code")
    def _check_hs_code_format(self):
        """Validate HS Code: 6-10 digits, optionally dot-separated."""
        hs_pattern = re.compile(r"^[\d]{4}(\.?[\d]{2}){1,3}$")
        for rec in self:
            if rec.hs_code:
                clean = rec.hs_code.replace(" ", "")
                if not hs_pattern.match(clean):
                    raise ValidationError(
                        _("Invalid HS Code: '%(code)s'. "
                          "HS Code must have 6-10 digits. Example: 8471.30.10",
                          code=rec.hs_code)
                    )
