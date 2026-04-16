# -*- coding: utf-8 -*-
import calendar
import json
from collections import defaultdict
from datetime import date, datetime as dt

from dateutil.relativedelta import relativedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.osv.expression import AND, OR
from odoo.tools import date_utils
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.tools.misc import format_date
from odoo.tools.translate import _


class GeneralLedgerS01dnReport(models.AbstractModel):
    _name = 'report.l10n_vn_s01dn_report.general_ledger_s01dn'
    _inherit = 'report.account_financial_report.general_ledger'
    _description = 'S01-DN General Ledger Summary (QWeb)'

    @api.model
    def _s01dn_ui_labels(self):
        """Static labels for QWeb toolbar and header (English source → vi_VN.po)."""
        return {
            'filters': _('Filters'),
            'filter_toggle_title': _('Show / hide filters'),
            'period': _('Period'),
            'period_placeholder': _('Choose…'),
            'date_from': _('From'),
            'date_to': _('To'),
            'target_move': _('Journal items'),
            'posted': _('Posted'),
            'all': _('All'),
            'accounts': _('Accounts'),
            'journals': _('Journals'),
            'partners': _('Partners'),
            'all_selected': _('All'),
            'select_all': _('Select all'),
            'select_none': _('Clear'),
            'search_placeholder': _('🔍 Search…'),
            'unit': _('Unit'),
            'unit_tooltip': _('Scale amounts on screen (display only)'),
            'unit_vnd': _('VND'),
            'unit_thousand': _('Thousand VND'),
            'unit_million': _('Million VND'),
            'header_unit': _('Company: '),
            'header_form': _('Form S01-DN'),
            'header_address': _('Address: '),
            'header_circular': _(
                '(Issued under Circular No. 200/2014/TT-BTC\n'
                'dated 22/12/2014 by the Ministry of Finance)'
            ),
            'report_title': _('JOURNAL – GENERAL LEDGER'),
            'open_book_prefix': _('- Book opened on:'),
            'move_entry_title': _('Open entry'),
            'table_line_no': _('Line\nno.'),
            'table_posting_date': _('Posting date\n(d/m/y)'),
            'table_voucher': _('Voucher'),
            'table_number': _('Number'),
            'table_date': _('Date'),
            'table_description': _('Description'),
            'table_amount': _('Transaction\namount'),
            'table_note': _('Note'),
            'table_offset': _('Offset account\ncode'),
            'table_debit': _('Debit'),
            'table_credit': _('Credit'),
            'acct_short': _('A/C'),
            'opening_balance': _('- Opening balance (year)'),
            'sign_bookkeeper': _('Bookkeeper'),
            'sign_chief': _('Chief accountant'),
            'sign_director': _('Director'),
            'sign_name': _('(Signature, full name)'),
            'sign_name_stamp': _('(Signature, full name, stamp)'),
        }

    @api.model
    def _s01dn_css_quoted_string(self, text):
        """JSON double-quoted literal for safe use inside CSS content: …"""
        return json.dumps(text or '', ensure_ascii=False)

    @api.model
    def _s01dn_print_margin_box_css_fragments(self):
        """@page margin box content: translatable strings + page counters (Chrome)."""
        book = (
            'content: '
            + self._s01dn_css_quoted_string(_('- This ledger has '))
            + ' counter(pages, decimal-leading-zero) '
            + self._s01dn_css_quoted_string(
                _(' content page(s), numbered from page 01 to page ')
            )
            + ' counter(pages, decimal-leading-zero) '
            + self._s01dn_css_quoted_string('.')
            + ';'
        )
        pager = (
            'content: '
            + self._s01dn_css_quoted_string(_('Page '))
            + ' counter(page, decimal-leading-zero) '
            + self._s01dn_css_quoted_string(_(' / '))
            + ' counter(pages, decimal-leading-zero);'
        )
        return {
            'bottom_left': Markup(book),
            'bottom_right': Markup(pager),
        }

    @api.model
    def _s01dn_js_i18n_dict(self):
        """Strings used by inline report JavaScript (English source)."""
        return {
            'cont': _(' (cont.)'),
            'summary_journal': _(
                'General journal — columns A–D, E, column 1 (amount), I; '
                'offset columns F, G; per Form S01-DN (Circular 200/2014/TT-BTC).'
            ),
            'ledger_detail_a': _('Details by account — accounts:'),
            'ledger_detail_b': _(
                '; column Description (E), line sequence (H), '
                'Debit/Credit pairs per TT200 column order.'
            ),
            'toc_journal': _('General journal'),
            'per_table': _('(per table)'),
            'acct_prefix': _('A/C'),
            'toc_block_title': _('TOC — header block (Company, S01-DN, period)'),
            'toc_continued': _('TOC (continued)'),
            'toc_heading': _('TOC — title'),
            'toc_heading_cont': _('TOC — title (continued)'),
            'toc_table_head': _('TOC — table header'),
            'toc_list': _('TOC — list by page'),
            'report_header_sim': _(
                'Report header — Company, period, Form S01-DN'
            ),
            'report_header_cont': _('Header (continued)'),
            'signature_block_sim': _(
                'Signatures — bookkeeper, chief accountant, director; book open date'
            ),
            'signature_cont': _('Signatures (continued)'),
            'toc_placeholder_hint': _(
                ' — TOC (height placeholder; matches Description column E).'
            ),
            'toc_placeholder_page': _(
                'Page %s — TOC placeholder (approximate height). '
                'S01-DN content follows each printed sheet.'
            ),
            'anchor_title': _('Go to this line on the ledger (click or Ctrl+click)'),
            'toc_title_upper': _('TABLE OF CONTENTS'),
            'toc_col_desc': _('Description'),
            'toc_col_page': _('Page'),
            'confirm_print': _(
                'This report has %s accounts — about %s '
                'printed pages (page 1: TOC when multiple sheets; page 2: '
                'journal A–I + F–G; then H + up to %s accounts per sheet). '
                'Printing may take time and paper. Export to Excel is often easier.\n\n'
                'Open the print dialog anyway?'
            ),
            'money_vnd': _('Unit: VND'),
            'money_thousand': _('Unit: thousand VND'),
            'money_million': _('Unit: million VND'),
            'all_label': _('All'),
            'none_label': _('None'),
            'none_selected': _('None selected'),
            'accounts_word': _('accounts'),
            'journals_word': _('journals'),
            'partners_word': _('partners'),
        }

    @api.model
    def _s01dn_counterparts_and_move_meta(self, entry_ids):
        """
        TK đối ứng + meta nhật ký/trạng thái CT — dùng search_read gộp thay vì
        browse từng move + line_ids (giảm tải ORM khi nhiều chứng từ).
        """
        if not entry_ids:
            return {}, {}

        Move = self.env['account.move']
        Line = self.env['account.move.line']

        moves_data = Move.search_read(
            [('id', 'in', entry_ids)],
            ['id', 'journal_id', 'state'],
        )
        journal_ids = {
            m['journal_id'][0] for m in moves_data if m.get('journal_id')
        }
        journal_name_map = {}
        if journal_ids:
            journals = self.env['account.journal'].browse(list(journal_ids))
            journal_name_map = {j.id: j.name or '' for j in journals}

        move_meta = {}
        for m in moves_data:
            mid = m['id']
            jid = m['journal_id'][0] if m.get('journal_id') else False
            move_meta[mid] = {
                'journal_name': journal_name_map.get(jid, ''),
                'move_state': m.get('state') or 'draft',
            }

        lines_data = Line.search_read(
            [('move_id', 'in', entry_ids)],
            ['id', 'move_id', 'account_id', 'debit', 'credit'],
            order='move_id, id',
        )
        if not lines_data:
            return {}, move_meta

        acc_ids = {
            l['account_id'][0] for l in lines_data if l.get('account_id')
        }
        code_map = {}
        if acc_ids:
            accounts = self.env['account.account'].browse(list(acc_ids))
            code_map = {a.id: a.code or '' for a in accounts}

        counterparts = {}
        for l in lines_data:
            mid = l['move_id'][0] if l.get('move_id') else False
            aid = l['account_id'][0] if l.get('account_id') else False
            counterparts.setdefault(mid, []).append({
                'id': l['id'],
                'code': code_map.get(aid, ''),
                'debit': l['debit'],
                'credit': l['credit'],
            })
        return counterparts, move_meta

    @api.model
    def _s01dn_cp_side_codes(self, others, use_debit):
        """Mã TK các dòng khác có Nợ (use_debit) hoặc Có — gộp chuỗi, giữ thứ tự."""
        out = []
        key = 'debit' if use_debit else 'credit'
        for o in others:
            if (o.get(key) or 0) and o.get('code') and o['code'] not in out:
                out.append(o['code'])
        return ', '.join(out)

    @api.model
    def _s01dn_allocate_split_amounts(self, total, weights, currency):
        """
        Chia `total` cho từng đối ứng có trọng số `weights`.
        Nếu tổng trọng số khớp total → giữ nguyên từng số; không → phân bổ tỷ lệ, làm tròn theo tiền tệ.
        """
        prec = (currency or self.env.company.currency_id).decimal_places
        if not weights:
            return [currency.round(total)]
        w = [max(0.0, float(x)) for x in weights]
        sum_w = sum(w)
        if float_is_zero(sum_w, precision_digits=prec):
            n = len(w)
            if not n:
                return [currency.round(total)]
            base = currency.round(total / n)
            alloc = [base] * n
            diff = currency.round(total - sum(alloc))
            if alloc:
                alloc[-1] = currency.round(alloc[-1] + diff)
            return [max(0.0, x) for x in alloc]
        if float_compare(total, sum_w, precision_digits=prec) == 0:
            return [currency.round(x) for x in w]
        out = []
        allocated = 0.0
        for i, wi in enumerate(w):
            if i == len(w) - 1:
                alloc = currency.round(total - allocated)
            else:
                alloc = currency.round(total * (wi / sum_w))
                allocated += alloc
            out.append(max(0.0, alloc))
        return out

    @api.model
    def _s01dn_counterpart_row_fragments(self, ml, counterparts_entry, currency):
        """
        Một hoặc nhiều “mảnh” hiển thị cho cùng một account.move.line: nếu có
        hơn một dòng đối ứng cùng phía (Nợ hoặc Có) thì tách dòng, mỗi dòng
        một TK đối ứng và số tiền tương ứng.
        """
        cur = currency or self.env.company.currency_id
        prec = cur.decimal_places
        my_debit = float(ml.get('debit') or 0)
        my_credit = float(ml.get('credit') or 0)
        amount_total = my_debit + my_credit

        entry_id = ml.get('entry_id')
        if not entry_id or entry_id not in counterparts_entry:
            return [{
                'cp_debit': '',
                'cp_credit': '',
                'amount': amount_total,
                'debit': my_debit,
                'credit': my_credit,
            }]

        others = [o for o in counterparts_entry[entry_id] if o['id'] != ml['id']]

        def credit_pairs():
            return [
                (o['code'], float(o['credit'] or 0))
                for o in others
                if o.get('code') and float_compare(
                    o.get('credit') or 0, 0, precision_digits=prec,
                ) > 0
            ]

        def debit_pairs():
            return [
                (o['code'], float(o['debit'] or 0))
                for o in others
                if o.get('code') and float_compare(
                    o.get('debit') or 0, 0, precision_digits=prec,
                ) > 0
            ]

        # Dòng Nợ TK này — đối ứng là các dòng Có
        if my_debit > 0 and float_is_zero(my_credit, precision_digits=prec):
            opp = credit_pairs()
            cp_debit_merged = self._s01dn_cp_side_codes(others, True)
            if len(opp) <= 1:
                cp_c = self._s01dn_cp_side_codes(others, False)
                if len(opp) == 1:
                    cp_c = opp[0][0]
                return [{
                    'cp_debit': cp_debit_merged,
                    'cp_credit': cp_c,
                    'amount': my_debit,
                    'debit': my_debit,
                    'credit': 0.0,
                }]
            weights = [a for _c, a in opp]
            splits = self._s01dn_allocate_split_amounts(my_debit, weights, cur)
            frag = []
            for (code, _w), amt in zip(opp, splits):
                frag.append({
                    'cp_debit': cp_debit_merged,
                    'cp_credit': code,
                    'amount': amt,
                    'debit': amt,
                    'credit': 0.0,
                })
            return frag

        # Dòng Có TK này — đối ứng là các dòng Nợ
        if my_credit > 0 and float_is_zero(my_debit, precision_digits=prec):
            opp = debit_pairs()
            cp_credit_merged = self._s01dn_cp_side_codes(others, False)
            if len(opp) <= 1:
                cp_d = self._s01dn_cp_side_codes(others, True)
                if len(opp) == 1:
                    cp_d = opp[0][0]
                return [{
                    'cp_debit': cp_d,
                    'cp_credit': cp_credit_merged,
                    'amount': my_credit,
                    'debit': 0.0,
                    'credit': my_credit,
                }]
            weights = [a for _c, a in opp]
            splits = self._s01dn_allocate_split_amounts(my_credit, weights, cur)
            frag = []
            for (code, _w), amt in zip(opp, splits):
                frag.append({
                    'cp_debit': code,
                    'cp_credit': cp_credit_merged,
                    'amount': amt,
                    'debit': 0.0,
                    'credit': amt,
                })
            return frag

        # Dòng lưỡng kỳ hoặc 0 — giữ một dòng gộp mã TK như trước
        cp_debit = []
        cp_credit = []
        for o in others:
            code = o.get('code') or ''
            if not code:
                continue
            if (o.get('debit') or 0) and code not in cp_debit:
                cp_debit.append(code)
            if (o.get('credit') or 0) and code not in cp_credit:
                cp_credit.append(code)
        return [{
            'cp_debit': ', '.join(cp_debit),
            'cp_credit': ', '.join(cp_credit),
            'amount': amount_total,
            'debit': my_debit,
            'credit': my_credit,
        }]

    @api.model
    def _s01dn_build_opening_balances(self, data, general_ledger):
        """
        Số dư đầu năm tài chính (đầu kỳ tài chính): pipeline account_financial_report
        với mốc date_from = đầu năm tài chính (fy_start_date), không phải đầu kỳ báo cáo.

        Lấy trực tiếp từ read_group; TK mã \"0\": luôn = 0 (mẫu S01-DN).
        """
        if not general_ledger:
            return {}
        foreign_currency = data.get('foreign_currency')
        year_opening = data.get('fy_start_date') or data['date_from']
        gen_ld_initial = self._get_initial_balance_data(
            data.get('account_ids'),
            data.get('partner_ids') or [],
            data['company_id'],
            year_opening,
            foreign_currency,
            data.get('only_posted_moves'),
            data.get('unaffected_earnings_account'),
            data['fy_start_date'],
            data.get('cost_center_ids') or [],
            data.get('domain'),
            data['grouped_by'],
        )
        opening_balances = {}
        for gl in general_ledger:
            acc_id = gl['id']
            if acc_id in gen_ld_initial:
                init = dict(gen_ld_initial[acc_id]['init_bal'])
            else:
                # Có phát sinh trong kỳ nhưng không có dòng đầu kỳ trong domain → 0
                init = {
                    'debit': 0.0,
                    'credit': 0.0,
                    'balance': 0.0,
                }
                if foreign_currency:
                    init['bal_curr'] = 0.0
            ob = {
                'debit': init['debit'],
                'credit': init['credit'],
                'balance': init['balance'],
            }
            if foreign_currency:
                ob['bal_curr'] = init.get('bal_curr', 0.0)
            code = (gl.get('code') or '').strip()
            if code == '0':
                ob = {'debit': 0.0, 'credit': 0.0, 'balance': 0.0}
                if foreign_currency:
                    ob['bal_curr'] = 0.0
            opening_balances[acc_id] = ob
        return opening_balances

    @api.model
    def _s01dn_fetch_summary_move_lines(self, data, date_from, date_to):
        """
        Dòng phát sinh [date_from, date_to] cùng domain bộ lọc wizard — dùng tính
        lũy kế quý / số dư cuối tháng khi kỳ báo cáo bắt đầu sau đầu năm tài chính.
        """
        Line = self.env['account.move.line']
        account_ids = data.get('account_ids')
        partner_ids = data.get('partner_ids') or []
        company_id = data['company_id']
        only_posted = data.get('only_posted_moves')
        cost_center_ids = data.get('cost_center_ids') or []
        extra_domain = data.get('domain') or []
        domain = self._get_period_domain(
            account_ids,
            partner_ids,
            company_id,
            only_posted,
            date_to,
            date_from,
            cost_center_ids,
        )
        if extra_domain:
            domain = domain + list(extra_domain)
        rows = Line.search_read(
            domain=domain,
            fields=['date', 'debit', 'credit', 'account_id'],
            order='date, id',
        )
        out = []
        for r in rows:
            aid = r['account_id'][0] if r.get('account_id') else False
            if not aid:
                continue
            d = r['date']
            if isinstance(d, str):
                d = date.fromisoformat(d[:10])
            out.append({
                'date': d,
                'debit': r.get('debit') or 0.0,
                'credit': r.get('credit') or 0.0,
                '_account_id': aid,
            })
        return out

    @api.model
    def _s01dn_money_divisor_from_filters(self, filters):
        """Hệ số quy đổi từ snapshot UI (Đồng / Ngàn / Triệu) — khớp Excel & in."""
        if not filters or not isinstance(filters, dict):
            return 1
        raw = filters.get('money_unit')
        if raw is None:
            return 1
        try:
            v = int(str(raw).strip())
        except (ValueError, TypeError):
            return 1
        if v in (1, 1000, 1000000):
            return v
        return 1

    @api.model
    def _s01dn_display_money_unit_caption(self, divisor):
        """Display caption for the selected money unit (matches Excel / screen)."""
        return {
            1: _('Unit: VND'),
            1000: _('Unit: thousand VND'),
            1000000: _('Unit: million VND'),
        }.get(divisor, _('Unit: VND'))

    @api.model
    def _s01dn_coerce_report_date(self, d):
        """date | str | False → date hoặc False."""
        if not d:
            return False
        if isinstance(d, date):
            return d
        if isinstance(d, str):
            try:
                return date.fromisoformat(d[:10])
            except ValueError:
                return fields.Date.from_string(d)
        return d

    @api.model
    def _s01dn_report_period_range_label(self, date_from, date_to):
        """
        Nhãn kỳ báo cáo (QWeb / Excel): rút gọn nếu trùng cả tháng / quý / năm dương lịch.
        Ngược lại: Từ ngày dd-mm-yyyy đến ngày dd-mm-yyyy.
        """
        df = self._s01dn_coerce_report_date(date_from)
        dt = self._s01dn_coerce_report_date(date_to)
        if not df or not dt:
            return _('From date … to date …')
        if df > dt:
            df, dt = dt, df
        if df.year != dt.year:
            return _('From %(df)s to %(dt)s') % {
                'df': df.strftime('%d-%m-%Y'),
                'dt': dt.strftime('%d-%m-%Y'),
            }

        y = df.year
        if df == date(y, 1, 1) and dt == date(y, 12, 31):
            return _('Year %s') % y

        quarters = (
            ((1, 1), (3, 31), 'I'),
            ((4, 1), (6, 30), 'II'),
            ((7, 1), (9, 30), 'III'),
            ((10, 1), (12, 31), 'IV'),
        )
        for (m0, d0), (m1, d1), roman in quarters:
            start = date(y, m0, d0)
            end = date(y, m1, d1)
            if df == start and dt == end:
                return _('Quarter %(roman)s - %(year)s') % {
                    'roman': roman,
                    'year': y,
                }

        if df.day == 1:
            month_last = date(
                y, df.month, calendar.monthrange(y, df.month)[1],
            )
            if dt == month_last:
                return _('Month %(month)s - %(year)s') % {
                    'month': df.month,
                    'year': y,
                }

        return _('From %(df)s to %(dt)s') % {
            'df': df.strftime('%d-%m-%Y'),
            'dt': dt.strftime('%d-%m-%Y'),
        }

    @api.model
    def _s01dn_format_company_address(self, company):
        """
        Địa chỉ công ty hiển thị trên S01-DN: đường/phố (và street2 nếu có),
        thành phố/tỉnh, bang/tỉnh (state). Các phần rỗng bỏ qua.
        """
        if not company:
            return ''
        parts = []
        if company.street:
            parts.append(company.street.strip())
        if company.street2:
            parts.append(company.street2.strip())
        if company.city:
            parts.append(company.city.strip())
        if company.state_id:
            parts.append((company.state_id.name or '').strip())
        return ', '.join(p for p in parts if p)

    @api.model
    def _s01dn_report_download_basename(self, date_from, date_to):
        """Tên file giống export Excel: Nhat_ky_So_Cai_S01_DN_DDMMYYYY_DDMMYYYY."""
        df = self._s01dn_coerce_report_date(date_from)
        dt = self._s01dn_coerce_report_date(date_to)
        dfp = df.strftime('%d%m%Y') if df else ''
        dtp = dt.strftime('%d%m%Y') if dt else ''
        return f'Journal_Ledger_S01_DN_{dfp}_{dtp}'

    @api.model
    def _get_report_values(self, docids, data):
        data = dict(data or {})
        self._ensure_s01dn_seed_account_ids(data)
        # Biên ngày ban đầu từ wizard — lưu trong JSON reload để vẫn siết được khi
        # transient wizard đã bị vacuum (merge ngày không còn phụ thuộc browse wiz).
        Wizard = self.env['general.ledger.report.wizard']
        wiz_bounds = (
            Wizard.browse(data['wizard_id'])
            if data.get('wizard_id')
            else Wizard.browse()
        )
        if wiz_bounds.id:
            if not data.get('s01dn_ui_date_min') and wiz_bounds.date_from:
                data['s01dn_ui_date_min'] = fields.Date.to_string(
                    wiz_bounds.date_from,
                )
            if not data.get('s01dn_ui_date_max') and wiz_bounds.date_to:
                data['s01dn_ui_date_max'] = fields.Date.to_string(
                    wiz_bounds.date_to,
                )
            data.setdefault(
                's01dn_ui_account_code_from_id',
                wiz_bounds.account_code_from.id
                if wiz_bounds.account_code_from
                else False,
            )
            data.setdefault(
                's01dn_ui_account_code_to_id',
                wiz_bounds.account_code_to.id
                if wiz_bounds.account_code_to
                else False,
            )
        else:
            data.setdefault('s01dn_ui_account_code_from_id', False)
            data.setdefault('s01dn_ui_account_code_to_id', False)
        data = self._merge_s01dn_ui_filters_into_data_domain(data)
        res = super()._get_report_values(docids, data)
        general_ledger = res.get('general_ledger', [])

        accounts_ordered = [
            {'id': gl['id'], 'code': gl['code'], 'name': gl['name']}
            for gl in general_ledger
        ]

        opening_balances = self._s01dn_build_opening_balances(
            data, general_ledger,
        )

        all_lines = []
        for gl in general_ledger:
            lines = gl.get('move_lines', [])
            if 'list_grouped' in gl:
                lines = [
                    ml
                    for g in gl['list_grouped']
                    for ml in g.get('move_lines', [])
                ]
            for ml in lines:
                ml['_account_id'] = gl['id']
                all_lines.append(ml)

        all_lines.sort(
            key=lambda ml: (
                ml['date'] if isinstance(ml['date'], date) else date.min,
                ml.get('entry_id') or 0,
                ml['id'],
            )
        )

        entry_ids = list({
            ml['entry_id'] for ml in all_lines if ml.get('entry_id')
        })
        counterparts, move_meta = self._s01dn_counterparts_and_move_meta(
            entry_ids,
        )

        company = self.env['res.company'].browse(data['company_id']) if data.get(
            'company_id',
        ) else self.env.company
        currency = company.currency_id

        line_no = 0
        current_month = None
        month_line_no = 0
        rows = []

        for ml in all_lines:
            ml_date = ml['date']
            if isinstance(ml_date, str):
                ml_date = date.fromisoformat(ml_date)
            ml_month = ml_date.month if ml_date else 0

            if ml_month != current_month:
                current_month = ml_month
                month_line_no = 0
                rows.append({
                    'type': 'month_header',
                    'label': _('- Movements in month %s') % current_month,
                    'month_num': current_month,
                })

            entry_id = ml.get('entry_id')
            meta = move_meta.get(entry_id, {})
            fragments = self._s01dn_counterpart_row_fragments(
                ml, counterparts, currency,
            )

            # Cột "Số tiền phát sinh" / cột TK: theo từng mảnh đối ứng khi tách dòng.
            for frag in fragments:
                line_no += 1
                month_line_no += 1
                rows.append({
                    'type': 'line',
                    'line_no': line_no,
                    'date': ml_date,
                    'entry': ml.get('entry', ''),
                    'move_id': entry_id,
                    'entry_date': ml_date,
                    'ref_label': ml.get('ref_label', ''),
                    'note': (ml.get('name') or '').strip(),
                    'amount': frag['amount'],
                    'cp_debit': frag['cp_debit'],
                    'cp_credit': frag['cp_credit'],
                    'month_line_no': month_line_no,
                    'month_num': ml_month,
                    'account_id': ml['_account_id'],
                    'debit': frag['debit'],
                    'credit': frag['credit'],
                    'journal_name': meta.get('journal_name', ''),
                    'move_state': meta.get('move_state', 'draft'),
                })

        date_from = res.get('date_from')
        date_to = res.get('date_to')
        if isinstance(date_from, str):
            date_from = date.fromisoformat(date_from)
        if isinstance(date_to, str):
            date_to = date.fromisoformat(date_to)

        fy_start_eff = self._s01dn_coerce_report_date(data.get('fy_start_date'))
        if fy_start_eff and date_from and fy_start_eff < date_from:
            summary_lines = self._s01dn_fetch_summary_move_lines(
                data, fy_start_eff, date_to,
            )
        else:
            summary_lines = all_lines

        monthly_summaries = self._compute_monthly_summaries(
            summary_lines, accounts_ordered, opening_balances,
            date_from, date_to, fy_start_eff,
        )

        # Cột phát sinh dòng mở đầu: tổng Nợ đầu năm (không dùng abs(Nợ)+abs(Có))
        total_opening = sum(
            float((opening_balances.get(acc['id']) or {}).get('debit', 0) or 0)
            for acc in accounts_ordered
        )
        opening_per_acc = {}
        for acc in accounts_ordered:
            bal = opening_balances.get(acc['id'], {}).get('balance', 0)
            opening_per_acc[acc['id']] = {
                'debit': bal if bal > 0 else 0,
                'credit': abs(bal) if bal < 0 else 0,
            }

        report_period_range = self._s01dn_report_period_range_label(
            date_from, date_to,
        )
        s01dn_report_document_title = self._s01dn_report_download_basename(
            date_from, date_to,
        )
        money_divisor = self._s01dn_money_divisor_from_filters(
            data.get('s01dn_ui_filters'),
        )

        wiz_doc = self.env['general.ledger.report.wizard'].browse(
            docids[0],
        ) if docids else None
        (
            s01dn_filter_accounts,
            s01dn_filter_journals,
            s01dn_filter_partners,
            _unused_filter_cc,
        ) = self._s01dn_filter_m2m_choices(wiz_doc, company)

        df_eff = res.get('date_from')
        dt_eff = res.get('date_to')

        def _s01dn_footer_open(d):
            if not d:
                return _('…………')
            if isinstance(d, str):
                d = fields.Date.from_string(d)
            return format_date(self.env, d)

        def _s01dn_footer_sign(d):
            if not d:
                return _('Day … month … year 20..')
            if isinstance(d, str):
                d = fields.Date.from_string(d)
            return format_date(self.env, d, date_format='long')

        addr_line = self._s01dn_format_company_address(company)
        date_ranges = self.env['date.range'].search(
            [('company_id', 'in', [False, company.id])]
        ).read(['name', 'date_start', 'date_end'])

        ui_echo = data.get('s01dn_ui_filters')
        if not ui_echo:
            # First load from Wizard: use data dictionary generated by _prepare_report_data
            jrnl_ids = data.get('journal_ids', [])
            jrnl_names = [j.name for j in self.env['account.journal'].browse(jrnl_ids) if j.name] if jrnl_ids else None
            ui_echo = {
                'account_ids': data.get('account_ids') or None,
                'partner_ids': data.get('partner_ids') or None,
                'journal_names': jrnl_names,
                'date_range_id': data.get('date_range_id') or False,
                'target_move': data.get('target_move', 'all'),
            }

        _margin_css = self._s01dn_print_margin_box_css_fragments()
        res.update({
            'env': self.env,
            's01dn_ui': self._s01dn_ui_labels(),
            's01dn_print_margin_bottom_left': _margin_css['bottom_left'],
            's01dn_print_margin_bottom_right': _margin_css['bottom_right'],
            's01dn_js_i18n_json': Markup(
                json.dumps(
                    self._s01dn_js_i18n_dict(),
                    ensure_ascii=False,
                    separators=(',', ':'),
                )
            ),
            'accounts_ordered': accounts_ordered,
            's01dn_n_accounts': len(accounts_ordered),
            's01dn_company_name_upper': (company.name or '').upper(),
            's01dn_company_address': addr_line or _('………………'),
            's01dn_footer_open_date': _s01dn_footer_open(df_eff),
            's01dn_footer_sign_date': _s01dn_footer_sign(dt_eff),
            'opening_balances': opening_balances,
            'opening_per_acc': opening_per_acc,
            'total_opening': total_opening,
            'detail_rows': rows,
            'monthly_summaries': monthly_summaries,
            'report_period_range': report_period_range,
            's01dn_report_document_title': s01dn_report_document_title,
            's01dn_money_unit': money_divisor,
            's01dn_money_unit_select_value': str(money_divisor),
            's01dn_money_unit_label': self._s01dn_display_money_unit_caption(
                money_divisor),
            's01dn_filter_accounts': s01dn_filter_accounts,
            's01dn_filter_journals': s01dn_filter_journals,
            's01dn_filter_partners': s01dn_filter_partners,
            's01dn_date_ranges': date_ranges,
            's01dn_filter_date_from': self._s01dn_format_date_html_input(df_eff),
            's01dn_filter_date_to': self._s01dn_format_date_html_input(dt_eff),
            's01dn_wizard_date_min': self._s01dn_format_date_html_input(
                data.get('s01dn_ui_date_min')
                or (wiz_doc.date_from if wiz_doc else None),
            ),
            's01dn_wizard_date_max': self._s01dn_format_date_html_input(
                data.get('s01dn_ui_date_max')
                or (wiz_doc.date_to if wiz_doc else None),
            ),
            's01dn_echo': ui_echo,
            's01dn_report_reload_json': Markup(
                self._serialize_data_for_report_reload(data)
            ),
            's01dn_tb_target_move': (
                'posted' if data.get('only_posted_moves') else 'all'
            ),
        })
        return res

    @api.model
    def _serialize_data_for_report_reload(self, data):
        """JSON an toàn để reload /report/html/...?options= (tránh escape QWeb)."""

        def convert(o):
            if isinstance(o, date) and not isinstance(o, dt):
                return fields.Date.to_string(o)
            if isinstance(o, dt):
                return fields.Datetime.to_string(o)
            if isinstance(o, dict):
                return {k: convert(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [convert(x) for x in o]
            return o

        return json.dumps(
            convert(dict(data)),
            ensure_ascii=False,
            separators=(',', ':'),
        )

    @api.model
    def _s01dn_filter_m2m_choices(self, wiz_doc, company):
        """
        Danh sách đầy đủ cho filter TK / nhật ký / đối tác trên QWeb dựa vào công ty.
        Không bị giới hạn bởi wiz_doc để user dể dàng thay đổi trên QWeb.
        """
        Account = self.env['account.account']
        Journal = self.env['account.journal']
        if not company:
            company = self.env.company

        acc_rows = Account.search_read(
            [
                ('company_ids', 'in', company.ids),
                ('deprecated', '=', False),
            ],
            ['id', 'code', 'name', 'account_type'],
            order='code',
        )
        filter_accounts = [
            {
                'id': r['id'],
                'code': r['code'] or '',
                'name': r['name'] or '',
                'account_type': r.get('account_type') or '',
            }
            for r in acc_rows
        ]

        j_rows = Journal.search_read(
            [('company_id', '=', company.id)],
            ['name'],
            order='name',
        )
        filter_journal_names = sorted(
            {r['name'] for r in j_rows if r.get('name')},
        )

        self.env.cr.execute("SELECT DISTINCT partner_id FROM account_move_line WHERE partner_id IS NOT NULL AND company_id = %s", (company.id,))
        p_ids = [r[0] for r in self.env.cr.fetchall()]
        pr = self.env['res.partner'].sudo().browse(p_ids).read(['display_name'])
        filter_partners = sorted([{'id': p['id'], 'name': p.get('display_name', '')} for p in pr], key=lambda x: x.get('name', ''))

        cc = self.env['account.analytic.account'].sudo().search([('company_id', 'in', [False, company.id])], limit=500).read(['display_name'])
        filter_cc = sorted([{'id': c['id'], 'name': c.get('display_name', '')} for c in cc], key=lambda x: x.get('name', ''))

        return filter_accounts, filter_journal_names, filter_partners, filter_cc

    @api.model
    def _s01dn_parse_date(self, val):
        if not val:
            return None
        if isinstance(val, date) and not isinstance(val, dt):
            return val
        if isinstance(val, dt):
            return val.date()
        if isinstance(val, str):
            return fields.Date.from_string(val)
        return val

    @api.model
    def _s01dn_format_date_html_input(self, val):
        """Giá trị cho input type=date (YYYY-MM-DD)."""
        d = self._s01dn_parse_date(val)
        if not d:
            return ''
        return fields.Date.to_string(d)

    @api.model
    def _ensure_s01dn_seed_account_ids(self, data):
        """Lưu danh sách TK gốc (wizard) để phải thu/trả/Từ–Đến mã chỉ thu hẹp trên đó."""
        if 's01dn_seed_account_ids' in data:
            return
        ai = data.get('account_ids')
        if ai is None:
            data['s01dn_seed_account_ids'] = None
        else:
            data['s01dn_seed_account_ids'] = list(ai)

    @api.model
    def _s01dn_narrow_account_ids_by_code_range(
        self, Acc, company_id, working_ids, acc_from, acc_to,
    ):
        if not working_ids or not acc_from.exists() or not acc_to.exists():
            return list(working_ids)
        cf = (acc_from.code or '').strip()
        ct = (acc_to.code or '').strip()
        if not cf or not ct:
            return list(working_ids)
        dom = [
            ('company_ids', 'in', [company_id]),
            ('id', 'in', list(working_ids)),
        ]
        if cf.isdigit() and ct.isdigit():
            sr, er = int(cf), int(ct)
            if sr > er:
                sr, er = er, sr
            dom += [
                ('code', '>=', str(sr)),
                ('code', '<=', str(er)),
            ]
        else:
            if cf > ct:
                cf, ct = ct, cf
            dom += [('code', '>=', cf), ('code', '<=', ct)]
        return Acc.search(dom).ids

    @api.model
    def _recompute_s01dn_data_account_ids(self, data):
        """
        Khoảng Từ mã–Đến mã (trong seed). Không chọn đủ Từ–Đến → không thu hẹp theo mã,
        giữ phạm vi seed.
        """
        company_id = data.get('company_id')
        if not company_id:
            return
        seed = data.get('s01dn_seed_account_ids')
        Acc = self.env['account.account']
        cf_id = data.get('s01dn_ui_account_code_from_id')
        ct_id = data.get('s01dn_ui_account_code_to_id')

        base_dom = [('company_ids', 'in', [company_id])]
        if seed:
            base_dom.append(('id', 'in', list(seed)))

        base_ids = Acc.search(base_dom).ids
        if not cf_id or not ct_id:
            data['account_ids'] = base_ids
            return
        af = Acc.browse(int(cf_id))
        at = Acc.browse(int(ct_id))
        if not af.exists() or not at.exists():
            data['account_ids'] = base_ids
            return
        if (
            company_id not in af.company_ids.ids
            or company_id not in at.company_ids.ids
        ):
            data['account_ids'] = base_ids
            return
        data['account_ids'] = self._s01dn_narrow_account_ids_by_code_range(
            Acc, company_id, list(base_ids), af, at,
        )

    @api.model
    def _merge_s01dn_ui_filters_into_data_domain(self, data):
        """Gộp bộ lọc UI vào domain journal items → truy vấn DB (search), không lọc DOM."""
        filters = data.get('s01dn_ui_filters')
        if not filters:
            return data

        # Cùng các field trên form General Ledger wizard — chỉnh trực tiếp trên thanh QWeb
        if filters.get('target_move') in ('posted', 'all'):
            data['only_posted_moves'] = filters['target_move'] == 'posted'
        if 'hide_account_at_0' in filters:
            data['hide_account_at_0'] = bool(filters['hide_account_at_0'])
        if 'account_code_from_id' in filters:
            v = filters.get('account_code_from_id')
            data['s01dn_ui_account_code_from_id'] = int(v) if v else False
        if 'account_code_to_id' in filters:
            v = filters.get('account_code_to_id')
            data['s01dn_ui_account_code_to_id'] = int(v) if v else False
            
        if 'receivable_accounts_only' in filters:
            data['receivable_accounts_only'] = bool(filters['receivable_accounts_only'])
        if 'payable_accounts_only' in filters:
            data['payable_accounts_only'] = bool(filters['payable_accounts_only'])
        if 'centralize' in filters:
            data['centralize'] = bool(filters['centralize'])
        if 'foreign_currency' in filters:
            data['foreign_currency'] = bool(filters['foreign_currency'])
        if 'show_cost_center' in filters:
            data['show_cost_center'] = bool(filters['show_cost_center'])

        company_id = data.get('company_id')
        wizard_id = data.get('wizard_id')
        wiz = self.env['general.ledger.report.wizard'].browse(
            wizard_id,
        ) if wizard_id else None

        self._recompute_s01dn_data_account_ids(data)

        # Kỳ từ thanh QWeb: không bắt buộc wizard còn tồn tại (transient có thể đã bị xóa).
        # Siết trong [s01dn_ui_date_min, s01dn_ui_date_max] lưu trong payload reload.
        udf = filters.get('date_from')
        udt = filters.get('date_to')
        if udf and udt and company_id:
            df = self._s01dn_parse_date(udf)
            dt = self._s01dn_parse_date(udt)
            if df and dt:
                wf = wt = None
                if wiz and wiz.id:
                    wf = wiz.date_from
                    wt = wiz.date_to
                if wf is None:
                    wf = self._s01dn_parse_date(data.get('s01dn_ui_date_min'))
                if wt is None:
                    wt = self._s01dn_parse_date(data.get('s01dn_ui_date_max'))
                if wf and df < wf:
                    df = wf
                if wt and dt > wt:
                    dt = wt
                if df > dt:
                    if wf and wt:
                        df, dt = wf, wt
                    else:
                        df, dt = dt, df
                data['date_from'] = df
                data['date_to'] = dt
                company = self.env['res.company'].browse(company_id)
                fy_start, _fy_end = date_utils.get_fiscal_year(
                    df,
                    day=company.fiscalyear_last_day,
                    month=int(company.fiscalyear_last_month),
                )
                data['fy_start_date'] = fy_start

        date_from = self._s01dn_parse_date(data.get('date_from'))
        date_to = self._s01dn_parse_date(data.get('date_to'))
        if not date_from or not date_to:
            return data

        target_move = filters.get('target_move')
        if target_move:
            data['target_move'] = target_move
            data['only_posted_moves'] = True if target_move == 'posted' else False
            if wiz:
                wiz.target_move = target_move

        base = (
            list(wiz._get_account_move_lines_domain())
            if wiz
            else list(data.get('domain') or [])
        )
        
        # Scrub state filters from base so we can re-apply dynamically
        base = [leaf for leaf in base if not (isinstance(leaf, tuple) and leaf[0] in ('parent_state', 'move_id.state'))]
        
        account_ids = filters.get('account_ids')
        journal_names = filters.get('journal_names')
        search = (filters.get('search') or '').strip()

        extra = []
        if data.get('only_posted_moves'):
            extra.append([('parent_state', '=', 'posted')])

        # TK
        if account_ids is not None:
            if len(account_ids) == 0:
                data['account_ids'] = []
                data['domain'] = base + [('id', '=', 0)]
                return data
            data['account_ids'] = [int(x) for x in account_ids]
            # Mỗi nhánh phải là domain dạng list [tuple,...], không phải tuple trần
            extra.append([
                ('account_id', 'in', data['account_ids']),
            ])
        else:
            data['account_ids'] = []

        # Nhật ký (theo tên hiển thị)
        if journal_names is not None:
            if len(journal_names) == 0:
                data['journal_ids'] = []
                data['domain'] = base + [('id', '=', 0)]
                return data
            jids = self.env['account.journal'].search([
                ('company_id', '=', company_id),
                ('name', 'in', list(journal_names)),
            ]).ids
            if not jids:
                data['journal_ids'] = []
                data['domain'] = base + [('id', '=', 0)]
                return data
            data['journal_ids'] = jids
            extra.append([('journal_id', 'in', jids)])
        else:
            data['journal_ids'] = []

        if search:
            term = f'%{search}%'
            # OR() trả về một domain (list) — append một phần tử cho AND()
            extra.append(
                OR([
                    [('name', 'ilike', term)],
                    [('ref', 'ilike', term)],
                    [('move_id.name', 'ilike', term)],
                ]),
            )

        partner_ids = filters.get('partner_ids')
        if partner_ids is not None:
            if len(partner_ids) == 0:
                data['partner_ids'] = []
                data['domain'] = base + [('id', '=', 0)]
                return data
            data['partner_ids'] = [int(x) for x in partner_ids]
            extra.append([('partner_id', 'in', data['partner_ids'])])
        else:
            data['partner_ids'] = []

        cost_center_ids = filters.get('cost_center_ids')
        if cost_center_ids is not None:
            if len(cost_center_ids) == 0:
                data['cost_center_ids'] = []
                data['domain'] = base + [('id', '=', 0)]
                return data
            data['cost_center_ids'] = [int(x) for x in cost_center_ids]
            extra.append([('analytic_line_ids.account_id', 'in', data['cost_center_ids'])])
        else:
            data['cost_center_ids'] = []

        # NOTE: receivable_accounts_only / payable_accounts_only are now
        # handled client-side by syncAccountCheckboxes() which auto-checks
        # the correct account_ids. No need for extra domain filters here.

        if extra:
            data['domain'] = AND([base] + extra) if base else AND(extra)
        else:
            data['domain'] = base
        return data

    @api.model
    def _compute_monthly_summaries(self, summary_lines, accounts_ordered,
                                   opening_balances, date_from, date_to,
                                   fy_start_date=None):
        if not date_from or not date_to:
            return []

        months = []
        d = date_from.replace(day=1)
        while d <= date_to:
            months.append((d.year, d.month))
            d += relativedelta(months=1)

        ml_by_month = defaultdict(list)
        for ml in summary_lines:
            ml_date = ml['date']
            if isinstance(ml_date, str):
                ml_date = date.fromisoformat(ml_date)
            if ml_date:
                ml_by_month[(ml_date.year, ml_date.month)].append(ml)

        acc_ids = [a['id'] for a in accounts_ordered]
        # Cột 1 (Số dư cuối tháng): đầu năm (tổng Nợ) + lũy kế Nợ phát sinh trong năm TK
        total_opening_debit = sum(
            float((opening_balances.get(a['id']) or {}).get('debit', 0) or 0)
            for a in accounts_ordered
        )
        running_closing_col1 = float(total_opening_debit)

        running_balance = {
            aid: opening_balances.get(aid, {}).get('balance', 0)
            for aid in acc_ids
        }

        fs = self._s01dn_coerce_report_date(fy_start_date)
        if fs and date_from:
            for ml in summary_lines:
                ml_date = ml['date']
                if isinstance(ml_date, str):
                    ml_date = date.fromisoformat(ml_date[:10])
                if ml_date and fs <= ml_date < date_from:
                    aid = ml['_account_id']
                    if aid in running_balance:
                        running_balance[aid] += float(
                            ml.get('debit', 0) or 0,
                        ) - float(ml.get('credit', 0) or 0)
                    running_closing_col1 += float(ml.get('debit', 0) or 0)

        def _ml_date(m):
            x = m['date']
            if isinstance(x, str):
                return date.fromisoformat(x[:10])
            return x

        def _cumul_quarter_lines(year, month):
            """Lũy kế theo quý dương lịch: từ tháng đầu quý đến hết tháng hiện tại."""
            qsm = ((month - 1) // 3) * 3 + 1
            chunk = []
            for ml in summary_lines:
                dline = _ml_date(ml)
                if dline and dline.year == year and qsm <= dline.month <= month:
                    chunk.append(ml)
            return chunk

        result = []
        for year, month in months:
            lines_m = ml_by_month.get((year, month), [])
            if not lines_m:
                continue

            month_debit = sum(ml.get('debit', 0) for ml in lines_m)
            month_credit = sum(ml.get('credit', 0) for ml in lines_m)
            running_closing_col1 += float(month_debit or 0)

            acc_d = {aid: 0.0 for aid in acc_ids}
            acc_c = {aid: 0.0 for aid in acc_ids}
            for ml in lines_m:
                aid = ml['_account_id']
                if aid in acc_d:
                    acc_d[aid] += ml.get('debit', 0)
                    acc_c[aid] += ml.get('credit', 0)

            closing_d = {}
            closing_c = {}
            for aid in acc_ids:
                running_balance[aid] += acc_d[aid] - acc_c[aid]
                bal = running_balance[aid]
                closing_d[aid] = bal if bal > 0 else 0
                closing_c[aid] = abs(bal) if bal < 0 else 0

            q_lines = _cumul_quarter_lines(year, month)
            cumul_debit = sum(float(x.get('debit', 0) or 0) for x in q_lines)
            cumul_credit = sum(float(x.get('credit', 0) or 0) for x in q_lines)
            cumul_acc = {aid: {'debit': 0.0, 'credit': 0.0} for aid in acc_ids}
            for ml in q_lines:
                aid = ml['_account_id']
                if aid in cumul_acc:
                    cumul_acc[aid]['debit'] += float(ml.get('debit', 0) or 0)
                    cumul_acc[aid]['credit'] += float(ml.get('credit', 0) or 0)

            result.append({
                'month': month,
                'year': year,
                'period_label': _('Total movements for month %s') % month,
                # Tổng phát sinh kỳ = tổng Nợ (= tổng Có); không cộng Nợ+Có (tránh gấp đôi)
                'period_total': month_debit,
                'period_debit': month_debit,
                'period_credit': month_credit,
                'period_acc_d': dict(acc_d),
                'period_acc_c': dict(acc_c),
                'closing_label': _('Closing balance at month-end %s') % month,
                'closing_col1': running_closing_col1,
                'closing_total_d': sum(closing_d.values()),
                'closing_total_c': sum(closing_c.values()),
                'closing_acc_d': dict(closing_d),
                'closing_acc_c': dict(closing_c),
                'cumul_label': _(
                    'Quarter-to-date cumulative through month %s'
                ) % month,
                'cumul_total': cumul_debit,
                'cumul_debit': cumul_debit,
                'cumul_credit': cumul_credit,
                'cumul_acc_d': {aid: v['debit']
                                for aid, v in cumul_acc.items()},
                'cumul_acc_c': {aid: v['credit']
                                for aid, v in cumul_acc.items()},
            })

        return result
