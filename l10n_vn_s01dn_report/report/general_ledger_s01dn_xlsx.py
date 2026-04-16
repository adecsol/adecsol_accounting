# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.tools.misc import format_date
from datetime import datetime
import logging
import os
import stat

_logger = logging.getLogger(__name__)

ACCOUNTS_PER_PAGE = 6   # number of TK (account) column-groups per page/sheet
# Cột cố định: A–J (0..9): … E Diễn giải, F Số tiền PS, G Ghi chú, H–I TK đối ứng, J thứ tự dòng
FIXED_COLS = 10
# Tiêu đề bảng (khớp QWeb / in)
S01DN_TABLE_HEADER_BG = '#FFFFCC'


def _s01dn_scale_amount(val, money_div):
    """Quy đổi số tiền VND theo đơn vị hiển thị (1 / 1000 / 1e6), khớp QWeb JS."""
    if val is None or val == '':
        return ''
    try:
        x = float(val)
    except (TypeError, ValueError):
        return ''
    div = money_div if money_div and money_div > 0 else 1
    if not x:
        return ''
    if div <= 1:
        ri = round(x)
        return '' if ri == 0 else ri
    y = x / div
    return '' if abs(y) < 1e-12 else y


class GeneralLedgerS01dnXlsx(models.AbstractModel):
    """
    Journal Ledger - General Ledger (Form S01-DN)
    Issued under Circular 200/2014/TT-BTC dated 22/12/2014
    """
    _name = 'report.l10n_vn_s01dn_report.general_ledger_s01dn_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'General Ledger S01-DN (Circular 200)'

    # ------------------------------------------------------------------
    #  ENTRY POINT
    # ------------------------------------------------------------------
    def generate_xlsx_report(self, workbook, data, objects):
        wizard = objects[0] if objects else None

        if wizard and (not data or 'wizard_id' not in data):
            wizard._set_default_wizard_values()
            data = wizard._prepare_report_data()

        data = dict(data or {})
        s01dn_report = self.env[
            'report.l10n_vn_s01dn_report.general_ledger_s01dn'
        ]
        data = s01dn_report._merge_s01dn_ui_filters_into_data_domain(data)
        money_div = s01dn_report._s01dn_money_divisor_from_filters(
            data.get('s01dn_ui_filters'),
        )

        company, date_from, date_to, target_move, journal_ids, account_ids = \
            self._parse_params(wizard, data)

        _logger.info(
            "S01-DN: company=%s  %s -> %s  target=%s",
            company.name, date_from, date_to, target_move,
        )

        # Cùng pipeline QWeb (general_ledger_s01dn) để khớp màn hình; cột phát sinh
        # lấy từ detail_rows['amount'] (đồng bộ HTML).
        # Bộ lọc đã gộp vào domain trong _get_report_values (truy vấn DB), không lọc dict sau.
        res = self._get_s01dn_qweb_values(data, wizard)

        accounts_ordered = res.get('accounts_ordered') or []
        if not accounts_ordered:
            sheet = workbook.add_worksheet('S01-DN')
            sheet.write(0, 0, self.env._('No movements in the selected period.'))
            return True

        opening_balances = res['opening_balances']
        detail_rows = res['detail_rows']
        monthly_summaries = res['monthly_summaries']

        fmt = self._create_formats(workbook, money_div)

        accounts = self.env['account.account'].browse(
            [a['id'] for a in accounts_ordered],
        )
        accounts_list = list(accounts)
        pages = self._split_accounts_into_pages(accounts_list)

        # Tổng Nợ đầu năm (cột số tiền phát sinh) giống nhau mọi sheet
        total_opening_global = sum(
            float((opening_balances.get(acc['id']) or {}).get('debit', 0) or 0)
            for acc in accounts_ordered
        )

        for page_idx, page_accounts in enumerate(pages):
            sheet_name = self.env._('Page %s') % str(page_idx + 1).zfill(2)
            sheet = workbook.add_worksheet(sheet_name)

            row = self._write_header(
                sheet, fmt, workbook,
                company, date_from, date_to, page_accounts, money_div,
            )
            row = self._write_table_header(sheet, fmt, page_accounts, row)
            row = self._write_opening_balance(
                sheet, fmt, page_accounts, opening_balances, row,
                total_opening_global=total_opening_global,
                money_div=money_div,
            )
            row = self._write_detail_rows_from_qweb(
                sheet, fmt, page_accounts, detail_rows, row, money_div=money_div)
            row = self._write_monthly_summaries_from_qweb(
                sheet, fmt, page_accounts, monthly_summaries, row,
                money_div=money_div,
            )

            total_cols = FIXED_COLS + len(page_accounts) * 2
            self._write_signature(
                sheet, fmt, workbook, row, date_from, date_to, total_cols - 1,
            )
            self._set_column_widths(
                sheet, page_accounts, detail_rows, monthly_summaries,
                opening_balances, total_opening_global, money_div,
            )

        return True

    def _get_s01dn_qweb_values(self, data, wizard):
        report = self.env['report.l10n_vn_s01dn_report.general_ledger_s01dn']
        docids = wizard.ids if wizard else []
        return report._get_report_values(docids, data)

    def _write_detail_rows_from_qweb(self, sheet, fmt, page_accounts,
                                     detail_rows, start_row, money_div=1):
        base_url =  False
        #(
        #     self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        # ).rstrip('/')
        row = start_row
        for r in detail_rows:
            t = r.get('type')
            if t == 'month_header':
                for c in range(FIXED_COLS):
                    sheet.write(row, c, '', fmt['total_label'])
                sheet.write(
                    row, 4, r.get('label') or '', fmt['total_label'],
                )
                col = FIXED_COLS
                for _a in page_accounts:
                    sheet.write(row, col, '', fmt['total_label'])
                    sheet.write(row, col + 1, '', fmt['total_label'])
                    col += 2
                row += 1
                continue
            if t != 'line':
                continue

            sheet.write(row, 0, r.get('line_no'), fmt['text_center'])
            sheet.write(row, 1, r.get('date'), fmt['date'])
            move_id = r.get('move_id')
            entry_text = r.get('entry') or ''
            if move_id and base_url:
                url = (
                    f'{base_url}/web#id={move_id}'
                    '&model=account.move&view_type=form'
                )
                sheet.write_url(row, 2, url, fmt['text_center'], entry_text)
            else:
                sheet.write(row, 2, entry_text, fmt['text_center'])
            sheet.write(row, 3, r.get('entry_date'), fmt['date'])
            sheet.write(row, 4, r.get('ref_label') or '', fmt['text'])

            # Cột 1: phát sinh đúng từng dòng TK (Nợ+Có dòng — một bên thường 0), khớp QWeb
            amt = r.get('amount')
            if amt is None:
                amt = float(r.get('debit') or 0) + float(r.get('credit') or 0)
            sheet.write(row, 5, _s01dn_scale_amount(amt, money_div), fmt['money'])
            sheet.write(row, 6, '', fmt['text'])

            sheet.write(row, 7, r.get('cp_debit') or '', fmt['text_center'])
            sheet.write(row, 8, r.get('cp_credit') or '', fmt['text_center'])
            # Cột H: cùng thứ tự dòng với cột A (line_no), không dùng month_line_no
            sheet.write(row, 9, r.get('line_no'), fmt['text_center'])

            col = FIXED_COLS
            aid = r.get('account_id')
            for acc in page_accounts:
                if acc is not None and aid == acc.id:
                    sheet.write(
                        row, col,
                        _s01dn_scale_amount(r.get('debit'), money_div),
                        fmt['money'],
                    )
                    sheet.write(
                        row, col + 1,
                        _s01dn_scale_amount(r.get('credit'), money_div),
                        fmt['money'],
                    )
                else:
                    sheet.write(row, col, '', fmt['empty_border'])
                    sheet.write(row, col + 1, '', fmt['empty_border'])
                col += 2
            row += 1
        return row

    def _write_monthly_summaries_from_qweb(self, sheet, fmt, page_accounts,
                                           monthly_summaries, start_row,
                                           money_div=1):
        row = start_row
        for ms in monthly_summaries:
            self._write_summary_row(
                sheet, fmt, page_accounts, row,
                ms['period_label'],
                ms['period_debit'], ms['period_credit'],
                ms['period_acc_d'], ms['period_acc_c'],
                style='total',
                money_div=money_div,
            )
            row += 1
            self._write_summary_row(
                sheet, fmt, page_accounts, row,
                ms['closing_label'],
                ms['closing_total_d'], ms['closing_total_c'],
                ms['closing_acc_d'], ms['closing_acc_c'],
                style='closing',
                amount_col5=ms['closing_col1'],
                money_div=money_div,
            )
            row += 1
            self._write_summary_row(
                sheet, fmt, page_accounts, row,
                ms['cumul_label'],
                ms['cumul_debit'], ms['cumul_credit'],
                ms['cumul_acc_d'], ms['cumul_acc_c'],
                style='total',
                money_div=money_div,
            )
            row += 2
        return row

    # ------------------------------------------------------------------
    #  SPLIT ACCOUNTS INTO PAGES (min ACCOUNTS_PER_PAGE per page)
    # ------------------------------------------------------------------
    def _split_accounts_into_pages(self, accounts_list):
        if not accounts_list:
            return [[None] * ACCOUNTS_PER_PAGE]

        pages = []
        for i in range(0, len(accounts_list), ACCOUNTS_PER_PAGE):
            chunk = accounts_list[i:i + ACCOUNTS_PER_PAGE]
            while len(chunk) < ACCOUNTS_PER_PAGE:
                chunk.append(None)
            pages.append(chunk)
        return pages

    # ------------------------------------------------------------------
    #  PARSE PARAMETERS (supports OCA _prepare_report_data dict)
    # ------------------------------------------------------------------
    def _parse_params(self, wizard, data):
        if data and data.get('company_id'):
            company = self.env['res.company'].browse(data['company_id'])
        elif wizard and wizard.company_id:
            company = wizard.company_id
        else:
            company = self.env.company

        date_from = (data or {}).get('date_from') or (
            wizard.date_from if wizard else fields.Date.today()
        )
        date_to = (data or {}).get('date_to') or (
            wizard.date_to if wizard else fields.Date.today()
        )

        if isinstance(date_from, str):
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if isinstance(date_to, str):
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

        if data and 'only_posted_moves' in data:
            target_move = 'posted' if data['only_posted_moves'] else 'all'
        elif wizard and hasattr(wizard, 'target_move'):
            target_move = wizard.target_move or 'posted'
        else:
            target_move = 'posted'

        journal_ids = (data or {}).get('journal_ids', [])
        if not journal_ids and wizard:
            if hasattr(wizard, 'account_journal_ids'):
                journal_ids = wizard.account_journal_ids.ids
            elif hasattr(wizard, 'journal_ids') and wizard.journal_ids:
                journal_ids = wizard.journal_ids.ids

        account_ids = (data or {}).get('account_ids', [])
        if not account_ids and wizard and wizard.account_ids:
            account_ids = wizard.account_ids.ids

        return company, date_from, date_to, target_move, journal_ids, account_ids

    # ------------------------------------------------------------------
    #  EXCEL FORMATS
    # ------------------------------------------------------------------
    def _create_formats(self, workbook, money_div=1):
        font = 'Arial'
        num_money = '#,##0'
        return {
            'title': workbook.add_format({
                'bold': True, 'font_name': font, 'font_size': 14,
                'align': 'center', 'valign': 'vcenter',
            }),
            'subtitle': workbook.add_format({
                'bold': True, 'font_name': font, 'font_size': 11,
                'align': 'center', 'valign': 'vcenter',
            }),
            'subtitle_period': workbook.add_format({
                'bold': True, 'italic': True, 'font_name': font,
                'font_size': 11, 'align': 'center', 'valign': 'vcenter',
            }),
            'company': workbook.add_format({
                'bold': True, 'font_name': font, 'font_size': 12,
            }),
            'header': workbook.add_format({
                'bold': True, 'border': 1, 'align': 'center',
                'valign': 'vcenter', 'text_wrap': True,
                'font_name': font, 'font_size': 8,
                'bg_color': S01DN_TABLE_HEADER_BG,
            }),
            'header_number': workbook.add_format({
                'bold': True, 'border': 1, 'align': 'center',
                'valign': 'vcenter',
                'font_name': font, 'font_size': 8,
                'bg_color': S01DN_TABLE_HEADER_BG,
            }),
            'date': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'num_format': 'dd/mm/yyyy', 'align': 'center',
                'valign': 'vcenter',
            }),
            'text': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'text_wrap': True, 'valign': 'vcenter',
            }),
            'text_center': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'align': 'center', 'valign': 'vcenter',
            }),
            'money': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'num_format': num_money, 'align': 'right', 'valign': 'vcenter',
            }),
            'money_bold': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'num_format': num_money, 'align': 'right', 'bold': True,
                'valign': 'vcenter',
            }),
            'money_red': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'num_format': f'{num_money};[Red]-{num_money}',
                'align': 'right',
                'valign': 'vcenter',
            }),
            'total_label': workbook.add_format({
                'border': 1, 'font_name': font,
                'font_size': 8, 'valign': 'vcenter',
            }),
            'total_money': workbook.add_format({
                'border': 1, 'font_name': font,
                'font_size': 8, 'num_format': num_money, 'align': 'right',
                'valign': 'vcenter',
            }),
            'opening_label': workbook.add_format({
                'border': 1,
                'font_name': font, 'font_size': 8, 'valign': 'vcenter',
            }),
            'opening_money': workbook.add_format({
                'border': 1,
                'font_name': font, 'font_size': 8, 'num_format': num_money,
                'align': 'right', 'valign': 'vcenter',
            }),
            'closing_label': workbook.add_format({
                'border': 1, 'font_name': font,
                'font_size': 8, 'valign': 'vcenter',
            }),
            'closing_money': workbook.add_format({
                'border': 1, 'font_name': font,
                'font_size': 8, 'num_format': num_money, 'align': 'right',
                'valign': 'vcenter',
            }),
            'empty_border': workbook.add_format({
                'border': 1, 'font_name': font, 'font_size': 8,
                'valign': 'vcenter',
            }),
            'signature_bold': workbook.add_format({
                'bold': True, 'align': 'center', 'font_name': font,
                'font_size': 11,
            }),
            'signature': workbook.add_format({
                'align': 'center', 'font_name': font, 'italic': True,
                'font_size': 11,
            }),
            'signature_right': workbook.add_format({
                'align': 'right', 'font_name': font, 'italic': True,
                'font_size': 11,
            }),
            'signature_left': workbook.add_format({
                'align': 'left', 'font_name': font,
                'font_size': 8,
            }),
            'right_bold': workbook.add_format({
                'bold': True, 'align': 'right', 'font_name': font,
                'font_size': 14,
            }),
            'italic_right': workbook.add_format({
                'italic': True, 'align': 'right', 'font_name': font,
                'font_size': 11, 'text_wrap': True, 'valign': 'top',
            }),
            'money_unit_line': workbook.add_format({
                'italic': True, 'align': 'right', 'font_name': font,
                'font_size': 10, 'valign': 'vcenter',
            }),
        }

    # ------------------------------------------------------------------
    #  HEADER
    # ------------------------------------------------------------------
    def _write_header(self, sheet, fmt, workbook, company, date_from, date_to,
                      page_accounts=None, money_div=1):
        row = 0
        n_acc = len(page_accounts) if page_accounts else ACCOUNTS_PER_PAGE
        last_col = FIXED_COLS + n_acc * 2 - 1

        company_name = (company.name or '').upper()
        fmt_co_label = workbook.add_format({
            'bold': True, 'font_name': 'Arial', 'font_size': 12,
        })
        fmt_co_val = workbook.add_format({
            'bold': False, 'font_name': 'Arial', 'font_size': 12,
        })
        sheet.merge_range(row, 0, row, 3, '', fmt_co_val)
        sheet.write_rich_string(
            row, 0,
            fmt_co_label, self.env._('Company: '),
            fmt_co_val, company_name,
            fmt_co_val,
        )
        sheet.merge_range(row, 4, row, last_col,
                          self.env._('Form S01-DN'), fmt['right_bold'])
        row += 1

        gl_rep = self.env['report.l10n_vn_s01dn_report.general_ledger_s01dn']
        address_body = gl_rep._s01dn_format_company_address(company) or (
            '………………'
        )
        addr_fmt_bold = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 12,
            'text_wrap': True,
            'valign': 'top',
        })
        addr_fmt_norm = workbook.add_format({
            'bold': False,
            'font_name': 'Arial',
            'font_size': 12,
            'text_wrap': True,
            'valign': 'top',
        })
        sheet.merge_range(row, 0, row, 3, '', addr_fmt_norm)
        sheet.write_rich_string(
            row, 0,
            addr_fmt_bold, self.env._('Address:  '),
            addr_fmt_norm, address_body,
            addr_fmt_norm,
        )
        sheet.merge_range(
            row, 4, row, last_col,
            self.env._(
                '(Issued under Circular No. 200/2014/TT-BTC\n'
                'dated 22/12/2014 by the Ministry of Finance)'
            ),
            fmt['italic_right'],
        )
        # Chiều cao dòng đủ cho địa chỉ xuống dòng (wrap); ~2–4 dòng @ 12pt
        addr_display_len = len('Địa chỉ:  ') + len(address_body)
        addr_lines = max(1, (addr_display_len + 39) // 40)
        sheet.set_row(row, min(18 * addr_lines + 12, 120))
        row += 2

        sheet.merge_range(row, 0, row, last_col,
                          self.env._('JOURNAL – GENERAL LEDGER'), fmt['title'])
        row += 1
        period_text = gl_rep._s01dn_report_period_range_label(
            date_from, date_to,
        )
        sheet.merge_range(
            row, 0, row, last_col,
            period_text,
            fmt['subtitle_period'],
        )
        row += 1
        unit_text = gl_rep._s01dn_display_money_unit_caption(money_div)
        sheet.merge_range(
            row+1, 0, row+1, last_col,
            unit_text,
            fmt['money_unit_line'],
        )
        row += 2
        return row

    # ------------------------------------------------------------------
    #  TABLE HEADER
    # ------------------------------------------------------------------
    def _write_table_header(self, sheet, fmt, page_accounts, start_row):
        row = start_row

        sheet.merge_range(row, 0, row + 1, 0,
                          self.env._('Line\nno.'), fmt['header'])
        sheet.merge_range(row, 1, row + 1, 1,
                          self.env._('Posting date\n(d/m/y)'), fmt['header'])
        sheet.merge_range(row, 2, row, 3, self.env._('Voucher'), fmt['header'])
        sheet.write(row + 1, 2, self.env._('Number'), fmt['header'])
        sheet.write(row + 1, 3, self.env._('Date'), fmt['header'])
        sheet.merge_range(row, 4, row + 1, 4, self.env._('Description'), fmt['header'])
        sheet.merge_range(row, 5, row + 1, 5,
                          self.env._('Transaction\namount'), fmt['header'])
        sheet.merge_range(row, 6, row + 1, 6, self.env._('Note'), fmt['header'])
        sheet.merge_range(row, 7, row, 8,
                          self.env._('Offset account\ncode'), fmt['header'])
        sheet.write(row + 1, 7, self.env._('Debit'), fmt['header'])
        sheet.write(row + 1, 8, self.env._('Credit'), fmt['header'])
        sheet.merge_range(row, 9, row + 1, 9,
                          self.env._('Line\nno.'), fmt['header'])

        col = FIXED_COLS
        for acc in page_accounts:
            if acc is not None:
                code = acc.code or acc.name
                label = self.env._('A/C %s') % code
            else:
                label = self.env._('A/C …')
            sheet.merge_range(row, col, row, col + 1, label, fmt['header'])
            sheet.write(row + 1, col, self.env._('Debit'), fmt['header'])
            sheet.write(row + 1, col + 1, self.env._('Credit'), fmt['header'])
            col += 2

        row += 2
        fixed_labels = ['A', 'B', 'C', 'D', 'E', '1', 'I', 'F', 'G', 'H']
        for c, lbl in enumerate(fixed_labels):
            sheet.write(row, c, lbl, fmt['header_number'])

        col = FIXED_COLS
        idx = 2
        for _acc in page_accounts:
            sheet.write(row, col, str(idx), fmt['header_number'])
            sheet.write(row, col + 1, str(idx + 1), fmt['header_number'])
            col += 2
            idx += 2

        sheet.set_row(start_row, 30)
        sheet.set_row(start_row + 1, 20)

        return row + 1

    # ------------------------------------------------------------------
    #  OPENING BALANCE
    # ------------------------------------------------------------------
    def _write_opening_balance(self, sheet, fmt, page_accounts,
                               opening_balances, row, total_opening_global=None,
                               money_div=1):
        sheet.write(row, 0, '', fmt['opening_label'])
        sheet.write(row, 1, '', fmt['opening_label'])
        sheet.write(row, 2, '', fmt['opening_label'])
        sheet.write(row, 3, '', fmt['opening_label'])
        sheet.write(row, 4, self.env._('- Opening balance (year)'), fmt['opening_label'])

        if total_opening_global is not None:
            total_opening = float(total_opening_global or 0)
        else:
            total_opening = 0.0
            for acc in page_accounts:
                if acc is None:
                    continue
                ob = opening_balances.get(
                    acc.id, {'debit': 0, 'credit': 0, 'balance': 0})
                total_opening += float(ob.get('debit', 0) or 0)

        sheet.write(
            row, 5, _s01dn_scale_amount(total_opening, money_div), fmt['opening_money'],
        )
        sheet.write(row, 6, '', fmt['opening_label'])
        sheet.write(row, 7, '', fmt['opening_label'])
        sheet.write(row, 8, '', fmt['opening_label'])
        sheet.write(row, 9, '', fmt['opening_label'])

        col = FIXED_COLS
        for acc in page_accounts:
            if acc is None:
                sheet.write(row, col, '', fmt['opening_money'])
                sheet.write(row, col + 1, '', fmt['opening_money'])
            else:
                ob = opening_balances.get(
                    acc.id, {'debit': 0, 'credit': 0, 'balance': 0})
                balance = ob['balance']
                if balance > 0:
                    sheet.write(
                        row, col,
                        _s01dn_scale_amount(balance, money_div),
                        fmt['opening_money'],
                    )
                    sheet.write(row, col + 1, '', fmt['opening_money'])
                elif balance < 0:
                    sheet.write(row, col, '', fmt['opening_money'])
                    sheet.write(
                        row, col + 1,
                        _s01dn_scale_amount(abs(balance), money_div),
                        fmt['opening_money'],
                    )
                else:
                    sheet.write(row, col, '', fmt['opening_money'])
                    sheet.write(row, col + 1, '', fmt['opening_money'])
            col += 2

        return row + 1

    def _write_summary_row(self, sheet, fmt, page_accounts, row, label,
                           total_debit, total_credit,
                           acc_debits, acc_credits, style='total',
                           amount_col5=None, money_div=1):
        if style == 'closing':
            lbl_fmt = fmt['closing_label']
            num_fmt = fmt['closing_money']
        else:
            lbl_fmt = fmt['total_label']
            num_fmt = fmt['total_money']

        sheet.write(row, 0, '', lbl_fmt)
        sheet.write(row, 1, '', lbl_fmt)
        sheet.write(row, 2, '', lbl_fmt)
        sheet.write(row, 3, '', lbl_fmt)
        sheet.write(row, 4, label, lbl_fmt)
        col5_raw = amount_col5 if amount_col5 is not None else total_debit
        sheet.write(row, 5, _s01dn_scale_amount(col5_raw, money_div), num_fmt)
        sheet.write(row, 6, '', lbl_fmt)
        sheet.write(row, 7, '', lbl_fmt)
        sheet.write(row, 8, '', lbl_fmt)
        sheet.write(row, 9, '', lbl_fmt)

        col = FIXED_COLS
        for acc in page_accounts:
            if acc is None:
                sheet.write(row, col, '', num_fmt)
                sheet.write(row, col + 1, '', num_fmt)
            else:
                d = acc_debits.get(acc.id, 0)
                c = acc_credits.get(acc.id, 0)
                sheet.write(row, col, _s01dn_scale_amount(d, money_div), num_fmt)
                sheet.write(row, col + 1, _s01dn_scale_amount(c, money_div), num_fmt)
            col += 2

    # ------------------------------------------------------------------
    #  SIGNATURE BLOCK
    # ------------------------------------------------------------------
    def _write_signature(self, sheet, fmt, workbook, row,
                         date_from, date_to, last_col):
        row += 2

        third = last_col // 3
        left_end = third - 1
        mid_start2 = third
        mid_end2 = 2 * third - 1
        right_start = 2 * third
        right_end = last_col

        open_date_str = (
            format_date(self.env, date_from) if date_from else self.env._('…………')
        )
        sheet.merge_range(
            row, 0, row, left_end,
            self.env._(
                '- This ledger has … content pages. '
                'Numbered from Page 01 to Page … at the bottom right of each sheet.'
            ),
            fmt['signature_left'],
        )
        row += 1
        sheet.merge_range(
            row, 0, row, left_end,
            self.env._('- Book opened on: %s') % open_date_str,
            fmt['signature_left'],
        )
        row += 1

        date_str = (
            format_date(self.env, date_to, date_format='long')
            if date_to else self.env._('Day … month … year 20..')
        )
        sheet.merge_range(row, right_start, row, right_end,
                          date_str, fmt['signature_right'])
        row += 2

        sheet.merge_range(row, 0, row, left_end,
                          self.env._('Bookkeeper'), fmt['signature_bold'])
        sheet.merge_range(row, mid_start2, row, mid_end2,
                          self.env._('Chief accountant'), fmt['signature_bold'])
        sheet.merge_range(row, right_start, row, right_end,
                          self.env._('Director'), fmt['signature_bold'])
        row += 1

        sheet.merge_range(row, 0, row, left_end,
                          self.env._('(Signature, full name)'), fmt['signature'])
        sheet.merge_range(row, mid_start2, row, mid_end2,
                          self.env._('(Signature, full name)'), fmt['signature'])
        sheet.merge_range(row, right_start, row, right_end,
                          self.env._('(Signature, full name, stamp)'), fmt['signature'])

    @staticmethod
    def _s01dn_xlsx_money_chars(val, money_div):
        s = _s01dn_scale_amount(val, money_div)
        if s == '' or s is None:
            return 0
        return len(str(s))

    # ------------------------------------------------------------------
    #  COLUMN WIDTHS
    # ------------------------------------------------------------------
    def _set_column_widths(
        self, sheet, page_accounts, detail_rows=None,
        monthly_summaries=None, opening_balances=None,
        total_opening_global=0.0, money_div=1,
    ):
        """Column widths from content; note column matches description width."""
        maxlen_ref = len(self.env._('Description'))
        max_line_no = 3
        max_entry = len(self.env._('Number'))
        max_cp = 6
        max_money = 6

        max_money = max(
            max_money,
            self._s01dn_xlsx_money_chars(total_opening_global, money_div),
        )

        for r in detail_rows or []:
            t = r.get('type')
            if t == 'line':
                ref = r.get('ref_label') or ''
                maxlen_ref = max(maxlen_ref, len(ref))
                ent = r.get('entry') or ''
                max_entry = max(max_entry, len(str(ent)))
                cpd = r.get('cp_debit') or ''
                cpc = r.get('cp_credit') or ''
                max_cp = max(max_cp, len(str(cpd)), len(str(cpc)))
                ln = r.get('line_no') or 0
                try:
                    max_line_no = max(max_line_no, len(str(int(ln))))
                except (TypeError, ValueError):
                    max_line_no = max(max_line_no, len(str(ln)))
                for fld in ('amount', 'debit', 'credit'):
                    max_money = max(
                        max_money, self._s01dn_xlsx_money_chars(r.get(fld), money_div),
                    )
            elif t == 'month_header':
                maxlen_ref = max(maxlen_ref, len(r.get('label') or ''))

        for ms in monthly_summaries or []:
            for k in ('period_label', 'closing_label', 'cumul_label'):
                maxlen_ref = max(maxlen_ref, len(ms.get(k) or ''))
            for fld in ('period_total', 'closing_col1', 'cumul_total'):
                max_money = max(
                    max_money, self._s01dn_xlsx_money_chars(ms.get(fld), money_div),
                )
            for dct in (
                ms.get('period_acc_d'), ms.get('period_acc_c'),
                ms.get('closing_acc_d'), ms.get('closing_acc_c'),
                ms.get('cumul_acc_d'), ms.get('cumul_acc_c'),
            ):
                if not dct:
                    continue
                for v in dct.values():
                    max_money = max(
                        max_money, self._s01dn_xlsx_money_chars(v, money_div),
                    )

        maxlen_ref = max(maxlen_ref, len(self.env._('- Opening balance (year)')))
        for acc in page_accounts or []:
            if acc is None or not opening_balances:
                continue
            ob = opening_balances.get(acc.id, {})
            for fld in ('debit', 'credit', 'balance'):
                max_money = max(
                    max_money,
                    self._s01dn_xlsx_money_chars(ob.get(fld), money_div),
                )

        w_e = min(30, max(5, int(maxlen_ref * 0.92)))
        w_g = w_e
        w_f = min(15, max(5, max_money))
        w_a = min(12, max(5, max_line_no))
        # Cột H (J) cùng line_no với cột A
        w_j = min(10, max(5, max_line_no))
        w_c = min(20, max(5, max_entry))
        w_cp = min(10, max(5, max_cp))

        sheet.set_column('A:A', w_a)
        sheet.set_column('B:B', 10)
        sheet.set_column('C:C', w_c)
        sheet.set_column('D:D', 10)
        sheet.set_column('E:E', w_e)
        sheet.set_column('F:F', w_f)
        sheet.set_column('G:G', w_g)
        sheet.set_column('H:H', w_cp)
        sheet.set_column('I:I', w_cp)
        sheet.set_column('J:J', w_j)

        col = FIXED_COLS
        for acc in page_accounts:
            money_w = w_f
            if acc is not None:
                code = acc.code or acc.name or ''
                hdr = max(money_w, len(self.env._('A/C %s') % code))
            else:
                hdr = money_w
            sheet.set_column(col, col + 1, min(10, max(3, int(hdr))))
            col += 2

    # ------------------------------------------------------------------
    #  OVERRIDE: Set file to read-only after writing
    # ------------------------------------------------------------------
    def create_xlsx_report(self, docids, data):
        result = super().create_xlsx_report(docids, data)
        self._set_readonly_on_temp_files()
        return result

    @staticmethod
    def _set_readonly_on_temp_files():
        import glob
        for fpath in glob.glob('/tmp/*.xlsx'):
            try:
                os.chmod(fpath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                _logger.info("S01-DN: Set read-only on %s", fpath)
            except OSError:
                _logger.warning("S01-DN: Cannot set read-only on %s", fpath)
