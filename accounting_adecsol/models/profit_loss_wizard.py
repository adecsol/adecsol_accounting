# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountingReport(models.TransientModel):
    _inherit = "accounting.report"

    def action_export_b02dn_excel(self):
        """
        Xuất báo cáo Kết quả hoạt động kinh doanh B02-DN
        Lấy tất cả thông tin từ popup để lọc dữ liệu
        """
        self.ensure_one()
        
        # Kiểm tra ngày
        if self.date_from > self.date_to:
            raise UserError("Ngày bắt đầu không thể lớn hơn ngày kết thúc!")
        
        # Chuẩn bị dữ liệu từ popup - BỎ fy_start_date
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
        
        # Gọi report action và truyền data
        report = self.env.ref('accounting_adecsol.profit_loss_xlsx_action')
        return report.report_action(self, data=data)