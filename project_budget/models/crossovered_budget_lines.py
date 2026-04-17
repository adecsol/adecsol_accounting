# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class CrossoveredBudgetLines(models.Model):
    _inherit = "crossovered.budget.lines"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._project_budget_invalidate_projects()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._project_budget_invalidate_projects()
        return res

    def unlink(self):
        self._project_budget_invalidate_projects()
        return super().unlink()

    def _project_budget_invalidate_projects(self):
        budget_ids = self.mapped("crossovered_budget_id").ids
        if not budget_ids:
            return
        projects = self.env["project.project"].search([("budget_id", "in", budget_ids)])
        if projects:
            projects.invalidate_recordset(["budget_id_lines"])
