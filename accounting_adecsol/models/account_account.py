from odoo import models, api, fields

class AccountAccount(models.Model):
    _inherit = "account.account"

    # Đổi tên từ root_id thành parent_level1_id để tránh trùng với core Odoo
    parent_level1_id = fields.Many2one(
        'account.account', 
        string='Tài khoản cấp 1 (Custom)', 
        compute='_compute_parent_level1_id', 
        store=True,
        index=True
    )

    @api.depends('code', 'company_ids')
    def _compute_parent_level1_id(self):
        for record in self:
            # Odoo 18 dùng Many2many cho company_ids
            comp_id = record.company_ids[:1].id if record.company_ids else False
            
            # Logic: Nếu code > 3 ký tự, tìm tài khoản 3 ký tự đầu làm cha
            if record.code and len(record.code) > 3:
                prefix = record.code[:3]
                domain = [('code', '=', prefix)]
                if comp_id:
                    domain.append(('company_ids', 'in', [comp_id]))
                
                parent = self.env['account.account'].search(domain, limit=1)
                record.parent_level1_id = parent.id if parent else False
            else:
                record.parent_level1_id = False

    # Hàm _compute_code của bạn
    @api.depends('code_store')
    def _compute_code(self):
        super()._compute_code()
        for record in self:
            # Nếu code có 4 số và kết thúc bằng 0 (ví dụ 1110) thì rút gọn thành 3 số (111)
            if record.code and len(record.code) == 4 and record.code.endswith('0'):
                record.code = record.code[:3]