# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CrossoveredBudget(models.Model):
    _inherit = "crossovered.budget"

    # Same definition as account_budget_oca; ensures the field exists on the registry when
    # the base addon code on the server is missing or out of date (form view requires it).
    creating_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsible",
        default=lambda self: self.env.user,
    )
    project_id = fields.Many2one("project.project", string="Project")
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Default Analytic Account"
    )
