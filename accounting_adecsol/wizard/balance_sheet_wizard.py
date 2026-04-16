# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountingReport(models.TransientModel):
    _inherit = "accounting.report"

    def action_export_b01dn_excel(self):
        """
        Export balance sheet B01-DN (Excel).
        Uses all filter fields from the wizard.
        """
        self.ensure_one()

        if self.date_from > self.date_to:
            raise UserError(_("Start date cannot be after end date."))

        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company_id.id,
            'target_move': self.target_move,
            'journal_ids': self.journal_ids.ids if self.journal_ids else [],
            'enable_filter': self.enable_filter if hasattr(self, 'enable_filter') else False,
            'filter_cmp': self.filter_cmp if hasattr(self, 'filter_cmp') else False,
            'date_from_cmp': self.date_from_cmp if hasattr(self, 'date_from_cmp') else False,
            'date_to_cmp': self.date_to_cmp if hasattr(self, 'date_to_cmp') else False,
            'debit_credit': self.debit_credit if hasattr(self, 'debit_credit') else False,
        }

        report = self.env.ref('accounting_adecsol.balance_sheet_xlsx_action')
        return report.report_action(self, data=data)
