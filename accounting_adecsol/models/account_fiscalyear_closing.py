# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class AccountFiscalyearClosing(models.Model):
    _inherit = "account.fiscalyear.closing"

    # --- BỔ SUNG FIELDS CHO SMART BUTTONS (Cập nhật store=True) ---
    revenue_amount = fields.Float(
        string=_("Total revenue"),
        compute="_compute_closing_stats",
        store=True
    )
    expense_amount = fields.Float(
        string=_("Total expenses"),
        compute="_compute_closing_stats",
        store=True
    )
    move_count = fields.Integer(
        string=_("Journal entry count"),
        compute="_compute_closing_stats",
        store=True
    )

    @api.depends('date_start', 'date_end', 'company_id', 'move_ids', 'move_ids.state')
    def _compute_closing_stats(self):
        for rec in self:
            if not rec.date_start or not rec.date_end:
                rec.revenue_amount = 0
                rec.expense_amount = 0
                rec.move_count = 0
                continue

            # Base domain lọc bút toán đã vào sổ trong kỳ
            base_domain = [
                ('parent_state', '=', 'posted'),
                ('date', '>=', rec.date_start),
                ('date', '<=', rec.date_end),
                ('company_id', '=', rec.company_id.id)
            ]

            # 1. Tính Doanh thu (Income)
            income_lines = self.env['account.move.line'].search(base_domain + [
                ('account_id.account_type', '=', 'income')
            ])
            rec.revenue_amount = sum(income_lines.mapped('credit')) - sum(income_lines.mapped('debit'))

            # 2. Tính Chi phí (Tất cả các loại chi phí đầu 6, 8)
            # Thêm 'expense_depreciation' để lấy cả khấu hao (6274, 6424...)
            expense_types = ['expense', 'expense_direct_cost', 'expense_depreciation']
            expense_lines = self.env['account.move.line'].search(base_domain + [
                ('account_id.account_type', 'in', expense_types)
            ])
            # Chi phí = Tổng Nợ - Tổng Có
            rec.expense_amount = sum(expense_lines.mapped('debit')) - sum(expense_lines.mapped('credit'))

            rec.move_count = len(rec.move_ids)

            
    # --- GIỮ NGUYÊN VÀ FIX LOGIC CÁC HÀM CŨ ---
    @api.model
    def default_get(self, fields_list):
        res = super(AccountFiscalyearClosing, self).default_get(fields_list)
        if self._context.get('default_template_auto_load', True):
            template = self.env.ref('accounting_adecsol.closing_template_tt200', raise_if_not_found=False)
            if template:
                res.update({
                    'closing_template_id': template.id,
                    'check_draft_moves': template.check_draft_moves,
                })
        return res

    @api.model
    def create(self, vals):
        if vals.get('closing_template_id') and 'move_config_ids' not in vals:
            record = super(AccountFiscalyearClosing, self).create(vals)
            record.onchange_template_id()
            return record
        return super(AccountFiscalyearClosing, self).create(vals)

    @api.onchange('year')
    def _onchange_year(self):
        if self.year and self.company_id:
            last_month = self.company_id.fiscalyear_last_month or 12
            last_day = self.company_id.fiscalyear_last_day or 31
            date_end_str = f"{self.year}-{str(last_month).zfill(2)}-{str(last_day).zfill(2)}"
            self.date_end = date_end_str
            date_end = fields.Date.from_string(date_end_str)
            date_start = date_end - relativedelta(years=1) + relativedelta(days=1)
            self.date_start = fields.Date.to_string(date_start)
            date_opening = date_end + relativedelta(days=1)
            self.date_opening = fields.Date.to_string(date_opening)
            if self.date_start and self.date_end:
                self.name = f"{self.date_start} - {self.date_end}"

    def calculate(self):
        for closing in self:
            if closing.check_draft_moves:
                closing.draft_moves_check()
            for config in closing.move_config_ids.filtered("enabled"):
                try:
                    move, data = config.moves_create()
                    if not move and data and data.get('error'):
                        pass 
                except Exception as e:
                    raise ValidationError(
                        _("Error while creating journal entry for \"%(name)s\": %(error)s")
                        % {"name": config.name, "error": str(e)}
                    )
        return True

    def button_calculate(self):
        res = self.calculate()
        if res is True:
            self.write({
                "state": "calculated",
                "calculation_date": fields.Datetime.now(),
            })
        return res

# --- CÁC CLASS CONFIG, MAPPING ---
class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config"

    def inverse_move_prepare(self):
        self.ensure_one()
        if not self.inverse:
            return self.env['account.move']
        config_to_inverse = self.fyc_id.move_config_ids.filtered(
            lambda r: r.code == self.inverse
        )
        if not config_to_inverse or not config_to_inverse.move_id:
            return self.env['account.move']
        return config_to_inverse.move_id

    def moves_create(self):
        self.ensure_one()
        data = False
        try:
            if self.mapping_ids:
                return self._create_move()
            elif self.inverse:
                move = self.inverse_move_prepare()
                if move: 
                    move.write({
                        "ref": self.name,
                        "closing_type": self.move_type
                    })
                    self.move_id = move.id
                    return move, data
                else:
                    return False, data
        except Exception as e:
            return False, data
        return False, data

class AccountFiscalyearClosingMapping(models.Model):
    _inherit = "account.fiscalyear.closing.mapping"

    def move_line_prepare(self, account, account_lines, partner_id=False):
        self.ensure_one()
        move_line = {}
        balance = 0
        precision = self.env['decimal.precision'].precision_get('Account')
        description = self.name or account.name
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == 'opening':
            date = self.fyc_config_id.fyc_id.date_opening
        if account_lines:
            total_debit = sum(account_lines.mapped('debit'))
            total_credit = sum(account_lines.mapped('credit'))
            balance = total_debit - total_credit
            if not float_is_zero(balance, precision_digits=precision):
                move_line = {
                    'account_id': account.id,
                    'debit': balance < 0 and -balance or 0.0,
                    'credit': balance > 0 and balance or 0.0,
                    'name': _("Closing: %s") % description,
                    'date': date,
                    'partner_id': partner_id,
                }
        return balance, move_line

    def dest_move_line_prepare(self, dest, balance, partner_id=False):
        self.ensure_one()
        move_line = {}
        precision = self.env['decimal.precision'].precision_get('Account')
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == 'opening':
            date = self.fyc_config_id.fyc_id.date_opening
        if not float_is_zero(balance, precision_digits=precision):
            move_line = {
                'account_id': dest.id,
                'debit': balance < 0 and -balance or 0.0,
                'credit': balance > 0 and balance or 0.0,
                'name': _("Closing balance transfer"),
                'date': date,
                'partner_id': partner_id,
            }
        return move_line

    def account_lines_get(self, account):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        return self.env['account.move.line'].search([
            ('company_id', '=', company_id),
            ('account_id', '=', account.id),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', start),
            ('date', '<=', end),
        ])

class AccountFiscalYearClosingUnbalancedMove(models.TransientModel):
    _inherit = "account.fiscalyear.closing.unbalanced.move"

    def button_recalculate(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            closing = self.env['account.fiscalyear.closing'].browse(active_id)
            return closing.button_calculate()
        return {'type': 'ir.actions.act_window_close'}