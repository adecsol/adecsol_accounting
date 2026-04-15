# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.tools import date_utils

class TrialBalanceReportWizard(models.TransientModel):
    _inherit = "trial.balance.report.wizard"

    # Các trường đã có sẵn trong Odoo, chỉ cần sử dụng
    # Không cần định nghĩa lại

    def action_export_balance_sheet_tt200(self):
        self.ensure_one()
        # Đảm bảo fy_start_date (Ngày đầu năm tài chính) luôn có giá trị để tính Số dư đầu kỳ cho TK loại 5-9
        if not self.fy_start_date:
            fy_date_from, fy_date_to = date_utils.get_fiscal_year(
                self.date_from,
                day=self.company_id.fiscalyear_last_day or 31,
                month=int(self.company_id.fiscalyear_last_month or 12),
            )
            self.fy_start_date = fy_date_from
        
        data = self._prepare_report_data()
        # Thêm các trường từ popup vào data
        data['hide_account_at_0'] = self.hide_account_at_0
        data['show_hierarchy'] = self.show_hierarchy
        data['limit_hierarchy_level'] = self.limit_hierarchy_level
        data['show_hierarchy_level'] = self.show_hierarchy_level
        data['hide_parent_hierarchy_level'] = self.hide_parent_hierarchy_level
        
        return self.env.ref('accounting_adecsol.trial_balance_xlsx_action').report_action(self, data=data)