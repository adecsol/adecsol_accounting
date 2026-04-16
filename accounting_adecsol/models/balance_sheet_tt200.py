# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
import xlsxwriter
import base64
from io import BytesIO
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class AccountBalanceSheetExcel(models.TransientModel):
    _name = 'adecsol.balance.sheet.export'
    _description = 'Export balance sheet (TT200)'

    date_from = fields.Date(
        string=_('From'),
        required=True,
        default=fields.Date.today,
        help=_('Start date for balance calculation')
    )

    date_to = fields.Date(
        string=_('To'),
        required=True,
        default=fields.Date.today,
        help=_('End date for balance calculation')
    )

    company_id = fields.Many2one(
        'res.company',
        string=_('Company'),
        default=lambda self: self.env.company,
        required=True
    )
    
    target_move = fields.Selection(
        [
            ('posted', _('All Posted Entries')),
            ('all', _('All Entries')),
        ],
        string=_('Target Moves'),
        default='posted',
        required=True,
    )

    enable_comparison = fields.Boolean(string=_('Enable Comparison'), default=False)
    display_debit_credit = fields.Boolean(string=_('Display Debit/Credit Columns'), default=False)

    def action_export_xlsx(self):
        """Export balance sheet Excel (TT200)."""
        self.ensure_one()
        _ = self.env._

        if self.date_from > self.date_to:
            raise UserError(_("Start date cannot be after end date."))

        mapping = {
            '110': {'name': _('Cash and cash equivalents'), 'accounts': ['111', '112', '113'], 'type': 'net_debit'},
            '111': {'name': _('1. Cash'), 'accounts': ['111'], 'type': 'net_debit'},
            '112': {'name': _('2. Cash equivalents'), 'accounts': ['112'], 'type': 'net_debit'},
            '130': {'name': _('III. Short-term receivables'), 'type': 'total'},
            '131': {'name': _('1. Short-term trade receivables from customers'), 'accounts': ['131'], 'type': 'gross_debit'},
            '132': {'name': _('2. Prepayments to suppliers (short-term)'), 'accounts': ['331'], 'type': 'gross_debit'},
            '137': {'name': _('7. Provision for short-term doubtful receivables'), 'accounts': ['2293'], 'type': 'negative_credit'},
            '140': {'name': _('IV. Inventories'), 'type': 'total'},
            '141': {'name': _('1. Inventories'), 'accounts': ['151', '152', '153', '154', '155', '156'], 'type': 'net_debit'},
            '149': {'name': _('2. Provision for decline in value of inventories'), 'accounts': ['2294'], 'type': 'negative_credit'},
            '200': {'name': _('B - LONG-TERM ASSETS'), 'type': 'total'},
            '221': {'name': _('1. Tangible fixed assets (cost)'), 'accounts': ['211'], 'type': 'net_debit'},
            '222': {'name': _('2. Accumulated depreciation'), 'accounts': ['2141', '2142', '2143'], 'type': 'negative_credit'},
            '223': {'name': _('3. Finance leased fixed assets (cost)'), 'accounts': ['212'], 'type': 'net_debit'},
            '300': {'name': _('C - LIABILITIES'), 'type': 'total'},
            '311': {'name': _('1. Short-term trade payables'), 'accounts': ['331'], 'type': 'gross_credit'},
            '312': {'name': _('2. Short-term advances from customers'), 'accounts': ['131'], 'type': 'gross_credit_side'},
            '313': {'name': _('3. Taxes and payables to the State'), 'accounts': ['333'], 'type': 'net_credit'},
            '400': {'name': _('D - EQUITY'), 'type': 'total'},
            '411': {'name': _('1. Owner contributed capital'), 'accounts': ['4111'], 'type': 'net_credit'},
            '421': {'name': _('8. Retained earnings'), 'accounts': ['4211', '4212'], 'type': 'net_credit'},
        }

        ordered_codes = [
            '110', '111', '112',
            '120',
            '130', '131', '132', '137',
            '140', '141', '149',
            '150',
            '200',
            '220', '221', '222', '223',
            '300',
            '310', '311', '312', '313',
            '400',
            '410', '411', '412', '421',
        ]

        try:
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output)
            sheet = workbook.add_worksheet(_('Balance sheet'))

            formats = self._create_excel_formats(workbook)

            self._write_report_header(sheet, formats, workbook)

            sheet.write(6, 0, _('Indicator'), formats['header'])
            sheet.write(6, 1, _('Code'), formats['header'])
            sheet.write(6, 2, _('Notes'), formats['header'])
            sheet.write(6, 3, _('End of period'), formats['header'])

            sheet.set_column('A:A', 50)
            sheet.set_column('B:B', 10)
            sheet.set_column('C:C', 12)
            sheet.set_column('D:D', 18)

            row = 7
            totals = {}

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
            
            self._write_signature(sheet, formats, workbook, row)

            workbook.close()

            return self._create_attachment(output)

        except Exception as e:
            _logger.error("Balance sheet export failed: %s", str(e))
            raise UserError(_("An error occurred while exporting the report: %s") % str(e)) from e

    # THÊM: Các hàm helper để code gọn gàng hơn

    def _create_excel_formats(self, workbook):
        """Build Excel cell formats."""
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
        """Write report title block."""
        _ = self.env._
        company_name = self.company_id.name.upper() if self.company_id else ''
        sheet.write(0, 0, company_name, formats['title'])

        street = self.company_id.street or ''
        sheet.write(1, 0, street, formats['normal_border'])

        sheet.merge_range(0, 2, 0, 3, _('Form B 01 – DN'), formats['subtitle'])
        sheet.merge_range(1, 2, 1, 3, _('(Issued with Circular No. 200/2014/TT-BTC)'), formats['italic'])

        sheet.merge_range(3, 0, 3, 3, _('BALANCE SHEET'),
                         workbook.add_format({'bold': True, 'align': 'center', 'size': 16, 'font_name': 'Times New Roman'}))

        date_str = self.date_to.strftime("%d/%m/%Y") if self.date_to else ''
        sheet.merge_range(4, 0, 4, 3, _('As of %s') % date_str,
                         workbook.add_format({'italic': True, 'align': 'center', 'font_name': 'Times New Roman'}))

    def _calculate_amount(self, info):
        """
        GIỮ NGUYÊN logic tính của bạn nhưng mở rộng để xử lý nhiều trường hợp hơn
        """
        amount = 0
        
        try:
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
            _logger.error("Amount calculation failed for %s: %s", info.get('name'), str(e))
            amount = 0

        return amount

    def _write_signature(self, sheet, formats, workbook, row):
        """Write signature block."""
        _ = self.env._
        row += 2
        signature_format = workbook.add_format({
            'align': 'center',
            'bold': True,
            'font_name': 'Times New Roman'
        })

        sheet.write(row, 0, _('Prepared by'), signature_format)
        sheet.write(row, 1, '', formats['normal_border'])
        sheet.write(row, 2, _('Chief accountant'), signature_format)
        sheet.write(row, 3, _('Director'), signature_format)

    def _create_attachment(self, output):
        """Create attachment and return download action."""
        filename = 'Balance_sheet_%s.xlsx' % self.date_to.strftime("%Y%m%d")
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'store_fname': filename,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }