# -*- coding: utf-8 -*-
# A.1 — Extend calendar.event

from odoo import api, fields, models


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    # ── Stub for calendar view (requires resource module) ────
    @api.model
    def get_unusual_days(self, date_from, date_to=None):
        """Stub: returns no unusual days when resource module is absent."""
        return {}

    project_id = fields.Many2one(
        "project.project",
        string="Project",
    )
    mom_ids = fields.One2many(
        "ba.mom",
        "calendar_event_id",
        string="Meeting Minutes",
    )
    mom_count = fields.Integer(
        compute="_compute_mom_count",
        string="MoM Count",
    )
    # ── Stub: this field belongs to hr_calendar, needs to be declared so JS calendar
    # doesn't error when hr_calendar is not installed ─────────────
    unavailable_partner_ids = fields.Many2many(
        "res.partner",
        compute="_compute_unavailable_partner_ids",
        string="Unavailable Partners",
    )

    @api.depends("partner_ids")
    def _compute_unavailable_partner_ids(self):
        """Stub: always empty — real logic only in hr_calendar."""
        for rec in self:
            rec.unavailable_partner_ids = self.env["res.partner"]

    @api.depends("mom_ids")
    def _compute_mom_count(self):
        for rec in self:
            rec.mom_count = len(rec.mom_ids)

    def action_create_mom(self):
        """Create a MoM record pre-filled from this calendar event."""
        self.ensure_one()
        mom = self.env["ba.mom"].create({
            "name": self.name or "Meeting Minutes",
            "project_id": self.project_id.id if self.project_id else False,
            "calendar_event_id": self.id,
            "start_date": self.start,
            "stop_date": self.stop,
            "attendee_ids": [(6, 0, self.partner_ids.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Meeting Minutes",
            "res_model": "ba.mom",
            "res_id": mom.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_moms(self):
        """Open the list of MoMs for this meeting."""
        self.ensure_one()
        if self.mom_count == 1:
            return {
                "type": "ir.actions.act_window",
                "name": "Meeting Minutes",
                "res_model": "ba.mom",
                "view_mode": "form",
                "res_id": self.mom_ids[0].id,
                "context": {
                    "default_calendar_event_id": self.id,
                    "default_project_id": self.project_id.id if self.project_id else False,
                    "default_name": self.name,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": "Meeting Minutes",
            "res_model": "ba.mom",
            "view_mode": "list,form",
            "domain": [("calendar_event_id", "=", self.id)],
            "context": {
                "default_calendar_event_id": self.id,
                "default_project_id": self.project_id.id if self.project_id else False,
                "default_name": self.name,
            },
        }
