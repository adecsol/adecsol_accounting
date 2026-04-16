# -*- coding: utf-8 -*-
from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _b03dn_ensure_report_lang(self):
        """Guarantee ``lang`` on the env used for QWeb + translated model fields.

        The web client's HTML report URL (``?options=...&context=...``) can omit
        ``lang`` in ``context``. ``ir.qweb`` then keeps the source language for
        ``ir.ui.view`` terms and some ORM translations.
        """
        if self.env.context.get("lang"):
            return self
        lang = False
        if self.env.uid:
            lang = self.env["res.users"].browse(self.env.uid).sudo().lang
        return self.with_context(lang=lang or "en_US")

    @api.model
    def _render_qweb_html(self, report_ref, docids, data=None):
        self = self._b03dn_ensure_report_lang()
        return super()._render_qweb_html(report_ref, docids, data=data)

    @api.model
    def _render_qweb_text(self, report_ref, docids, data=None):
        self = self._b03dn_ensure_report_lang()
        return super()._render_qweb_text(report_ref, docids, data=data)
