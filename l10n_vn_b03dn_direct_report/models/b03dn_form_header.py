# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class L10nVnB03dnFormHeader(models.Model):
    """Right-hand report header: «Form B 03 – DN» and circular reference line."""

    _name = "l10n.vn.b03dn.form.header"
    _description = "B03-DN — Form header"
    _order = "circular_type"

    name = fields.Char(
        string="Description",
        required=True,
        translate=True,
    )
    circular_type = fields.Selection(
        [
            ("tt133", "TT133"),
            ("tt99", "TT99"),
            ("tt200", "TT200"),
        ],
        string="Circular type",
        required=True,
    )
    form_title = fields.Char(
        string="Form reference (line 1)",
        required=True,
        translate=True,
        default="Form B 03 – DN",
        help="Example: «Form B 03 – DN».",
    )
    legal_reference = fields.Text(
        string="Circular reference (line 2)",
        required=True,
        translate=True,
        default="(Issued with Circular No. 200/2014/TT-BTC dated 22/12/2014 by the Ministry of Finance)",
        help="Parenthetical line under the form reference, e.g. legal basis.",
    )

    _sql_constraints = [
        (
            "l10n_vn_b03dn_form_header_circular_type_unique",
            "unique(circular_type)",
            "Only one form header record is allowed per circular type.",
        ),
    ]

    @api.model
    def _default_header_values(self):
        return {
            "form_title": _("Form B 03 – DN"),
            "legal_reference": _(
                "(Issued with Circular No. 200/2014/TT-BTC dated 22/12/2014 by the Ministry of Finance)"
            ),
        }

    @api.model
    def _values_for_company(self, company):
        """Two header lines for the company's circular (or defaults).

        Read with sudo(): the report may use `company` from filters (possibly
        different from the user's active company); record rules tied to
        user.company_id would otherwise miss the row and QWeb falls back to
        defaults.
        """
        if not company:
            return self._default_header_values()
        lang = self.env.context.get("lang")
        if not lang and self.env.uid:
            lang = self.env["res.users"].browse(self.env.uid).sudo().lang
        if not lang:
            lang = "en_US"
        rec = (
            self.sudo()
            .with_context(lang=lang)
            .search(
                [("circular_type", "=", company.circular_type or "tt200")],
                limit=1,
            )
        )
        if rec:
            return {
                "form_title": rec.form_title or "",
                "legal_reference": rec.legal_reference or "",
            }
        return self._default_header_values()
