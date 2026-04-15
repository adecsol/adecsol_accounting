# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import xlsxwriter
import base64
from io import BytesIO
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class AccountBalanceSheetExcel(models.TransientModel):
    _name = 'adecsol.balance.sheet.export'
    _description = 'Xuất Bảng cân đối kế toán TT 200'

    # THÊM: Các trường dữ liệu cần thiết cho wizard
    date_from = fields.Date(
        string='Từ ngày',
        required=True,
        default=fields.Date.today,
        help="Ngày bắt đầu lấy số dư"
    )
    
    date_to = fields.Date(
        string='Đến ngày',
        required=True,
        default=fields.Date.today,
        help="Ngày kết thúc lấy số dư"
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True
    )
    
    target_move = fields.Selection([
        ('posted', 'All Posted Entries'),
        ('all', 'All Entries')
    ], string='Target Moves', default='posted', required=True)
    
    enable_comparison = fields.Boolean(string='Enable Comparison', default=False)
    display_debit_credit = fields.Boolean(string='Display Debit/Credit Columns', default=False)

    def action_export_xlsx(self):
        """
        Hàm chính xuất file Excel bảng cân đối kế toán
        GIỮ NGUYÊN logic code của bạn, chỉ THÊM phần xử lý hoàn chỉnh
        """
        self.ensure_one()
        
        # THÊM: Validate dữ liệu
        if self.date_from > self.date_to:
            raise UserError("Ngày bắt đầu không thể lớn hơn ngày kết thúc!")
        
        # GIỮ NGUYÊN: Định nghĩa Mapping của bạn - nhưng MỞ RỘNG thêm
        mapping = {
            # TÀI SẢN NGẮN HẠN
            '110': {'name': 'Tiền và các khoản tương đương tiền', 'accounts': ['111', '112', '113'], 'type': 'net_debit'},
            '111': {'name': '1. Tiền', 'accounts': ['111'], 'type': 'net_debit'},  # THÊM
            '112': {'name': '2. Các khoản tương đương tiền', 'accounts': ['112'], 'type': 'net_debit'},  # THÊM
            
            # Các khoản phải thu
            '130': {'name': 'III. Các khoản phải thu ngắn hạn', 'type': 'total'},  # THÊM chỉ tiêu tổng
            '131': {'name': '1. Phải thu ngắn hạn của khách hàng', 'accounts': ['131'], 'type': 'gross_debit'},
            '132': {'name': '2. Trả trước cho người bán ngắn hạn', 'accounts': ['331'], 'type': 'gross_debit'},  # THÊM
            '137': {'name': '7. Dự phòng phải thu ngắn hạn khó đòi', 'accounts': ['2293'], 'type': 'negative_credit'},  # THÊM
            
            # Hàng tồn kho
            '140': {'name': 'IV. Hàng tồn kho', 'type': 'total'},  # THÊM
            '141': {'name': '1. Hàng tồn kho', 'accounts': ['151', '152', '153', '154', '155', '156'], 'type': 'net_debit'},  # THÊM
            '149': {'name': '2. Dự phòng giảm giá hàng tồn kho', 'accounts': ['2294'], 'type': 'negative_credit'},  # THÊM
            
            # TÀI SẢN DÀI HẠN
            '200': {'name': 'B - TÀI SẢN DÀI HẠN', 'type': 'total'},  # THÊM
            '221': {'name': '1. Nguyên giá TSCĐ hữu hình', 'accounts': ['211'], 'type': 'net_debit'},
            '222': {'name': '2. Giá trị hao mòn lũy kế', 'accounts': ['2141', '2142', '2143'], 'type': 'negative_credit'},  # SỬA: chi tiết hơn
            '223': {'name': '3. Nguyên giá TSCĐ thuê tài chính', 'accounts': ['212'], 'type': 'net_debit'},  # THÊM
            
            # NỢ PHẢI TRẢ
            '300': {'name': 'C - NỢ PHẢI TRẢ', 'type': 'total'},  # THÊM
            '311': {'name': '1. Phải trả người bán ngắn hạn', 'accounts': ['331'], 'type': 'gross_credit'},
            '312': {'name': '2. Người mua trả tiền trước ngắn hạn', 'accounts': ['131'], 'type': 'gross_credit_side'},
            '313': {'name': '3. Thuế và các khoản phải nộp Nhà nước', 'accounts': ['333'], 'type': 'net_credit'},  # THÊM
            
            # VỐN CHỦ SỞ HỮU
            '400': {'name': 'D - VỐN CHỦ SỞ HỮU', 'type': 'total'},  # THÊM
            '411': {'name': '1. Vốn góp của chủ sở hữu', 'accounts': ['4111'], 'type': 'net_credit'},  # THÊM
            '421': {'name': '8. Lợi nhuận sau thuế chưa phân phối', 'accounts': ['4211', '4212'], 'type': 'net_credit'},  # THÊM
        }

        # THÊM: Danh sách chỉ tiêu theo đúng thứ tự TT200
        ordered_codes = [
            '110', '111', '112',  # Tiền
            '120',  # Đầu tư tài chính ngắn hạn (thêm sau)
            '130', '131', '132', '137',  # Phải thu
            '140', '141', '149',  # Hàng tồn kho
            '150',  # Tài sản ngắn hạn khác
            '200',  # Tài sản dài hạn
            '220', '221', '222', '223',  # Tài sản cố định
            '300',  # Nợ phải trả
            '310', '311', '312', '313',  # Nợ ngắn hạn
            '400',  # Vốn chủ sở hữu
            '410', '411', '412', '421',  # Vốn chủ sở hữu chi tiết
        ]

        try:
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output)
            sheet = workbook.add_worksheet('Bảng Cân Đối Kế Toán')
            
            # THÊM: Tạo định dạng đẹp hơn
            formats = self._create_excel_formats(workbook)
            
            # THÊM: Ghi tiêu đề báo cáo (tên công ty, địa chỉ, ngày tháng)
            self._write_report_header(sheet, formats, workbook)
            
            # GIỮ NGUYÊN: Viết tiêu đề bảng (nhưng format đẹp hơn)
            sheet.write(6, 0, 'CHỈ TIÊU', formats['header'])
            sheet.write(6, 1, 'MÃ SỐ', formats['header'])
            sheet.write(6, 2, 'THUYẾT MINH', formats['header'])  # THÊM cột thuyết minh
            sheet.write(6, 3, 'SỐ CUỐI KỲ', formats['header'])
            
            # THÊM: Đặt độ rộng cột
            sheet.set_column('A:A', 50)  # Tên chỉ tiêu
            sheet.set_column('B:B', 10)  # Mã số
            sheet.set_column('C:C', 12)  # Thuyết minh
            sheet.set_column('D:D', 18)  # Số tiền

            row = 7
            totals = {}  # THÊM: Để lưu tổng các nhóm
            
            # SỬA: Duyệt theo thứ tự đã định
            for code in ordered_codes:
                if code not in mapping:
                    continue
                    
                info = mapping[code]
                
                # THÊM: Xử lý chỉ tiêu tổng
                if info.get('type') == 'total':
                    # Tính tổng từ các chỉ tiêu con
                    children = [c for c in ordered_codes if c.startswith(code[:2]) and c != code]
                    amount = sum(totals.get(c, 0) for c in children)
                    totals[code] = amount
                else:
                    # GIỮ NGUYÊN: Logic tính của bạn - nhưng gọi qua hàm riêng để clean hơn
                    amount = self._calculate_amount(info)
                    totals[code] = amount
                
                # Xác định format (in đậm cho chỉ tiêu tổng)
                is_bold = code.endswith('0') or code in ['100', '200', '300', '400']
                label_format = formats['bold_label'] if is_bold else formats['normal_border']
                num_format = formats['bold_number'] if is_bold else formats['money']
                
                # Ghi vào Excel
                sheet.write(row, 0, info['name'], label_format)
                sheet.write(row, 1, code, label_format)
                sheet.write(row, 2, '', label_format)  # Cột thuyết minh để trống
                sheet.write(row, 3, amount, num_format)
                
                row += 1
            
            # THÊM: Ghi phần ký tên
            self._write_signature(sheet, formats, workbook, row)
            
            workbook.close()
            
            # THÊM: Trả về file download
            return self._create_attachment(output)
            
        except Exception as e:
            _logger.error(f"Lỗi xuất báo cáo: {str(e)}")
            raise UserError(f"Có lỗi xảy ra khi xuất báo cáo: {str(e)}")

    # THÊM: Các hàm helper để code gọn gàng hơn

    def _create_excel_formats(self, workbook):
        """Tạo các định dạng Excel"""
        return {
            'title': workbook.add_format({
                'bold': True, 
                'font_name': 'Times New Roman', 
                'font_size': 14
            }),
            'subtitle': workbook.add_format({
                'bold': True, 
                'align': 'center', 
                'font_name': 'Times New Roman'
            }),
            'header': workbook.add_format({
                'bold': True, 
                'align': 'center', 
                'border': 1, 
                'bg_color': '#E9ECEF', 
                'font_name': 'Times New Roman'
            }),
            'bold_label': workbook.add_format({
                'bold': True, 
                'border': 1, 
                'font_name': 'Times New Roman'
            }),
            'bold_number': workbook.add_format({
                'bold': True, 
                'border': 1, 
                'num_format': '#,##0', 
                'font_name': 'Times New Roman'
            }),
            'normal_border': workbook.add_format({
                'border': 1, 
                'font_name': 'Times New Roman'
            }),
            'money': workbook.add_format({
                'num_format': '#,##0', 
                'border': 1, 
                'font_name': 'Times New Roman'
            }),
            'negative': workbook.add_format({
                'num_format': '#,##0;[Red](#,##0)', 
                'border': 1, 
                'font_name': 'Times New Roman'
            }),
            'italic': workbook.add_format({
                'italic': True, 
                'align': 'center', 
                'font_name': 'Times New Roman', 
                'size': 9
            }),
        }

    def _write_report_header(self, sheet, formats, workbook):
        """Ghi tiêu đề báo cáo"""
        # Dòng 0: Tên công ty
        company_name = self.company_id.name.upper() if self.company_id else ''
        sheet.write(0, 0, company_name, formats['title'])
        
        # Dòng 1: Địa chỉ
        street = self.company_id.street or ''
        sheet.write(1, 0, street, formats['normal_border'])
        
        # Mẫu số
        sheet.merge_range(0, 2, 0, 3, 'Mẫu số B 01 - DN', formats['subtitle'])
        sheet.merge_range(1, 2, 1, 3, '(Ban hành theo TT số 200/2014/TT-BTC)', formats['italic'])
        
        # Tên báo cáo
        sheet.merge_range(3, 0, 3, 3, 'BẢNG CÂN ĐỐI KẾ TOÁN', 
                         workbook.add_format({'bold': True, 'align': 'center', 'size': 16, 'font_name': 'Times New Roman'}))
        
        # Ngày
        date_str = self.date_to.strftime("%d/%m/%Y") if self.date_to else ''
        sheet.merge_range(4, 0, 4, 3, f'Tại ngày {date_str}', 
                         workbook.add_format({'italic': True, 'align': 'center', 'font_name': 'Times New Roman'}))

    def _calculate_amount(self, info):
        """
        GIỮ NGUYÊN logic tính của bạn nhưng mở rộng để xử lý nhiều trường hợp hơn
        """
        amount = 0
        
        try:
            # GIỮ NGUYÊN code của bạn cho các type đã có
            if info['type'] == 'net_debit':
                # Tổng Nợ - Tổng Có của nhóm tài khoản
                domain = [('move_id.state', '=', 'posted')]
                if self.target_move == 'posted':
                    domain = [('move_id.state', '=', 'posted')]
                
                # Tìm tất cả tài khoản con
                accounts = self.env['account.account'].search([
                    ('code', 'in', info['accounts']),
                    ('company_ids', 'in', [self.company_id.id])
                ])
                
                lines = self.env['account.move.line'].search([
                    ('account_id', 'in', accounts.ids),
                    ('date', '<=', self.date_to),
                    ('move_id.state', '=', 'posted')
                ])
                amount = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))

            elif info['type'] == 'gross_debit':
                # GIỮ NGUYÊN: Bóc tách đối tượng - Chỉ lấy những Partner dư Nợ
                account = self.env['account.account'].search([
                    ('code', '=', info['accounts'][0]),
                    ('company_ids', 'in', [self.company_id.id])
                ], limit=1)
                
                if account:
                    self._cr.execute("""
                        SELECT SUM(debit - credit) as balance 
                        FROM account_move_line 
                        WHERE account_id = %s 
                            AND date <= %s 
                            AND parent_state = 'posted'
                        GROUP BY partner_id 
                        HAVING SUM(debit - credit) > 0
                    """, (account.id, self.date_to))
                    results = self._cr.fetchall()
                    amount = sum(r[0] for r in results)

            elif info['type'] == 'gross_credit':
                # THÊM: Xử lý gross_credit (TK 331)
                account = self.env['account.account'].search([
                    ('code', '=', info['accounts'][0]),
                    ('company_ids', 'in', [self.company_id.id])
                ], limit=1)
                
                if account:
                    self._cr.execute("""
                        SELECT SUM(credit - debit) as balance 
                        FROM account_move_line 
                        WHERE account_id = %s 
                            AND date <= %s 
                            AND parent_state = 'posted'
                        GROUP BY partner_id 
                        HAVING SUM(credit - debit) > 0
                    """, (account.id, self.date_to))
                    results = self._cr.fetchall()
                    amount = sum(r[0] for r in results)

            elif info['type'] == 'gross_credit_side':
                # GIỮ NGUYÊN: Lấy những Partner dư Có của TK 131
                account = self.env['account.account'].search([
                    ('code', '=', info['accounts'][0]),
                    ('company_ids', 'in', [self.company_id.id])
                ], limit=1)
                
                if account:
                    self._cr.execute("""
                        SELECT SUM(credit - debit) as balance 
                        FROM account_move_line 
                        WHERE account_id = %s 
                            AND date <= %s 
                            AND parent_state = 'posted'
                        GROUP BY partner_id 
                        HAVING SUM(credit - debit) > 0
                    """, (account.id, self.date_to))
                    results = self._cr.fetchall()
                    amount = sum(r[0] for r in results)

            elif info['type'] == 'negative_credit':
                # GIỮ NGUYÊN: Ép số âm cho tài khoản hao mòn
                accounts = self.env['account.account'].search([
                    ('code', '=ilike', info['accounts'][0] + '%'),
                    ('company_ids', 'in', [self.company_id.id])
                ])
                
                lines = self.env['account.move.line'].search([
                    ('account_id', 'in', accounts.ids),
                    ('date', '<=', self.date_to),
                    ('move_id.state', '=', 'posted')
                ])
                amount = (sum(lines.mapped('credit')) - sum(lines.mapped('debit'))) * -1

            elif info['type'] == 'net_credit':
                # THÊM: Cho các tài khoản nguồn vốn
                accounts = self.env['account.account'].search([
                    ('code', 'in', info['accounts']),
                    ('company_ids', 'in', [self.company_id.id])
                ])
                
                lines = self.env['account.move.line'].search([
                    ('account_id', 'in', accounts.ids),
                    ('date', '<=', self.date_to),
                    ('move_id.state', '=', 'posted')
                ])
                amount = sum(lines.mapped('credit')) - sum(lines.mapped('debit'))

        except Exception as e:
            _logger.error(f"Lỗi tính toán cho {info.get('name')}: {str(e)}")
            amount = 0

        return amount

    def _write_signature(self, sheet, formats, workbook, row):
        """Ghi phần ký tên"""
        row += 2
        signature_format = workbook.add_format({
            'align': 'center', 
            'bold': True, 
            'font_name': 'Times New Roman'
        })
        
        sheet.write(row, 0, 'Người lập biểu', signature_format)
        sheet.write(row, 1, '', formats['normal_border'])
        sheet.write(row, 2, 'Kế toán trưởng', signature_format)
        sheet.write(row, 3, 'Giám đốc', signature_format)

    def _create_attachment(self, output):
        """Tạo file đính kèm và trả về action download"""
        filename = f'Bang_Can_Doi_Ke_Toan_{self.date_to.strftime("%Y%m%d")}.xlsx'
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'store_fname': filename,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Trả về URL để download
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }