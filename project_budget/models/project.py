# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Project(models.Model):
    _inherit = "project.project"

    budget_id = fields.Many2one("crossovered.budget", string="Budget")
    # Computed instead of related=...crossovered_budget_line_ids: avoids registry
    # setup ordering where project.project is initialized before that One2many exists
    # on crossovered.budget (e.g. addons path / partial install edge cases).
    budget_id_lines = fields.One2many(
        comodel_name="crossovered.budget.lines",
        compute="_compute_budget_id_lines",
        string="Budget Lines",
    )
    budget_state = fields.Selection(related="budget_id.state", string="Budget Status")

    @api.depends("budget_id")
    def _compute_budget_id_lines(self):
        """Use search instead of budget_id.crossovered_budget_line_ids so @depends does
        not require that field on crossovered.budget (some DBs only expose budget.line).
        """
        Line = self.env["crossovered.budget.lines"]
        empty = Line.browse()
        for project in self:
            if not project.budget_id:
                project.budget_id_lines = empty
                continue
            project.budget_id_lines = Line.search(
                [("crossovered_budget_id", "=", project.budget_id.id)]
            )
