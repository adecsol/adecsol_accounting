# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, Command


class BAProjectTeam(models.Model):
    _name = "ba.project.team"
    _description = "Project Team"

    name = fields.Char(string="Team Name", required=True)
    project_id = fields.Many2one("project.project", string="Project", required=True, ondelete="cascade")
    member_ids = fields.Many2many("res.partner", string="Members")

    @api.depends("name", "project_id.display_name")
    def _compute_display_name(self):
        for rec in self:
            if rec.project_id:
                rec.display_name = f"[{rec.project_id.display_name}] {rec.name}".strip()
            else:
                rec.display_name = rec.name or ""

    def action_quick_mom(self):
        """Open a new MoM form with project + team + attendees pre-filled."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Meeting Minutes"),
            "res_model": "ba.mom",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_project_id": self.project_id.id,
                "default_project_team_id": self.id,
                "default_attendee_ids": [Command.set(self.member_ids.ids)],
            },
        }
