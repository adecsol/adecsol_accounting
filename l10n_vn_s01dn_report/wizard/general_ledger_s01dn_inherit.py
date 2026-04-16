# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import date_utils


class GeneralLedgerReportWizardS01dn(models.TransientModel):
    _inherit = 'general.ledger.report.wizard'

    @api.model
    def action_open_s01dn_html_menu(self):
        """Open the S01-DN QWeb report directly from the menu (no wizard form)."""
        vals = self.default_get(list(self._fields))
        company = self.env.company
        today = fields.Date.context_today(self)
        if not vals.get('date_from'):
            ds, _de = date_utils.get_fiscal_year(
                today,
                day=company.fiscalyear_last_day,
                month=int(company.fiscalyear_last_month),
            )
            vals['date_from'] = ds
        if not vals.get('date_to'):
            vals['date_to'] = today
        wiz = self.create(vals)
        wiz._set_default_wizard_values()
        data = wiz._prepare_report_data()
        report = self.env.ref(
            'l10n_vn_s01dn_report.general_ledger_s01dn_html_action',
        )
        return report.report_action(wiz, data=data)

    def button_export_s01dn_xlsx(self):
        """Export the S01-DN journal / general ledger to Excel."""
        self.ensure_one()
        self._set_default_wizard_values()
        data = self._prepare_report_data()
        report = self.env.ref(
            'l10n_vn_s01dn_report.general_ledger_s01dn_xlsx_action'
        )
        return report.report_action(self, data=data)

    def button_view_s01dn_html(self):
        """Open the S01-DN journal / general ledger summary in QWeb HTML."""
        self.ensure_one()
        self._set_default_wizard_values()
        data = self._prepare_report_data()
        report = self.env.ref(
            'l10n_vn_s01dn_report.general_ledger_s01dn_html_action'
        )
        return report.report_action(self, data=data)
