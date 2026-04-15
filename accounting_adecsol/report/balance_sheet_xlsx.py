# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class BalanceSheetXlsx(models.AbstractModel):
    _name = 'report.accounting_adecsol.balance_sheet_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Bảng Cân Đối Kế Toán B01-DN theo TT200'

    def generate_xlsx_report(self, workbook, data, objects):
        """
        Generate Balance Sheet report according to Circular 200/2014/TT-BTC
        """
        # ===========================================================
        # 1. XỬ LÝ DỮ LIỆU ĐẦU VÀO
        # ===========================================================
        # Lấy thông tin từ objects hoặc data
        if objects and isinstance(objects, list) and objects:
            wizard = objects[0]
            company = wizard.company_id if hasattr(wizard, 'company_id') else self.env.company
            date_from = wizard.date_from if hasattr(wizard, 'date_from') else fields.Date.today()
            date_to = wizard.date_to if hasattr(wizard, 'date_to') else fields.Date.today()
            target_move = wizard.target_move if hasattr(wizard, 'target_move') else 'posted'
        else:
            # Nếu gọi từ action report không qua wizard
            company = self.env.company
            date_from = data.get('date_from', fields.Date.today())
            date_to = data.get('date_to', fields.Date.today())
            target_move = data.get('target_move', 'posted')
        
        # Xử lý date_to nếu là bool
        if isinstance(date_to, bool) or not date_to:
            date_to = fields.Date.today()
        
        # Xử lý date_from nếu là bool
        if isinstance(date_from, bool) or not date_from:
            # Mặc định lấy đầu năm tài chính
            fiscal_date = self._get_fiscal_start(date_to, company)
            date_from = fiscal_date
        
        # Chuyển đổi sang date object nếu là string
        if isinstance(date_from, str):
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if isinstance(date_to, str):
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Tính ngày đầu năm tài chính (cho số đầu năm)
        fy_start = self._get_fiscal_start(date_to, company)
        
        _logger.info(f"Generating Balance Sheet from {date_from} to {date_to}, FY start: {fy_start}")
        
        # ===========================================================
        # 2. TẠO WORKBOOK VÀ FORMATS
        # ===========================================================
        sheet = workbook.add_worksheet('B 01 – DN')
        
        # Định dạng chính
        formats = self._create_excel_formats(workbook)
        
        # Đặt độ rộng cột
        sheet.set_column('A:A', 50)  # Tên chỉ tiêu
        sheet.set_column('B:B', 8)   # Mã số
        sheet.set_column('C:C', 12)  # Thuyết minh
        sheet.set_column('D:E', 18)  # Số cuối năm, Số đầu năm
        
        # ===========================================================
        # 3. GHI TIÊU ĐỀ BÁO CÁO
        # ===========================================================
        row = self._write_report_header(sheet, formats, workbook, company, date_from, date_to)
        
        # ===========================================================
        # 4. TÍNH TOÁN SỐ LIỆU
        # ===========================================================
        # Tính số cuối kỳ (tại ngày date_to)
        end_balances = self._calculate_balances(date_to, target_move, company)
        
        # Tính số đầu năm (tại ngày fy_start - 1 ngày)
        start_balances = self._calculate_balances(fy_start - relativedelta(days=1), target_move, company)
        
        # ===========================================================
        # 5. ĐỊNH NGHĨA MAPPING CHỈ TIÊU THEO TT200
        # ===========================================================
        indicators = self._get_indicator_mapping()
        
        # ===========================================================
        # 6. GHI DỮ LIỆU RA EXCEL
        # ===========================================================
        row = self._write_indicator_data(sheet, formats, indicators, end_balances, start_balances)
        
        # ===========================================================
        # 7. GHI CHỮ KÝ
        # ===========================================================
        self._write_signature(sheet, formats, workbook, row, date_to)
        
        return True
    
    # -----------------------------------------------------------------
    # CÁC HÀM HELPER
    # -----------------------------------------------------------------
    
    def _create_excel_formats(self, workbook):
        """Tạo các định dạng Excel"""
        # Format canh giữa cho mã số
        center_border = workbook.add_format({
            'border': 1, 
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
        
        center_bold_border = workbook.add_format({
            'bold': True, 
            'border': 1, 
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
        
        return {
            'title_bold': workbook.add_format({
                'bold': True, 
                'font_name': 'Times New Roman', 
                'font_size': 14
            }),
            'title_italic': workbook.add_format({
                'italic': True, 
                'align': 'center', 
                'font_name': 'Times New Roman', 
                'font_size': 9
            }),
            'header': workbook.add_format({
                'bold': True, 
                'align': 'center', 
                'valign': 'vcenter',
                'border': 1, 
                'bg_color': '#E9ECEF', 
                'font_name': 'Times New Roman'
            }),
            'header_number': workbook.add_format({
                'bold': True, 
                'align': 'center', 
                'valign': 'vcenter',
                'border': 1, 
                'bg_color': '#E9ECEF', 
                'font_name': 'Times New Roman'
            }),
            'bold_label': workbook.add_format({
                'bold': True, 
                'border': 1, 
                'align': 'left',
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            'bold_center': center_bold_border,
            'bold_number': workbook.add_format({
                'bold': True, 
                'border': 1, 
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0', 
                'font_name': 'Times New Roman'
            }),
            'normal_border': workbook.add_format({
                'border': 1, 
                'align': 'left',
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            'normal_center': center_border,
            'money': workbook.add_format({
                'num_format': '#,##0', 
                'border': 1, 
                'align': 'right',
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            'negative': workbook.add_format({
                'num_format': '#,##0;[Red](#,##0)', 
                'border': 1, 
                'align': 'right',
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            'negative_bold': workbook.add_format({
                'num_format': '#,##0;[Red](#,##0)', 
                'border': 1, 
                'bold': True, 
                'align': 'right',
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            'signature': workbook.add_format({
                'align': 'center', 
                'bold': True, 
                'font_name': 'Times New Roman'
            }),
            'signature_border': workbook.add_format({
                'align': 'center', 
                'border': 1,
                'font_name': 'Times New Roman'
            }),
        }
    
    def _get_fiscal_start(self, date, company):
        """Lấy ngày đầu năm tài chính"""
        fiscal_year = self.env['account.fiscal.year'].search([
            ('company_id', '=', company.id),
            ('date_from', '<=', date),
            ('date_to', '>=', date),
        ], limit=1)
        
        if fiscal_year:
            return fiscal_year.date_from
        else:
            # Mặc định lấy ngày 01/01
            return date.replace(month=1, day=1)
    
    def _calculate_balances(self, as_of_date, target_move, company):
        """
        Tính số dư các tài khoản tại một thời điểm
        Trả về dictionary: {account_code: balance}
        """
        balances = {}
        
        # Domain cơ bản
        domain = [
            ('date', '<=', as_of_date),
            ('company_id', '=', company.id),
        ]
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        
        # Lấy tất cả tài khoản
        accounts = self.env['account.account'].search([
            ('company_ids', 'in', [company.id])
        ])

        _logger.info("="*60)
        _logger.info(f"TÍNH TOÁN SỐ DƯ TẠI NGÀY: {as_of_date}")
        
        # Tính số dư cho từng tài khoản
        for account in accounts:
            lines = self.env['account.move.line'].search(domain + [('account_id', '=', account.id)])
            balance = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))
            
            # QUAN TRỌNG: Ưu tiên dùng code nếu có, nếu không thì dùng tên
            if account.code and account.code.strip():
                key = account.code.strip()
            else:
                # Nếu không có code, dùng tên nhưng loại bỏ dấu ngoặc nhọn
                # Xử lý JSONB field
                if isinstance(account.name, dict):
                    key = account.name.get('en_US', account.name.get('vi_VN', ''))
                else:
                    key = str(account.name).replace('{"en_US": "', '').replace('", "vi_VN": "', ' - ').replace('"}', '')
            
            balances[key] = balance
            
            # Log các tài khoản có số dư để debug
            if balance != 0:
                _logger.info(f"  ✅ TK {key}: {balance:,.0f} (code={account.code})")
                
            # Log các tài khoản quan trọng để debug
            if account.code in ['111', '112', '156', '2141', '331', '334', '421']:
                _logger.info(f"🔍 Account {account.code}: {balance}")
                
            # Log các tài khoản nợ phải trả (dù không có code)
            if balance != 0 and not account.code:
                if 'payable' in key.lower() or 'phải trả' in key.lower() or 'trade' in key.lower():
                    _logger.info(f"🔍 LIABILITY ACCOUNT: {key} = {balance}")
        
        # Xử lý đặc biệt cho tài khoản lưỡng tính (131, 331)
        balances = self._process_receivable_payable_balances(as_of_date, target_move, company, balances)

        _logger.info("="*60)

        return balances
    
    def _process_receivable_payable_balances(self, as_of_date, target_move, company, balances):
        """
        Xử lý tài khoản lưỡng tính (131, 331) theo partner
        """
        # TK 131 - Phải thu khách hàng
        account_131 = self.env['account.account'].search([
            ('code', '=', '131'),
            ('company_ids', 'in', [company.id])
        ], limit=1)
        
        if account_131:
            query = """
                SELECT SUM(debit - credit) as balance
                FROM account_move_line 
                WHERE account_id = %s 
                    AND date <= %s 
                    AND parent_state = 'posted'
                GROUP BY partner_id
            """
            self.env.cr.execute(query, (account_131.id, as_of_date))
            results = self.env.cr.dictfetchall()
            
            debit_balance = sum(r['balance'] for r in results if r['balance'] > 0)
            credit_balance = abs(sum(r['balance'] for r in results if r['balance'] < 0))
            
            balances['131'] = debit_balance
            balances['312_from_131'] = credit_balance
            _logger.info(f"  ✅ TK 131 (xử lý lưỡng tính): Dư Nợ={debit_balance:,.0f}, Dư Có={credit_balance:,.0f}")

        # TK 331 - Phải trả người bán
        account_331 = self.env['account.account'].search([
            ('code', '=', '331'),
            ('company_ids', 'in', [company.id])
        ], limit=1)
        
        if account_331:
            query = """
                SELECT SUM(credit - debit) as balance
                FROM account_move_line 
                WHERE account_id = %s 
                    AND date <= %s 
                    AND parent_state = 'posted'
                GROUP BY partner_id
            """
            self.env.cr.execute(query, (account_331.id, as_of_date))
            results = self.env.cr.dictfetchall()
            
            credit_balance = sum(r['balance'] for r in results if r['balance'] > 0)
            debit_balance = abs(sum(r['balance'] for r in results if r['balance'] < 0))
            
            balances['331'] = credit_balance
            balances['132_from_331'] = debit_balance
            _logger.info(f"  ✅ TK 331 (xử lý lưỡng tính): Dư Có={credit_balance:,.0f}, Dư Nợ={debit_balance:,.0f}")
        
        # THÊM PHẦN NÀY ĐỂ LOG TẤT CẢ TÀI KHOẢN NỢ PHẢI TRẢ
        _logger.info("  🔍 TẤT CẢ TÀI KHOẢN NỢ PHẢI TRẢ TRONG BALANCES:")
        for key, value in balances.items():
            if value != 0 and any(x in key.lower() for x in ['payable', 'phải trả', 'trade', 'tax', 'thuế', 'staff', 'nhân viên']):
                _logger.info(f"    - {key}: {value:,.0f}")
        
        return balances
    
    def _get_indicator_mapping(self):
        """
        Định nghĩa mapping chỉ tiêu theo TT200
        Trả về list các dict để dễ thao tác
        """
        return [
            # A - TÀI SẢN NGẮN HẠN (100)
            {'code': '100', 'name': 'A - TÀI SẢN NGẮN HẠN', 'accounts': None, 'is_total': True, 'is_negative': False, 'children': ['110', '120', '130', '140', '150']},
            
            # I. Tiền (110)
            {'code': '110', 'name': 'I. Tiền và các khoản tương đương tiền', 'accounts': ['111', '112'], 'is_total': True, 'is_negative': False, 'children': ['111', '112']},
            {'code': '111', 'name': '1. Tiền', 'accounts': ['1111', '1112', '1113'], 'is_total': False, 'is_negative': False},
            {'code': '112', 'name': '2. Các khoản tương đương tiền', 'accounts': ['1121', '1122'], 'is_total': False, 'is_negative': False},
            
            # II. Đầu tư tài chính ngắn hạn (120)
            {'code': '120', 'name': 'II. Đầu tư tài chính ngắn hạn', 'accounts': ['121', '122', '123'], 'is_total': True, 'is_negative': False, 'children': ['121', '122', '123']},
            {'code': '121', 'name': '1. Chứng khoán kinh doanh', 'accounts': ['121'], 'is_total': False, 'is_negative': False},
            {'code': '122', 'name': '2. Dự phòng giảm giá chứng khoán kinh doanh (*)', 'accounts': ['2291'], 'is_total': False, 'is_negative': True},
            {'code': '123', 'name': '3. Đầu tư nắm giữ đến ngày đáo hạn', 'accounts': ['1281', '1282', '1283', '1288'], 'is_total': False, 'is_negative': False},
            
            # III. Các khoản phải thu ngắn hạn (130)
            {'code': '130', 'name': 'III. Các khoản phải thu ngắn hạn', 'accounts': ['131', '132', '133', '134', '135', '136', '137', '139'], 'is_total': True, 'is_negative': False, 'children': ['131', '132', '133', '134', '135', '136', '137', '139']},
            {'code': '131', 'name': '1. Phải thu ngắn hạn của khách hàng', 'accounts': ['131'], 'is_total': False, 'is_negative': False},
            {'code': '132', 'name': '2. Trả trước cho người bán ngắn hạn', 'accounts': ['132_from_331'], 'is_total': False, 'is_negative': False},
            {'code': '133', 'name': '3. Phải thu nội bộ ngắn hạn', 'accounts': ['136'], 'is_total': False, 'is_negative': False},
            {'code': '134', 'name': '4. Phải thu theo tiến độ kế hoạch HĐXD', 'accounts': ['337'], 'is_total': False, 'is_negative': False},
            {'code': '135', 'name': '5. Phải thu về cho vay ngắn hạn', 'accounts': ['1283'], 'is_total': False, 'is_negative': False},
            {'code': '136', 'name': '6. Phải thu ngắn hạn khác', 'accounts': ['138', '3388'], 'is_total': False, 'is_negative': False},
            {'code': '137', 'name': '7. Dự phòng phải thu ngắn hạn khó đòi (*)', 'accounts': ['2293'], 'is_total': False, 'is_negative': True},
            {'code': '139', 'name': '8. Tài sản thiếu chờ xử lý', 'accounts': ['1381'], 'is_total': False, 'is_negative': False},
            
            # IV. Hàng tồn kho (140)
            {'code': '140', 'name': 'IV. Hàng tồn kho', 'accounts': ['141', '149'], 'is_total': True, 'is_negative': False, 'children': ['141', '149']},
            {'code': '141', 'name': '1. Hàng tồn kho', 'accounts': ['151', '152', '153', '154', '155', '156', '157'], 'is_total': False, 'is_negative': False},
            {'code': '149', 'name': '2. Dự phòng giảm giá hàng tồn kho (*)', 'accounts': ['2294'], 'is_total': False, 'is_negative': True},
            
            # V. Tài sản ngắn hạn khác (150)
            {'code': '150', 'name': 'V. Tài sản ngắn hạn khác', 'accounts': ['151', '152', '153', '154', '155'], 'is_total': True, 'is_negative': False, 'children': ['151', '152', '153', '154', '155']},
            {'code': '151', 'name': '1. Chi phí trả trước ngắn hạn', 'accounts': ['142', '242'], 'is_total': False, 'is_negative': False},
            {'code': '152', 'name': '2. Thuế GTGT được khấu trừ', 'accounts': ['133'], 'is_total': False, 'is_negative': False},
            {'code': '153', 'name': '3. Thuế và các khoản khác phải thu NN', 'accounts': ['138'], 'is_total': False, 'is_negative': False},
            {'code': '154', 'name': '4. Giao dịch mua bán lại trái phiếu CP', 'accounts': ['171'], 'is_total': False, 'is_negative': False},
            {'code': '155', 'name': '5. Tài sản ngắn hạn khác', 'accounts': ['138'], 'is_total': False, 'is_negative': False},
            
            # B - TÀI SẢN DÀI HẠN (200)
            {'code': '200', 'name': 'B - TÀI SẢN DÀI HẠN', 'accounts': ['210', '220', '230', '240', '250', '260'], 'is_total': True, 'is_negative': False, 'children': ['210', '220', '230', '240', '250', '260']},
            
            # I. Các khoản phải thu dài hạn (210)
            {'code': '210', 'name': 'I. Các khoản phải thu dài hạn', 'accounts': ['211', '212', '213', '214', '215', '216', '219'], 'is_total': True, 'is_negative': False, 'children': ['211', '212', '213', '214', '215', '216', '219']},
            {'code': '211', 'name': '1. Phải thu dài hạn của khách hàng', 'accounts': ['131'], 'is_total': False, 'is_negative': False},
            {'code': '212', 'name': '2. Trả trước cho người bán dài hạn', 'accounts': ['331'], 'is_total': False, 'is_negative': False},
            {'code': '213', 'name': '3. Vốn kinh doanh ở đơn vị trực thuộc', 'accounts': ['136'], 'is_total': False, 'is_negative': False},
            {'code': '214', 'name': '4. Phải thu nội bộ dài hạn', 'accounts': ['1368'], 'is_total': False, 'is_negative': False},
            {'code': '215', 'name': '5. Phải thu về cho vay dài hạn', 'accounts': ['1283'], 'is_total': False, 'is_negative': False},
            {'code': '216', 'name': '6. Phải thu dài hạn khác', 'accounts': ['1388'], 'is_total': False, 'is_negative': False},
            {'code': '219', 'name': '7. Dự phòng phải thu dài hạn khó đòi (*)', 'accounts': ['2293'], 'is_total': False, 'is_negative': True},
            
            # II. Tài sản cố định (220)
            {'code': '220', 'name': 'II. Tài sản cố định', 'accounts': ['221', '222', '223', '224', '225', '226', '227', '228', '229'], 'is_total': True, 'is_negative': False, 'children': ['221', '222', '223', '224', '225', '226', '227', '228', '229']},
            {'code': '221', 'name': '1. Tài sản cố định hữu hình', 'accounts': ['211'], 'is_total': False, 'is_negative': False},
            {'code': '222', 'name': '- Nguyên giá', 'accounts': ['2111'], 'is_total': False, 'is_negative': False},
            {'code': '223', 'name': '- Giá trị hao mòn lũy kế (*)', 'accounts': ['2141'], 'is_total': False, 'is_negative': True},
            {'code': '224', 'name': '2. Tài sản cố định thuê tài chính', 'accounts': ['212'], 'is_total': False, 'is_negative': False},
            {'code': '225', 'name': '- Nguyên giá', 'accounts': ['2121'], 'is_total': False, 'is_negative': False},
            {'code': '226', 'name': '- Giá trị hao mòn lũy kế (*)', 'accounts': ['2142'], 'is_total': False, 'is_negative': True},
            {'code': '227', 'name': '3. Tài sản cố định vô hình', 'accounts': ['213'], 'is_total': False, 'is_negative': False},
            {'code': '228', 'name': '- Nguyên giá', 'accounts': ['2131'], 'is_total': False, 'is_negative': False},
            {'code': '229', 'name': '- Giá trị hao mòn lũy kế (*)', 'accounts': ['2143'], 'is_total': False, 'is_negative': True},
            
            # III. Bất động sản đầu tư (230)
            {'code': '230', 'name': 'III. Bất động sản đầu tư', 'accounts': ['231', '232'], 'is_total': True, 'is_negative': False, 'children': ['231', '232']},
            {'code': '231', 'name': '- Nguyên giá', 'accounts': ['217'], 'is_total': False, 'is_negative': False},
            {'code': '232', 'name': '- Giá trị hao mòn lũy kế (*)', 'accounts': ['2147'], 'is_total': False, 'is_negative': True},
            
            # IV. Tài sản dở dang dài hạn (240)
            {'code': '240', 'name': 'IV. Tài sản dở dang dài hạn', 'accounts': ['241', '242'], 'is_total': True, 'is_negative': False, 'children': ['241', '242']},
            {'code': '241', 'name': '1. Chi phí SXKD dở dang dài hạn', 'accounts': ['154'], 'is_total': False, 'is_negative': False},
            {'code': '242', 'name': '2. Chi phí xây dựng cơ bản dở dang', 'accounts': ['241'], 'is_total': False, 'is_negative': False},
            
            # V. Đầu tư tài chính dài hạn (250)
            {'code': '250', 'name': 'V. Đầu tư tài chính dài hạn', 'accounts': ['251', '252', '253', '254', '255'], 'is_total': True, 'is_negative': False, 'children': ['251', '252', '253', '254', '255']},
            {'code': '251', 'name': '1. Đầu tư vào công ty con', 'accounts': ['221'], 'is_total': False, 'is_negative': False},
            {'code': '252', 'name': '2. Đầu tư vào công ty liên doanh, liên kết', 'accounts': ['222'], 'is_total': False, 'is_negative': False},
            {'code': '253', 'name': '3. Đầu tư góp vốn vào đơn vị khác', 'accounts': ['228'], 'is_total': False, 'is_negative': False},
            {'code': '254', 'name': '4. Dự phòng đầu tư tài chính dài hạn (*)', 'accounts': ['2292'], 'is_total': False, 'is_negative': True},
            {'code': '255', 'name': '5. Đầu tư nắm giữ đến ngày đáo hạn', 'accounts': ['1283'], 'is_total': False, 'is_negative': False},
            
            # VI. Tài sản dài hạn khác (260)
            {'code': '260', 'name': 'VI. Tài sản dài hạn khác', 'accounts': ['261', '262', '263', '268'], 'is_total': True, 'is_negative': False, 'children': ['261', '262', '263', '268']},
            {'code': '261', 'name': '1. Chi phí trả trước dài hạn', 'accounts': ['242'], 'is_total': False, 'is_negative': False},
            {'code': '262', 'name': '2. Tài sản thuế thu nhập hoãn lại', 'accounts': ['243'], 'is_total': False, 'is_negative': False},
            {'code': '263', 'name': '3. Thiết bị, vật tư, phụ tùng thay thế dài hạn', 'accounts': ['153'], 'is_total': False, 'is_negative': False},
            {'code': '268', 'name': '4. Tài sản dài hạn khác', 'accounts': ['248'], 'is_total': False, 'is_negative': False},
            
            # TỔNG CỘNG TÀI SẢN (270)
            {'code': '270', 'name': 'TỔNG CỘNG TÀI SẢN (270 = 100 + 200)', 'accounts': ['100', '200'], 'is_total': True, 'is_negative': False, 'children': ['100', '200']},
            
            # C - NỢ PHẢI TRẢ (300)
            #{'code': '300', 'name': 'C - NỢ PHẢI TRẢ', 'accounts': ['310', '330'], 'is_total': True, 'is_negative': False, 'children': ['310', '330']},
            {'code': '300', 'name': 'C - NỢ PHẢI TRẢ', 'accounts': None, 'is_total': True, 'is_negative': False, 'children': ['310', '330']},
            # I. Nợ ngắn hạn (310)
            {'code': '310', 'name': 'I. Nợ ngắn hạn', 'accounts': ['311', '312', '313', '314', '315', '316', '317', '318', '319', '320', '321', '322', '323', '324'], 'is_total': True, 'is_negative': False, 'children': ['311', '312', '313', '314', '315', '316', '317', '318', '319', '320', '321', '322', '323', '324']},
            {'code': '311', 'name': '1. Phải trả người bán ngắn hạn', 
                'accounts': ['Trade payables - short term'], 'is_total': False, 'is_negative': True},
            {'code': '312', 'name': '2. Người mua trả tiền trước ngắn hạn', 'accounts': ['312_from_131'], 'is_total': False, 'is_negative': False},
            {'code': '313', 'name': '3. Thuế và các khoản phải nộp NN', 
                'accounts': ['Corporate income tax - short term'], 'is_total': False, 'is_negative': True},
            {'code': '314', 'name': '4. Phải trả người lao động', 
                'accounts': ['Payables to staff - short term'], 'is_total': False, 'is_negative': True},
            {'code': '315', 'name': '5. Chi phí phải trả ngắn hạn', 'accounts': ['335'], 'is_total': False, 'is_negative': False},
            {'code': '316', 'name': '6. Phải trả nội bộ ngắn hạn', 'accounts': ['336'], 'is_total': False, 'is_negative': False},
            {'code': '317', 'name': '7. Phải trả theo tiến độ KHHĐXD', 'accounts': ['337'], 'is_total': False, 'is_negative': False},
            {'code': '318', 'name': '8. Doanh thu chưa thực hiện ngắn hạn', 'accounts': ['3387'], 'is_total': False, 'is_negative': False},
            {'code': '319', 'name': '9. Phải trả ngắn hạn khác', 'accounts': ['338'], 'is_total': False, 'is_negative': False},
            {'code': '320', 'name': '10. Vay và nợ thuê TC ngắn hạn', 'accounts': ['311', '312', '315', '341'], 'is_total': False, 'is_negative': False},
            {'code': '321', 'name': '11. Dự phòng phải trả ngắn hạn', 'accounts': ['352'], 'is_total': False, 'is_negative': False},
            {'code': '322', 'name': '12. Quỹ khen thưởng, phúc lợi', 'accounts': ['353'], 'is_total': False, 'is_negative': False},
            {'code': '323', 'name': '13. Quỹ bình ổn giá', 'accounts': ['357'], 'is_total': False, 'is_negative': False},
            {'code': '324', 'name': '14. Giao dịch mua bán lại trái phiếu CP', 'accounts': ['171'], 'is_total': False, 'is_negative': False},
            
            # II. Nợ dài hạn (330)
            {'code': '330', 'name': 'II. Nợ dài hạn', 'accounts': ['331', '332', '333', '334', '335', '336', '337', '338', '339', '340', '341', '342', '343'], 'is_total': True, 'is_negative': False, 'children': ['331', '332', '333', '334', '335', '336', '337', '338', '339', '340', '341', '342', '343']},
            {'code': '331', 'name': '1. Phải trả người bán dài hạn', 'accounts': ['331'], 'is_total': False, 'is_negative': False},
            {'code': '332', 'name': '2. Người mua trả tiền trước dài hạn', 'accounts': ['131'], 'is_total': False, 'is_negative': False},
            {'code': '333', 'name': '3. Chi phí phải trả dài hạn', 'accounts': ['335'], 'is_total': False, 'is_negative': False},
            {'code': '334', 'name': '4. Phải trả nội bộ về vốn kinh doanh', 'accounts': ['336'], 'is_total': False, 'is_negative': False},
            {'code': '335', 'name': '5. Phải trả nội bộ dài hạn', 'accounts': ['336'], 'is_total': False, 'is_negative': False},
            {'code': '336', 'name': '6. Doanh thu chưa thực hiện dài hạn', 'accounts': ['3387'], 'is_total': False, 'is_negative': False},
            {'code': '337', 'name': '7. Phải trả dài hạn khác', 'accounts': ['338'], 'is_total': False, 'is_negative': False},
            {'code': '338', 'name': '8. Vay và nợ thuê TC dài hạn', 'accounts': ['341'], 'is_total': False, 'is_negative': False},
            {'code': '339', 'name': '9. Trái phiếu chuyển đổi', 'accounts': ['3431'], 'is_total': False, 'is_negative': False},
            {'code': '340', 'name': '10. Cổ phiếu ưu đãi', 'accounts': ['4112'], 'is_total': False, 'is_negative': False},
            {'code': '341', 'name': '11. Thuế thu nhập hoãn lại phải trả', 'accounts': ['347'], 'is_total': False, 'is_negative': False},
            {'code': '342', 'name': '12. Dự phòng phải trả dài hạn', 'accounts': ['352'], 'is_total': False, 'is_negative': False},
            {'code': '343', 'name': '13. Quỹ phát triển KH&CN', 'accounts': ['356'], 'is_total': False, 'is_negative': False},
            
            # D - VỐN CHỦ SỞ HỮU (400)
            {'code': '400', 'name': 'D - VỐN CHỦ SỞ HỮU', 'accounts': ['410', '430'], 'is_total': True, 'is_negative': False, 'children': ['410', '430']},
            
            # I. Vốn chủ sở hữu (410)
            {'code': '410', 'name': 'I. Vốn chủ sở hữu', 'accounts': ['411', '412', '413', '414', '415', '416', '417', '418', '419', '420', '421', '422'], 'is_total': True, 'is_negative': False, 'children': ['411', '412', '413', '414', '415', '416', '417', '418', '419', '420', '421', '422']},
            {'code': '411', 'name': '1. Vốn góp của chủ sở hữu', 'accounts': ['4111'], 'is_total': False, 'is_negative': False},
            {'code': '411a', 'name': '- Cổ phiếu phổ thông có quyền biểu quyết', 'accounts': ['41111'], 'is_total': False, 'is_negative': False},
            {'code': '411b', 'name': '- Cổ phiếu ưu đãi', 'accounts': ['41112'], 'is_total': False, 'is_negative': False},
            {'code': '412', 'name': '2. Thặng dư vốn cổ phần', 'accounts': ['4112'], 'is_total': False, 'is_negative': False},
            {'code': '413', 'name': '3. Quyền chọn chuyển đổi trái phiếu', 'accounts': ['4113'], 'is_total': False, 'is_negative': False},
            {'code': '414', 'name': '4. Vốn khác của chủ sở hữu', 'accounts': ['4118'], 'is_total': False, 'is_negative': False},
            {'code': '415', 'name': '5. Cổ phiếu quỹ (*)', 'accounts': ['4191'], 'is_total': False, 'is_negative': True},
            {'code': '416', 'name': '6. Chênh lệch đánh giá lại tài sản', 'accounts': ['412'], 'is_total': False, 'is_negative': False},
            {'code': '417', 'name': '7. Chênh lệch tỷ giá hối đoái', 'accounts': ['413'], 'is_total': False, 'is_negative': False},
            {'code': '418', 'name': '8. Quỹ đầu tư phát triển', 'accounts': ['414'], 'is_total': False, 'is_negative': False},
            {'code': '419', 'name': '9. Quỹ hỗ trợ sắp xếp doanh nghiệp', 'accounts': ['417'], 'is_total': False, 'is_negative': False},
            {'code': '420', 'name': '10. Quỹ khác thuộc vốn chủ sở hữu', 'accounts': ['418'], 'is_total': False, 'is_negative': False},
            {'code': '421', 'name': '11. Lợi nhuận sau thuế chưa phân phối', 'accounts': ['4211', '4212'], 'is_total': False, 'is_negative': False},
            {'code': '421a', 'name': '- LNST chưa phân phối lũy kế đến cuối kỳ trước', 'accounts': ['4211'], 'is_total': False, 'is_negative': False},
            {'code': '421b', 'name': '- LNST chưa phân phối kỳ này', 'accounts': ['4212'], 'is_total': False, 'is_negative': False},
            {'code': '422', 'name': '12. Nguồn vốn đầu tư XDCB', 'accounts': ['441'], 'is_total': False, 'is_negative': False},
            
            # II. Nguồn kinh phí và quỹ khác (430)
            {'code': '430', 'name': 'II. Nguồn kinh phí và quỹ khác', 'accounts': ['431', '432'], 'is_total': True, 'is_negative': False, 'children': ['431', '432']},
            {'code': '431', 'name': '1. Nguồn kinh phí', 'accounts': ['461'], 'is_total': False, 'is_negative': False},
            {'code': '432', 'name': '2. Nguồn kinh phí đã hình thành TSCĐ', 'accounts': ['466'], 'is_total': False, 'is_negative': False},
            
            # TỔNG CỘNG NGUỒN VỐN (440)
            {'code': '440', 'name': 'TỔNG CỘNG NGUỒN VỐN (440 = 300 + 400)', 'accounts': ['300', '400'], 'is_total': True, 'is_negative': False, 'children': ['300', '400']},
        ]
    
    def _write_report_header(self, sheet, formats, workbook, company, date_from, date_to):
        """Ghi tiêu đề báo cáo"""
        # Dòng 0: Tên công ty
        company_name = company.name.upper() if company and company.name else ''
        sheet.merge_range(0, 0, 0, 2, company_name, formats['title_bold'])
        
        # Mẫu số bên phải
        sheet.merge_range(0, 3, 0, 4, 'Mẫu số B01-DN', 
                         workbook.add_format({'bold': True, 'align': 'right', 'font_name': 'Times New Roman'}))
        
        # Dòng 1: Địa chỉ
        street = company.street or ''
        sheet.merge_range(1, 0, 1, 2, street, formats['normal_border'])
        
        # Thông tư
        sheet.merge_range(1, 3, 1, 4, '(Ban hành theo Thông tư số 200/2014/TT-BTC)', formats['title_italic'])
        
        # Dòng 3: Tên báo cáo
        sheet.merge_range(3, 0, 3, 4, 'BẢNG CÂN ĐỐI KẾ TOÁN', 
                         workbook.add_format({'bold': True, 'align': 'center', 'size': 16, 'font_name': 'Times New Roman'}))
        
        # Dòng 4: Khoảng thời gian
        date_from_str = date_from.strftime("%d/%m/%Y") if date_from else ''
        date_to_str = date_to.strftime("%d/%m/%Y") if date_to else ''
        sheet.merge_range(4, 0, 4, 4, f'Từ ngày {date_from_str} đến ngày {date_to_str}', 
                         workbook.add_format({'italic': True, 'align': 'center', 'font_name': 'Times New Roman'}))
        
        # Dòng 6: Header bảng
        headers = ['TÀI SẢN', 'Mã số', 'Thuyết minh', 'Số cuối năm', 'Số đầu năm']
        for col, title in enumerate(headers):
            sheet.write(6, col, title, formats['header'])
        
        # Dòng 7: Ghi chú cột
        notes = ['1', '2', '3', '4', '5']
        for col, note in enumerate(notes):
            sheet.write(7, col, note, formats['header_number'])
        
        return 8  # Dòng bắt đầu ghi dữ liệu
    
    def _write_indicator_data(self, sheet, formats, indicators, end_balances, start_balances):
        """Ghi dữ liệu các chỉ tiêu"""
        row = 8
        
        # Tạo dictionary để lưu giá trị tính toán
        values = {}
        
        # DEBUG: Xem tất cả keys trong end_balances
        _logger.info("="*60)
        _logger.info("DEBUG: TẤT CẢ KEYS TRONG END_BALANCES:")
        for key, value in end_balances.items():
            if value != 0:
                _logger.info(f"  {key}: {value:,.0f}")
        _logger.info("="*60)
        
        # Bước 1: Tính giá trị cho từng chỉ tiêu
        for indicator in indicators:
            code = indicator['code']
            accounts = indicator['accounts']
            is_total = indicator['is_total']
            is_negative = indicator['is_negative']
            
            # Tính số liệu
            if is_total and 'children' in indicator:
                # Chỉ tiêu tổng hợp: sẽ tính sau
                values[code] = {'end': 0, 'start': 0}
            elif accounts:
                # Chỉ tiêu đơn: lấy từ balances
                if isinstance(accounts, list):
                    end_value = 0
                    start_value = 0
                    for acc in accounts:
                        # Thử tìm key chính xác trong end_balances
                        found = False
                        for end_key in end_balances.keys():
                            if acc.lower() in end_key.lower() or end_key.lower() in acc.lower():
                                end_value += end_balances[end_key]
                                found = True
                                _logger.info(f"  ✅ Tìm thấy {code} từ key '{end_key}' cho account '{acc}'")
                                break
                        if not found:
                            end_value += end_balances.get(acc, 0)
                        
                        for start_key in start_balances.keys():
                            if acc.lower() in start_key.lower() or start_key.lower() in acc.lower():
                                start_value += start_balances[start_key]
                                break
                        if not found:
                            start_value += start_balances.get(acc, 0)
                else:
                    end_value = end_balances.get(accounts, 0)
                    start_value = start_balances.get(accounts, 0)
                
                # Đảo dấu nếu là chỉ tiêu âm
                if is_negative:
                    end_value = -abs(end_value) if end_value != 0 else 0
                    start_value = -abs(start_value) if start_value != 0 else 0
                
                values[code] = {'end': end_value, 'start': start_value}
            else:
                values[code] = {'end': 0, 'start': 0}
        
        # Bước 2: Tính các chỉ tiêu tổng hợp theo children
        for indicator in indicators:
            code = indicator['code']
            if indicator.get('is_total') and 'children' in indicator:
                end_total = 0
                start_total = 0
                for child_code in indicator['children']:
                    if child_code in values:
                        end_total += values[child_code]['end']
                        start_total += values[child_code]['start']
                values[code] = {'end': end_total, 'start': start_total}
        
        # Bước 3: BỔ SUNG CÁC CHỈ TIÊU ĐẶC BIỆT (311, 313, 314, 421)
        # Phải trả người bán (311) - từ TK 331 hoặc 3311
        found_311 = False
        if '331' in end_balances:
            values['311'] = {'end': -abs(end_balances['331']), 'start': 0}
            _logger.info(f"🔹 Gán 311 từ TK 331: {values['311']['end']:,.0f}")
            found_311 = True
        elif '3311' in end_balances:
            values['311'] = {'end': -abs(end_balances['3311']), 'start': 0}
            _logger.info(f"🔹 Gán 311 từ TK 3311: {values['311']['end']:,.0f}")
            found_311 = True
        
        if not found_311:
            # Tìm trong end_balances bằng tên
            for key, value in end_balances.items():
                if 'trade payables' in key.lower() or 'phải trả người bán' in key.lower():
                    values['311'] = {'end': -abs(value), 'start': 0}
                    _logger.info(f"🔹 Gán 311 từ key '{key}': {value:,.0f}")
                    found_311 = True
                    break
        
        
        # Thuế (313) - từ TK 33341
        found_313 = False
        if '33341' in end_balances:
            values['313'] = {'end': -abs(end_balances['33341']), 'start': 0}
            _logger.info(f"🔹 Gán 313 từ TK 33341: {values['313']['end']:,.0f}")
            found_313 = True
        
        if not found_313:
            # Tìm các TK thuế khác
            for key, value in end_balances.items():
                if key.startswith('333') or 'corporate income tax' in key.lower() or 'thuế thu nhập' in key.lower():
                    values['313'] = {'end': -abs(value), 'start': 0}
                    _logger.info(f"🔹 Gán 313 từ key '{key}': {value:,.0f}")
                    found_313 = True
                    break
        
        # Phải trả người lao động (314) - từ TK 334 hoặc 3341
        found_314 = False
        if '334' in end_balances:
            values['314'] = {'end': -abs(end_balances['334']), 'start': 0}
            _logger.info(f"🔹 Gán 314 từ TK 334: {values['314']['end']:,.0f}")
            found_314 = True
        elif '3341' in end_balances:
            values['314'] = {'end': -abs(end_balances['3341']), 'start': 0}
            _logger.info(f"🔹 Gán 314 từ TK 3341: {values['314']['end']:,.0f}")
            found_314 = True
        
        if not found_314:
            # Tìm trong end_balances bằng tên
            for key, value in end_balances.items():
                if 'payables to staff' in key.lower() or 'phải trả công nhân' in key.lower():
                    values['314'] = {'end': -abs(value), 'start': 0}
                    _logger.info(f"🔹 Gán 314 từ key '{key}': {value:,.0f}")
                    found_314 = True
                    break
        
        # Lợi nhuận sau thuế (421) - tính từ các tài khoản doanh thu, chi phí
        doanh_thu = 0
        for key, value in end_balances.items():
            if 'revenue' in key.lower() or 'doanh thu' in key.lower():
                doanh_thu += value
        
        gia_von = 0
        for key, value in end_balances.items():
            if 'costs of goods sold' in key.lower() or 'giá vốn' in key.lower():
                gia_von += value
        
        cp_ban_hang = 0
        for key, value in end_balances.items():
            if 'employees costs' in key.lower() or 'chi phí nhân viên' in key.lower():
                cp_ban_hang += value
        
        cp_qldn = 0
        dt_tai_chinh = 0
        for key, value in end_balances.items():
            if 'financial income' in key.lower() or 'doanh thu tài chính' in key.lower():
                dt_tai_chinh += value
        
        cp_tai_chinh = 0
        for key, value in end_balances.items():
            if 'financial expenses' in key.lower() or 'chi phí tài chính' in key.lower():
                cp_tai_chinh += value
        
        tn_khac = 0
        for key, value in end_balances.items():
            if 'other income' in key.lower() or 'thu nhập khác' in key.lower():
                tn_khac += value
        
        cp_khac = 0
        for key, value in end_balances.items():
            if 'other expenses' in key.lower() or 'chi phí khác' in key.lower():
                cp_khac += value
        
        thue_tndn = 0
        for key, value in end_balances.items():
            if 'corporate income tax expenses' in key.lower() or 'chi phí thuế' in key.lower():
                thue_tndn += value
        
        loi_nhuan = doanh_thu - gia_von - cp_ban_hang - cp_qldn + dt_tai_chinh - cp_tai_chinh + tn_khac - cp_khac - thue_tndn
        values['421'] = {'end': loi_nhuan, 'start': 0}
        _logger.info(f"🔹 Tính 421: doanh_thu={doanh_thu:,.0f}, gia_von={gia_von:,.0f}, cp_ban_hang={cp_ban_hang:,.0f}, dt_tai_chinh={dt_tai_chinh:,.0f}, cp_tai_chinh={cp_tai_chinh:,.0f}, tn_khac={tn_khac:,.0f}, cp_khac={cp_khac:,.0f}, thue_tndn={thue_tndn:,.0f} => {loi_nhuan:,.0f}")
        
        # Đảm bảo các chỉ tiêu 311, 313, 314 tồn tại
        if '311' not in values:
            values['311'] = {'end': 0, 'start': 0}
        if '313' not in values:
            values['313'] = {'end': 0, 'start': 0}
        if '314' not in values:
            values['314'] = {'end': 0, 'start': 0}
        
        # Bước 4: Tính lại các chỉ tiêu tổng hợp sau khi đã bổ sung
        # Tính tổng nợ ngắn hạn (310)
        if '310' in values:
            children_310 = ['311', '312', '313', '314', '315', '316', '317', '318', '319', '320', '321', '322', '323', '324']
            total_end = 0
            total_start = 0
            for child in children_310:
                if child in values:
                    total_end += values[child]['end']
                    total_start += values[child]['start']
            values['310']['end'] = total_end
            values['310']['start'] = total_start
        
        # Tính tổng vốn chủ sở hữu (410)
        if '410' in values:
            children_410 = ['411', '412', '413', '414', '415', '416', '417', '418', '419', '420', '421', '422']
            total_end = 0
            total_start = 0
            for child in children_410:
                if child in values:
                    total_end += values[child]['end']
                    total_start += values[child]['start']
            values['410']['end'] = total_end
            values['410']['start'] = total_start
        
        # Tính tổng nợ phải trả (300)
        if '300' in values and '310' in values and '330' in values:
            values['300']['end'] = values['310']['end'] + values['330']['end']
            values['300']['start'] = values['310']['start'] + values['330']['start']
        
        # Tính tổng vốn chủ sở hữu (400)
        if '400' in values and '410' in values and '430' in values:
            values['400']['end'] = values['410']['end'] + values['430']['end']
            values['400']['start'] = values['410']['start'] + values['430']['start']
        
        # Tính tổng nguồn vốn (440)
        if '440' in values and '300' in values and '400' in values:
            values['440']['end'] = values['300']['end'] + values['400']['end']
            values['440']['start'] = values['300']['start'] + values['400']['start']
        
        # Tính tổng tài sản ngắn hạn (100)
        if '100' in values and '110' in values and '120' in values and '130' in values and '140' in values and '150' in values:
            values['100']['end'] = values['110']['end'] + values['120']['end'] + values['130']['end'] + values['140']['end'] + values['150']['end']
            values['100']['start'] = values['110']['start'] + values['120']['start'] + values['130']['start'] + values['140']['start'] + values['150']['start']
        
        # Tính tổng tài sản dài hạn (200)
        if '200' in values and '210' in values and '220' in values and '230' in values and '240' in values and '250' in values and '260' in values:
            values['200']['end'] = values['210']['end'] + values['220']['end'] + values['230']['end'] + values['240']['end'] + values['250']['end'] + values['260']['end']
            values['200']['start'] = values['210']['start'] + values['220']['start'] + values['230']['start'] + values['240']['start'] + values['250']['start'] + values['260']['start']
        
        # Tính tổng tài sản (270)
        if '270' in values and '100' in values and '200' in values:
            values['270']['end'] = values['100']['end'] + values['200']['end']
            values['270']['start'] = values['100']['start'] + values['200']['start']
        
        # Bước 5: LOG DEBUG
        _logger.info("🔍 FINAL VALUES:")
        for code in ['100', '110', '111', '112', '140', '141', '200', '220', '223', '270', '300', '310', '311', '313', '314', '400', '410', '421', '440']:
            if code in values:
                _logger.info(f"  {code}: end={values[code]['end']:,.0f}, start={values[code]['start']:,.0f}")
            else:
                _logger.info(f"  {code}: NOT FOUND")
        
        # Bước 6: Ghi ra Excel (giữ nguyên phần này)
        for indicator in indicators:
            code = indicator['code']
            name = indicator['name']
            is_total = indicator['is_total']
            is_negative = indicator['is_negative']
            
            end_value = values.get(code, {'end': 0})['end']
            start_value = values.get(code, {'start': 0})['start']
            
            # Chọn format cho cột A (Tên chỉ tiêu)
            if is_total:
                label_format = formats['bold_label']
            else:
                label_format = formats['normal_border']
            
            # Chọn format cho cột B (Mã số) - luôn canh giữa
            if is_total:
                code_format = formats['bold_center']
            else:
                code_format = formats['normal_center']
            
            # Chọn format cho cột D, E (Số tiền)
            if is_total:
                end_format = formats['negative_bold'] if is_negative and end_value < 0 else formats['bold_number']
                start_format = formats['negative_bold'] if is_negative and start_value < 0 else formats['bold_number']
            else:
                end_format = formats['negative'] if is_negative and end_value < 0 else formats['money']
                start_format = formats['negative'] if is_negative and start_value < 0 else formats['money']
            
            # Ghi dữ liệu
            sheet.write(row, 0, name, label_format)
            sheet.write(row, 1, code, code_format)
            sheet.write(row, 2, '', code_format)  # Cột thuyết minh để trống
            
            # Số cuối năm - chỉ ghi nếu có giá trị hoặc là chỉ tiêu tổng
            if end_value != 0 or code in ['100', '200', '270', '300', '400', '440']:
                sheet.write(row, 3, end_value, end_format)
            else:
                sheet.write(row, 3, '', code_format)
            
            # Số đầu năm - chỉ ghi nếu có giá trị hoặc là chỉ tiêu tổng
            if start_value != 0 or code in ['100', '200', '270', '300', '400', '440']:
                sheet.write(row, 4, start_value, start_format)
            else:
                sheet.write(row, 4, '', code_format)
            
            row += 1
            
            # Thêm dòng trống giữa các phần
            if code in ['112', '123', '139', '149', '155', '219', '229', '232', '242', '255', '268', '270', '324', '343', '422', '432', '440']:
                # Dòng trống vẫn có border
                sheet.write(row, 0, '', formats['normal_border'])
                sheet.write(row, 1, '', formats['normal_center'])
                sheet.write(row, 2, '', formats['normal_center'])
                sheet.write(row, 3, '', formats['normal_center'])
                sheet.write(row, 4, '', formats['normal_center'])
                row += 1
        
        return row
    def _write_signature(self, sheet, formats, workbook, row, date_to):
        """Ghi phần chữ ký"""
        row += 2
        
        # Dòng ngày tháng - canh phải
        date_str = date_to.strftime("Ngày %d tháng %m năm %Y") if date_to else "Ngày ... tháng ... năm 20.."
        sheet.merge_range(row, 3, row, 4, date_str, 
                         workbook.add_format({'align': 'right', 'font_name': 'Times New Roman', 'italic': True}))
        row += 2  # Thêm khoảng trống
        
        # Tạo format không border cho phần chữ ký
        no_border = workbook.add_format({'font_name': 'Times New Roman', 'align': 'center'})
        no_border_bold = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'align': 'center'})
        
        # Dòng 1: Tiêu đề chức danh - KHÔNG ĐÓNG KHUNG
        sheet.write(row, 0, 'Người lập biểu', no_border_bold)
        sheet.write(row, 1, '', no_border)
        sheet.write(row, 2, 'Kế toán trưởng', no_border_bold)
        sheet.write(row, 3, '', no_border)
        sheet.write(row, 4, 'Giám đốc', no_border_bold)
        row += 1
        
        # Dòng 2: Hướng dẫn ký - KHÔNG ĐÓNG KHUNG
        sheet.write(row, 0, '(Ký, họ tên)', no_border)
        sheet.write(row, 1, '', no_border)
        sheet.write(row, 2, '(Ký, họ tên)', no_border)
        sheet.write(row, 3, '', no_border)
        sheet.write(row, 4, '(Ký, họ tên, đóng dấu)', no_border)