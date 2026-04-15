# -*- coding: utf-8 -*-
from odoo import models
import datetime

class TrialBalanceVnXlsx(models.AbstractModel):
    _name = 'report.accounting_adecsol.trial_balance_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizards):
        wizard = wizards[0] if wizards else None
        if not wizard: return

        # Lấy các tham số từ popup
        show_hierarchy = getattr(wizard, 'show_hierarchy', True)
        
        # BƯỚC 1: TÍNH TOÁN TẤT CẢ DỮ LIỆU
        all_lines = self._calculate_all_data(wizard)
        
        # BƯỚC 2: LỌC THEO POPUP
        filtered_lines = self._filter_by_popup(all_lines, wizard)

        sheet = workbook.add_worksheet('Bảng CĐ Phát Sinh')
        font_name = 'Times New Roman'
        
        # --- ĐỊNH DẠNG CƠ BẢN ---
        bold_center = workbook.add_format({'font_name': font_name, 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#F2F2F2'})
        
        # ĐỊNH DẠNG CHO SỐ
        money_normal = workbook.add_format({'font_name': font_name, 'num_format': '#,##0;[Red](#,##0);"-"', 'border': 1})
        money_bold = workbook.add_format({'font_name': font_name, 'num_format': '#,##0;[Red](#,##0);"-"', 'border': 1, 'bold': True})
        money_italic = workbook.add_format({'font_name': font_name, 'num_format': '#,##0;[Red](#,##0);"-"', 'border': 1, 'italic': True})
        
        # ĐỊNH DẠNG CHO CHỮ
        txt_normal = workbook.add_format({'font_name': font_name, 'border': 1})
        txt_bold = workbook.add_format({'font_name': font_name, 'border': 1, 'bold': True})
        txt_italic = workbook.add_format({'font_name': font_name, 'border': 1, 'italic': True})

        sheet.set_column('A:A', 12)
        sheet.set_column('B:B', 45)
        sheet.set_column('C:H', 17)

        # --- HEADER ---
        sheet.write(0, 0, wizard.company_id.name.upper(), workbook.add_format({'font_name': font_name, 'bold': True}))
        sheet.merge_range(0, 5, 0, 7, 'Mẫu số S06-DN', workbook.add_format({'font_name': font_name, 'bold': True, 'align': 'center'}))
        sheet.merge_range(1, 5, 1, 7, '(Ban hành theo Thông tư số 200/2014/TT-BTC)', workbook.add_format({'font_name': font_name, 'italic': True, 'align': 'center', 'font_size': 10}))
        sheet.merge_range(3, 0, 3, 7, 'BẢNG CÂN ĐỐI SỐ PHÁT SINH', workbook.add_format({'font_name': font_name, 'bold': True, 'font_size': 14, 'align': 'center'}))
        sheet.merge_range(4, 0, 4, 7, f'Từ ngày {wizard.date_from.strftime("%d/%m/%Y")} đến ngày {wizard.date_to.strftime("%d/%m/%Y")}', 
                          workbook.add_format({'font_name': font_name, 'italic': True, 'align': 'center'}))

        row = 7
        sheet.merge_range(row, 0, row + 1, 0, 'Số hiệu TK', bold_center)
        sheet.merge_range(row, 1, row + 1, 1, 'Tên tài khoản', bold_center)
        sheet.merge_range(row, 2, row, 3, 'Số dư đầu kỳ', bold_center)
        sheet.merge_range(row, 4, row, 5, 'Số phát sinh trong kỳ', bold_center)
        sheet.merge_range(row, 6, row, 7, 'Số dư cuối kỳ', bold_center)
        for i, h in enumerate(['Nợ', 'Có', 'Nợ', 'Có', 'Nợ', 'Có']):
            sheet.write(row + 1, i + 2, h, bold_center)

        row += 2
        totals = [0.0] * 6  # [init_debit, init_credit, debit, credit, end_debit, end_credit]
        
        # --- ĐỔ DỮ LIỆU ĐÃ LỌC ---
        for line in filtered_lines:
            # Thụt đầu dòng
            indent = '    ' * line['level']
            display_name = indent + line['name']
            
            # XÁC ĐỊNH ĐỊNH DẠNG DỰA VÀO CẤP
            code_len = len(line['code'])
            
            if code_len == 3:  # Cấp 1: IN ĐẬM
                txt_format = txt_bold
                money_format = money_bold
            elif code_len <= 5:  # Cấp 2 (4-5 số): IN THƯỜNG
                txt_format = txt_normal
                money_format = money_normal
            else:  # Cấp 3+ (≥6 số): IN NGHIÊNG
                txt_format = txt_italic
                money_format = money_italic

            sheet.write(row, 0, line['code'], workbook.add_format({'font_name': font_name, 'border': 1, 'align': 'center', 'bold': code_len == 3}))
            sheet.write(row, 1, display_name, txt_format)

            vals = [line['initial_debit'], line['initial_credit'], line['debit'], line['credit'], line['ending_debit'], line['ending_credit']]
            for i, val in enumerate(vals):
                sheet.write(row, i + 2, val, money_format)
                
                # QUY TẮC TÍNH TỔNG:
                if show_hierarchy:
                    # Chế độ nhiều cấp: chỉ cộng tài khoản lá
                    if not line['is_parent']:
                        totals[i] += val
                else:
                    # Chế độ 1 cấp: cộng tất cả
                    totals[i] += val
            row += 1

        # --- TỔNG CỘNG ---
        sheet.merge_range(row, 0, row, 1, 'TỔNG CỘNG', bold_center)
        for i, t in enumerate(totals):
            sheet.write(row, i + 2, t, money_bold)

        row += 2
        
        # --- PHẦN CHỮ KÝ ---
        today = datetime.date.today()
        
        sign_title = workbook.add_format({
            'font_name': font_name, 
            'bold': True, 
            'align': 'center',
            'valign': 'vcenter',
        })
        
        sign_text = workbook.add_format({
            'font_name': font_name, 
            'align': 'center',
            'valign': 'vcenter',
            'italic': True,
            'font_size': 11
        })
        
        sheet.merge_range(row, 4, row, 7, f"Ngày {today.day} tháng {today.month} năm {today.year}", 
                         workbook.add_format({'font_name': font_name, 'italic': True, 'align': 'center'}))
        row += 2
        
        sheet.write(row, 0, 'Người lập biểu', sign_title)
        sheet.write(row, 2, 'Kế toán trưởng', sign_title)
        sheet.write(row, 5, 'Giám đốc', sign_title)
        row += 1
        
        sheet.write(row, 0, '(Ký, họ tên)', sign_text)
        sheet.write(row, 2, '(Ký, họ tên)', sign_text)
        sheet.write(row, 5, '(Ký, họ tên, đóng dấu)', sign_text)
        
        return True

    def _calculate_all_data(self, wizard):
        """Tính toán TẤT CẢ dữ liệu"""
        company_id = wizard.company_id.id
        accounts = self.env['account.account'].search([
            ('company_ids', 'in', [company_id])
        ]).sorted(key=lambda a: a.code)

        # Bước 1: Lấy dữ liệu gốc
        raw_data = {}
        for account in accounts:
            init_data = self.env['account.move.line']._read_group([
                ('account_id', '=', account.id),
                ('date', '<', wizard.date_from),
                ('parent_state', '=', 'posted'),
                ('company_id', '=', company_id)
            ], [], ['balance:sum'])
            initial_balance = init_data[0][0] or 0.0

            period_data = self.env['account.move.line']._read_group([
                ('account_id', '=', account.id),
                ('date', '>=', wizard.date_from),
                ('date', '<=', wizard.date_to),
                ('parent_state', '=', 'posted'),
                ('company_id', '=', company_id)
            ], [], ['debit:sum', 'credit:sum'])
            debit = period_data[0][0] or 0.0
            credit = period_data[0][1] or 0.0

            raw_data[account.code] = {
                'name': account.name,
                'initial_balance': initial_balance,
                'debit': debit,
                'credit': credit,
            }

        # Bước 2: Xác định quan hệ cha-con
        parent_child = {}
        child_parent = {}
        
        for code in raw_data:
            parent_child[code] = []
            
        for code in raw_data:
            if len(code) > 3:
                parent_code = code[:-1]
                while parent_code and parent_code not in raw_data:
                    parent_code = parent_code[:-1]
                if parent_code and parent_code in raw_data:
                    parent_child[parent_code].append(code)
                    child_parent[code] = parent_code

        # Bước 3: Tính tổng hợp cho tài khoản cha
        sorted_codes = sorted(raw_data.keys(), key=len, reverse=True)
        consolidated = {code: raw_data[code].copy() for code in raw_data}
        
        for code in sorted_codes:
            if code in child_parent:
                parent = child_parent[code]
                consolidated[parent]['initial_balance'] += consolidated[code]['initial_balance']
                consolidated[parent]['debit'] += consolidated[code]['debit']
                consolidated[parent]['credit'] += consolidated[code]['credit']

        # Bước 4: Xây dựng cây phân cấp
        tree_structure = []
        root_codes = []
        for code in raw_data.keys():
            if len(code) == 3 or code not in child_parent:
                root_codes.append(code)
        root_codes.sort()
        
        def add_to_tree(code, level):
            if code not in raw_data:
                return
            tree_structure.append((code, level))
            children = sorted(parent_child.get(code, []))
            for child in children:
                add_to_tree(child, level + 1)
        
        for code in root_codes:
            add_to_tree(code, 0)

        # Bước 5: Tạo kết quả
        result = []
        for code, level in tree_structure:
            data = consolidated[code]
            ending_bal = data['initial_balance'] + data['debit'] - data['credit']
            
            result.append({
                'code': code,
                'name': raw_data[code]['name'],
                'initial_balance': data['initial_balance'],
                'initial_debit': data['initial_balance'] if data['initial_balance'] > 0 else 0.0,
                'initial_credit': abs(data['initial_balance']) if data['initial_balance'] < 0 else 0.0,
                'debit': data['debit'],
                'credit': data['credit'],
                'ending_balance': ending_bal,
                'ending_debit': ending_bal if ending_bal > 0 else 0.0,
                'ending_credit': abs(ending_bal) if ending_bal < 0 else 0.0,
                'is_parent': bool(parent_child[code]),
                'level': level,
                'code_len': len(code)
            })
        
        return result

    def _filter_by_popup(self, all_lines, wizard):
        """Lọc dữ liệu theo lựa chọn trên Popup"""
        filtered = []
        
        hide_zero = getattr(wizard, 'hide_account_at_0', False)
        show_hierarchy = getattr(wizard, 'show_hierarchy', True)
        limit_hierarchy = getattr(wizard, 'limit_hierarchy_level', False)
        hierarchy_level = getattr(wizard, 'show_hierarchy_level', 99)
        hide_parent = getattr(wizard, 'hide_parent_hierarchy_level', False)

        for line in all_lines:
            # Nếu không hiển thị phân cấp, chỉ lấy cấp 0
            if not show_hierarchy and line['level'] != 0:
                continue
            
            # Lọc theo cấp
            if limit_hierarchy and line['level'] + 1 > hierarchy_level:
                continue
            
            # Lọc ẩn tài khoản cha
            if hide_parent and line['is_parent']:
                continue
            
            # Lọc ẩn tài khoản 0
            if hide_zero:
                if (abs(line['initial_balance']) < 0.01 and 
                    line['debit'] < 0.01 and 
                    line['credit'] < 0.01):
                    continue
            
            filtered.append(line)
        
        return filtered