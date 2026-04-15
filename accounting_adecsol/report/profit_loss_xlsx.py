# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class ProfitLossXlsx(models.AbstractModel):
    _name = 'report.accounting_adecsol.profit_loss_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Báo cáo Kết quả hoạt động kinh doanh B02-DN theo TT200'

    def generate_xlsx_report(self, workbook, data, objects):
        """
        Generate Profit & Loss report according to Circular 200/2014/TT-BTC
        """
        # ===========================================================
        # 1. XỬ LÝ DỮ LIỆU ĐẦU VÀO
        # ===========================================================
        if objects and isinstance(objects, list) and objects:
            wizard = objects[0]
            company = wizard.company_id if hasattr(wizard, 'company_id') else self.env.company
            date_from = wizard.date_from if hasattr(wizard, 'date_from') else fields.Date.today()
            date_to = wizard.date_to if hasattr(wizard, 'date_to') else fields.Date.today()
            target_move = wizard.target_move if hasattr(wizard, 'target_move') else 'posted'
            journal_ids = wizard.journal_ids.ids if hasattr(wizard, 'journal_ids') and wizard.journal_ids else []
        else:
            company = self.env.company
            date_from = data.get('date_from', fields.Date.today())
            date_to = data.get('date_to', fields.Date.today())
            target_move = data.get('target_move', 'posted')
            journal_ids = data.get('journal_ids', [])
        
        if isinstance(date_to, bool) or not date_to:
            date_to = fields.Date.today()
        if isinstance(date_from, bool) or not date_from:
            date_from = date_to.replace(month=1, day=1)
        
        if isinstance(date_from, str):
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if isinstance(date_to, str):
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        _logger.info("="*50)
        _logger.info(f"Generating Profit & Loss from {date_from} to {date_to}")
        _logger.info(f"Company: {company.name}")
        _logger.info(f"Target move: {target_move}")
        _logger.info(f"Journals: {journal_ids}")
        _logger.info("="*50)
        
        # ===========================================================
        # 2. TẠO WORKBOOK VÀ FORMATS
        # ===========================================================
        sheet = workbook.add_worksheet('B 02 – DN')
        formats = self._create_excel_formats(workbook)
        
        # Đặt độ rộng cột - 5 CỘT
        sheet.set_column('A:A', 50)  # Chỉ tiêu
        sheet.set_column('B:B', 10)  # Mã số
        sheet.set_column('C:C', 12)  # Thuyết minh
        sheet.set_column('D:E', 18)  # Năm nay, Năm trước
        
        # ===========================================================
        # 3. GHI TIÊU ĐỀ
        # ===========================================================
        row = self._write_report_header(sheet, formats, workbook, company, date_from, date_to)
        
        # ===========================================================
        # 4. TÍNH TOÁN SỐ LIỆU
        # ===========================================================
        balances = self._calculate_balances(date_from, date_to, target_move, company, journal_ids)
        indicators = self._get_indicator_mapping(balances)
        
        # ===========================================================
        # 5. GHI DỮ LIỆU
        # ===========================================================
        row = self._write_indicator_data(sheet, formats, workbook, indicators, row)
        
        # ===========================================================
        # 6. GHI CHỮ KÝ
        # ===========================================================
        self._write_signature(sheet, formats, workbook, row, date_to)
        
        return True
    
    # -----------------------------------------------------------------
    # CÁC HÀM HELPER
    # -----------------------------------------------------------------
    
    def _create_excel_formats(self, workbook):
        """Tạo các định dạng Excel"""
        center_border = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Times New Roman'
        })
        
        center_bold_border = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Times New Roman'
        })
        
        return {
            'title_bold': workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 14}),
            'title_italic': workbook.add_format({'italic': True, 'align': 'center', 'font_name': 'Times New Roman', 'font_size': 9}),
            'header': workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#E9ECEF', 'font_name': 'Times New Roman'}),
            'header_number': workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#E9ECEF', 'font_name': 'Times New Roman'}),
            'bold_label': workbook.add_format({'bold': True, 'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_name': 'Times New Roman'}),
            'bold_center': center_bold_border,
            'bold_number': workbook.add_format({'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0', 'font_name': 'Times New Roman'}),
            'normal_border': workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_name': 'Times New Roman'}),
            'normal_center': center_border,
            'money': workbook.add_format({'num_format': '#,##0', 'border': 1, 'align': 'right', 'valign': 'vcenter', 'font_name': 'Times New Roman'}),
            'negative': workbook.add_format({'num_format': '#,##0;[Red](#,##0)', 'border': 1, 'align': 'right', 'valign': 'vcenter', 'font_name': 'Times New Roman'}),
            'negative_bold': workbook.add_format({'num_format': '#,##0;[Red](#,##0)', 'border': 1, 'bold': True, 'align': 'right', 'valign': 'vcenter', 'font_name': 'Times New Roman'}),
            'signature': workbook.add_format({'align': 'center', 'bold': True, 'font_name': 'Times New Roman'}),
            'signature_border': workbook.add_format({'align': 'center', 'border': 1, 'font_name': 'Times New Roman'}),
        }
    
    def _calculate_balances(self, date_from, date_to, target_move, company, journal_ids=None):
        """Tính số dư tài khoản với bộ lọc journal"""
        balances = {}
        
        # Domain cơ bản
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company.id),
        ]
        
        if target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        
        # Thêm bộ lọc journal nếu có
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))
        
        _logger.info(f"Search domain: {domain}")
        
        # Lấy tất cả tài khoản
        accounts = self.env['account.account'].search([
            ('company_ids', 'in', [company.id])
        ])
        
        # Danh sách tài khoản cần lấy cho B02-DN
        account_prefixes = ['511', '512', '515', '632', '635', '641', '642', '711', '811', '8211', '8212']
        
        for acc in accounts:
            # Kiểm tra nếu tài khoản có mã bắt đầu bằng các prefix trên
            for prefix in account_prefixes:
                if acc.code and str(acc.code).startswith(prefix):
                    _logger.info(f"Found account: {acc.code} - {acc.name}")
                    
                    # Lấy dòng phát sinh
                    lines = self.env['account.move.line'].search(
                        domain + [('account_id', '=', acc.id)]
                    )
                    
                    total_debit = sum(lines.mapped('debit'))
                    total_credit = sum(lines.mapped('credit'))
                    
                    if total_debit > 0 or total_credit > 0:
                        balances[acc.code] = {
                            'debit': total_debit,
                            'credit': total_credit
                        }
                        _logger.info(f"  -> Debit: {total_debit}, Credit: {total_credit}")
                    break
        
        _logger.info(f"Total accounts with data: {len(balances)}")
        return balances
    
    def _get_indicator_mapping(self, balances):
        """Định nghĩa các chỉ tiêu B02-DN"""
        
        def get_bal(prefixes, side='credit'):
            total = 0
            for code, values in balances.items():
                if any(code.startswith(prefix) for prefix in prefixes):
                    if side == 'credit':
                        total += values['credit'] - values['debit']
                    else:  # debit
                        total += values['debit'] - values['credit']
            return total
        
        # Doanh thu (TK 5xx)
        doanh_thu = get_bal(['511', '512'], 'credit')
        dt_tai_chinh = get_bal(['515'], 'credit')
        tn_khac = get_bal(['711'], 'credit')
        
        # Giá vốn & Chi phí (TK 6xx, 8xx)
        gia_von = get_bal(['632'], 'debit')
        cp_tai_chinh = get_bal(['635'], 'debit')
        lai_vay = get_bal(['6351', '6352'], 'debit')
        cp_ban_hang = get_bal(['641'], 'debit')
        cp_qldn = get_bal(['642'], 'debit')
        cp_khac = get_bal(['811'], 'debit')
        thue_tndn = get_bal(['8211', '8212'], 'debit')
        
        # Log để debug
        _logger.info(f"===== B02-DN CALCULATION =====")
        _logger.info(f"Doanh thu: {doanh_thu}")
        _logger.info(f"Giá vốn: {gia_von}")
        _logger.info(f"Chi phí bán hàng: {cp_ban_hang}")
        _logger.info(f"Chi phí QLDN: {cp_qldn}")
        _logger.info(f"Doanh thu TC: {dt_tai_chinh}")
        _logger.info(f"Chi phí TC: {cp_tai_chinh}")
        _logger.info(f"Thu nhập khác: {tn_khac}")
        _logger.info(f"Chi phí khác: {cp_khac}")
        _logger.info(f"Thuế TNDN: {thue_tndn}")
        _logger.info("="*30)
        
        # Tính các chỉ tiêu tổng hợp
        doanh_thu_thuan = doanh_thu
        loi_nhuan_gop = doanh_thu - gia_von
        loi_nhuan_thuan = loi_nhuan_gop + (dt_tai_chinh - cp_tai_chinh) - (cp_ban_hang + cp_qldn)
        loi_nhuan_khac = tn_khac - cp_khac
        loi_nhuan_truoc_thue = loi_nhuan_thuan + loi_nhuan_khac
        loi_nhuan_sau_thue = loi_nhuan_truoc_thue - thue_tndn
        
        return [
            {'code': '1', 'name': '1. Doanh thu bán hàng và cung cấp dịch vụ', 'amount': doanh_thu, 'is_total': False, 'is_negative': False},
            {'code': '2', 'name': '2. Các khoản giảm trừ doanh thu', 'amount': 0, 'is_total': False, 'is_negative': True},
            {'code': '10', 'name': '3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (10 = 01 - 02)', 'amount': doanh_thu_thuan, 'is_total': True, 'is_negative': False},
            {'code': '11', 'name': '4. Giá vốn hàng bán', 'amount': -gia_von, 'is_total': False, 'is_negative': True},
            {'code': '20', 'name': '5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ (20 = 10 - 11)', 'amount': loi_nhuan_gop, 'is_total': True, 'is_negative': False},
            {'code': '21', 'name': '6. Doanh thu hoạt động tài chính', 'amount': dt_tai_chinh, 'is_total': False, 'is_negative': False},
            {'code': '22', 'name': '7. Chi phí tài chính', 'amount': -cp_tai_chinh, 'is_total': False, 'is_negative': True},
            {'code': '23', 'name': '- Trong đó: Chi phí lãi vay', 'amount': -lai_vay, 'is_total': False, 'is_negative': True},
            {'code': '25', 'name': '8. Chi phí bán hàng', 'amount': -cp_ban_hang, 'is_total': False, 'is_negative': True},
            {'code': '26', 'name': '9. Chi phí quản lý doanh nghiệp', 'amount': -cp_qldn, 'is_total': False, 'is_negative': True},
            {'code': '30', 'name': '10. Lợi nhuận thuần từ hoạt động kinh doanh (30 = 20 + (21 - 22) - (25 + 26))', 'amount': loi_nhuan_thuan, 'is_total': True, 'is_negative': False},
            {'code': '31', 'name': '11. Thu nhập khác', 'amount': tn_khac, 'is_total': False, 'is_negative': False},
            {'code': '32', 'name': '12. Chi phí khác', 'amount': -cp_khac, 'is_total': False, 'is_negative': True},
            {'code': '40', 'name': '13. Lợi nhuận khác (40 = 31 - 32)', 'amount': loi_nhuan_khac, 'is_total': True, 'is_negative': False},
            {'code': '50', 'name': '14. Tổng lợi nhuận kế toán trước thuế (50 = 30 + 40)', 'amount': loi_nhuan_truoc_thue, 'is_total': True, 'is_negative': False},
            {'code': '51', 'name': '15. Chi phí thuế TNDN hiện hành', 'amount': -thue_tndn, 'is_total': False, 'is_negative': True},
            {'code': '52', 'name': '16. Chi phí thuế TNDN hoãn lại', 'amount': 0, 'is_total': False, 'is_negative': True},
            {'code': '60', 'name': '17. Lợi nhuận sau thuế thu nhập doanh nghiệp (60 = 50 - 51 - 52)', 'amount': loi_nhuan_sau_thue, 'is_total': True, 'is_negative': False},
            {'code': '70', 'name': '18. Lãi cơ bản trên cổ phiếu (*)', 'amount': 0, 'is_total': False, 'is_negative': False},
            {'code': '71', 'name': '19. Lãi suy giảm trên cổ phiếu (*)', 'amount': 0, 'is_total': False, 'is_negative': False},
        ]
    
    def _write_report_header(self, sheet, formats, workbook, company, date_from, date_to):
        """Ghi tiêu đề báo cáo"""
        company_name = company.name.upper() if company and company.name else ''
        sheet.merge_range(0, 0, 0, 2, company_name, formats['title_bold'])
        sheet.merge_range(0, 3, 0, 4, 'Mẫu số B 02-DN', 
                          workbook.add_format({'bold': True, 'align': 'right', 'font_name': 'Times New Roman'}))
        
        street = company.street or 'Địa chỉ: …'
        sheet.merge_range(1, 0, 1, 2, street, formats['normal_border'])
        sheet.merge_range(1, 3, 1, 4, '(Ban hành theo Thông tư số 200/2014/TT-BTC)', formats['title_italic'])
        
        sheet.merge_range(3, 0, 3, 4, 'BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH', 
                          workbook.add_format({'bold': True, 'align': 'center', 'size': 16, 'font_name': 'Times New Roman'}))
        sheet.merge_range(4, 0, 4, 4, f'Năm {date_from.year}', 
                          workbook.add_format({'italic': True, 'align': 'center', 'font_name': 'Times New Roman'}))
        
        # Header bảng - 5 CỘT
        headers = ['CHỈ TIÊU', 'Mã số', 'Thuyết minh', 'Năm nay', 'Năm trước']
        for col, title in enumerate(headers):
            sheet.write(6, col, title, formats['header'])
        
        notes = ['1', '2', '3', '4', '5']
        for col, note in enumerate(notes):
            sheet.write(7, col, note, formats['header_number'])
        
        return 8
    
    def _write_indicator_data(self, sheet, formats, workbook, indicators, start_row):
        """Ghi dữ liệu các chỉ tiêu"""
        row = start_row
        for ind in indicators:
            code = ind['code']
            name = ind['name']
            amount = ind['amount']
            is_total = ind['is_total']
            is_negative = ind['is_negative']
            
            label_format = formats['normal_border']  # Tất cả đều dùng chữ thường
            code_format = formats['normal_center']
            
            if is_total:
                money_format = formats['negative_bold'] if is_negative and amount < 0 else formats['bold_number']
            else:
                money_format = formats['negative'] if is_negative and amount < 0 else formats['money']
            
            sheet.write(row, 0, name, label_format)
            sheet.write(row, 1, code, code_format)
            sheet.write(row, 2, '', code_format)
            sheet.write(row, 3, amount, money_format)
            sheet.write(row, 4, 0, money_format)
            row += 1
            
            if code in ['10', '20', '30', '40', '50', '60']:
                row += 1
        
        # Ghi chú (*)
        row += 1
        sheet.write(row, 0, '(*) Chỉ áp dụng tại công ty cổ phần', formats['title_italic'])
        return row + 1
    
    def _write_signature(self, sheet, formats, workbook, row, date_to):
        """Ghi phần chữ ký"""
        row += 2
        
        # Dòng ngày tháng
        date_str = date_to.strftime("Ngày %d tháng %m năm %Y") if date_to else "Ngày .. tháng .. năm 20.."
        sheet.merge_range(row, 2, row, 4, date_str, 
                          workbook.add_format({'align': 'right', 'font_name': 'Times New Roman', 'italic': True}))
        row += 2
        
        no_border = workbook.add_format({'font_name': 'Times New Roman', 'align': 'center'})
        no_border_bold = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'align': 'center'})
        
        # Dòng chức danh
        sheet.write(row, 0, 'Người lập biểu', no_border_bold)
        sheet.write(row, 1, 'Kế toán trưởng', no_border_bold)
        sheet.write(row, 3, 'Giám đốc', no_border_bold)
        row += 1
        
        # Dòng hướng dẫn ký
        sheet.write(row, 0, '(Ký, họ tên)', no_border)
        sheet.write(row, 1, '(Ký, họ tên)', no_border)
        sheet.write(row, 3, '(Ký, họ tên, đóng dấu)', no_border)