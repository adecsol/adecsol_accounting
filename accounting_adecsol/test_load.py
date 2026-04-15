# test_load.py
from odoo import api, SUPERUSER_ID

def load_test_data(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    account_111 = env['account.account'].search([('code', '=', '111')], limit=1)
    account_511 = env['account.account'].search([('code', '=', '511')], limit=1)
    
    if account_111 and account_511:
        move_vals = {
            'date': '2026-02-01',
            'ref': 'Test B02-DN',
            'journal_id': env['account.journal'].search([('type', '=', 'general')], limit=1).id,
            'line_ids': [
                (0, 0, {'account_id': account_111.id, 'debit': 100000000, 'credit': 0}),
                (0, 0, {'account_id': account_511.id, 'debit': 0, 'credit': 100000000}),
            ]
        }
        move = env['account.move'].create(move_vals)
        move.action_post()
        print(f"Created test entry: {move.id}")