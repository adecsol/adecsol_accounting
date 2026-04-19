# -*- coding: utf-8 -*-
# A1.MoM.01 — Meeting Minutes

import pytz
from markupsafe import Markup
from datetime import timedelta
from odoo import api, fields, models, Command, _


class BAMoM(models.Model):
    """Meeting Minutes (A1.MoM.01)."""

    _name = "ba.mom"
    _description = "Meeting Minutes (MoM)"
    _inherit = ["mail.thread", "mail.activity.mixin", "ba.knowledge.mixin"]
    _order = "start_date desc, id desc"

    name = fields.Char(
        string="Subject",
        tracking=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="project_id.partner_id",
    )
    calendar_event_id = fields.Many2one(
        "calendar.event",
        string="Calendar Event",
    )
    document_page_id = fields.Many2one(
        "document.page",
        string="Knowledge Article",
    )
    knowledge_template_id = fields.Many2one(
        "mail.template",
        string="Knowledge Template",
        domain="[('model', '=', 'ba.mom')]",
    )
    start_date = fields.Datetime(
        string="Start",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    stop_date = fields.Datetime(
        string="End",
        default=lambda self: fields.Datetime.now() + timedelta(hours=1),
        required=True,
        tracking=True,
    )
    attendee_ids = fields.Many2many(
        "res.partner",
        string="Attendees",
    )
    note_take_partner_id = fields.Many2one(
        "res.partner",
        string="Note Taker",
        domain="[('id', 'in', attendee_ids)]",
        default=lambda self: self.env.user.partner_id,
    )
    project_team_id = fields.Many2one(
        "ba.project.team",
        string="Project Team",
        domain="[('project_id', '=?', project_id)]",
    )
    meeting_format = fields.Selection(
        [("online", "Online"), ("offline", "Offline")],
        string="Format",
        default="online",
    )
    meeting_location = fields.Char(
        string="Location",
        help="Used for offline meetings",
    )
    meeting_url = fields.Char(
        string="Meeting URL",
        help="Online meeting URL (Google Meet, Zoom, Teams…)",
    )
    content = fields.Html(
        string="Minutes Content",
        sanitize=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("approved", "Approved"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # ── CRUD overrides ────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self._generate_default_name(vals)
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if not rec.name:
                rec.name = rec._generate_default_name()
        return res

    def _generate_default_name(self, vals=None):
        """Generate default name from team or date."""
        if vals:
            team_id = vals.get("project_team_id")
            if team_id:
                team = self.env["ba.project.team"].browse(team_id)
                return _("Meeting %s") % team.display_name
            start = vals.get("start_date") or fields.Datetime.now()
            if isinstance(start, str):
                start = fields.Datetime.from_string(start)
            return _("Meeting Minutes %s") % start.strftime('%d/%m/%Y %H:%M')
        if self.project_team_id:
            return _("Meeting %s") % self.project_team_id.display_name
        start = self.start_date or fields.Datetime.now()
        return _("Meeting Minutes %s") % start.strftime('%d/%m/%Y %H:%M')

    # ── Actions ──────────────────────────────────────────────
    def action_confirm(self):
        """Confirm minutes and sync Calendar Event."""
        self.write({"state": "confirmed"})
        for rec in self:
            rec._sync_calendar_event()

        attendee_names = ", ".join(self.mapped("attendee_ids.name")) or "—"
        is_update = bool(self[:1].calendar_event_id)
        verb = _("Updated") if is_update else _("Created")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": f"📅 {verb} " + _("meeting"),
                "message": _("Calendar synced for: %s") % attendee_names,
                "type": "success",
                "sticky": False,
            },
        }

    def action_approve(self):
        self.write({"state": "approved"})
        self.action_post_to_project()

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_reset_draft(self):
        self.write({"state": "draft"})

    # _open_template_preview, action_open_knowledge_page,
    # action_preview_knowledge_document → inherited from ba.knowledge.mixin

    def action_preview_knowledge_template(self):
        """Preview the Knowledge template in a popup."""
        self.ensure_one()
        template = self.knowledge_template_id or self.env.ref(
            "adecsol_ba.knowledge_tpl_mom", raise_if_not_found=False
        )
        return self._open_template_preview(template, _("Knowledge Template Preview"))

    @api.onchange("project_id")
    def _onchange_project_id_clear_team(self):
        if not self.project_id:
            self.project_team_id = False
        elif (
            self.project_team_id
            and self.project_team_id.project_id != self.project_id
        ):
            self.project_team_id = False

    @api.onchange("project_team_id")
    def _onchange_project_team_id(self):
        if self.project_team_id:
            self.attendee_ids = self.project_team_id.member_ids
            if not self.project_id and self.project_team_id.project_id:
                self.project_id = self.project_team_id.project_id
            if not self.name:
                self.name = _("Meeting %s") % self.project_team_id.display_name

            domain = [
                ("project_team_id", "=", self.project_team_id.id),
                ("state", "!=", "cancel"),
            ]
            if getattr(self, "_origin", False) and self._origin.id:
                domain.append(("id", "!=", self._origin.id))

            last_mom = self.env["ba.mom"].search(domain, order="start_date desc, id desc", limit=1)
            if last_mom:
                if last_mom.start_date and last_mom.stop_date:
                    duration = last_mom.stop_date - last_mom.start_date
                    now = fields.Datetime.now()
                    self.start_date = last_mom.start_date.replace(year=now.year, month=now.month, day=now.day)
                    self.stop_date = self.start_date + duration

                self.meeting_format = last_mom.meeting_format
                self.meeting_location = last_mom.meeting_location
                self.meeting_url = last_mom.meeting_url
                self.note_take_partner_id = last_mom.note_take_partner_id

    # ── Calendar sync ─────────────────────────────────────────
    def _sync_calendar_event(self):
        """Create or update calendar.event for the meeting."""
        self.ensure_one()

        if self.meeting_url:
            description = Markup(
                f"<p><strong>{self.name}</strong></p>"
                f'<p>🔗 <a href="{self.meeting_url}" target="_blank">{self.meeting_url}</a></p>'
            )
        else:
            description = Markup(f"<p><strong>{self.name}</strong></p>")

        partner_ids = self.attendee_ids.ids[:]
        if self.note_take_partner_id and self.note_take_partner_id.id not in partner_ids:
            partner_ids.append(self.note_take_partner_id.id)
        partner_ids = list(set(partner_ids))

        event_vals = {
            "name": f"[MoM] {self.name}",
            "start": self.start_date,
            "stop": self.stop_date,
            "description": description,
            # v18: use Command for x2many writes
            "partner_ids": [Command.set(partner_ids)],
            "location": self.meeting_location or self.meeting_url or "",
        }

        if self.calendar_event_id:
            self.calendar_event_id.write(event_vals)
        else:
            event = self.env["calendar.event"].create(event_vals)
            self.calendar_event_id = event.id

    # ── Knowledge sync ────────────────────────────────────────
    def action_post_to_project(self):
        """Update or create a Document Page for the MoM."""
        for rec in self:
            parent_id = (
                rec.project_id.document_page_category_id.id
                if rec.project_id and rec.project_id.document_page_category_id
                else False
            )
            project_id = rec.project_id.id if rec.project_id else False
            
            template = rec.knowledge_template_id
            if not template:
                template = self.env.ref(
                    "adecsol_ba.knowledge_tpl_mom", raise_if_not_found=False
                )
                
            if template:
                body = template._render_field("body_html", [rec.id])[rec.id]
                page_name = template._render_field("subject", [rec.id])[rec.id]
            else:
                meeting_url_html = (
                    Markup(f'<a href="{rec.meeting_url}">{rec.meeting_url}</a>')
                    if rec.meeting_url
                    else Markup("—")
                )
                user_tz = pytz.timezone(rec.env.user.tz or 'Asia/Ho_Chi_Minh')
                tz_start = rec.start_date.astimezone(user_tz).strftime('%d/%m/%Y %H:%M') if rec.start_date else ""
                tz_stop = rec.stop_date.astimezone(user_tz).strftime('%H:%M') if rec.stop_date else ""
                body = Markup(
                    f"<strong>📝 Meeting Minutes:</strong> {rec.name}<br/>"
                    f"<strong>Time:</strong> {tz_start} - {tz_stop}<br/>"
                    f"<strong>Attendees:</strong> "
                    f"{', '.join(rec.attendee_ids.mapped('name'))}<br/>"
                    f"<strong>Meeting URL:</strong> {meeting_url_html}<br/>"
                    f"<hr/>{rec.content or ''}"
                )
                page_name = f"Meeting Minutes: {rec.name}"

            if not rec.document_page_id:
                doc = self.env["document.page"].create({
                    "name": page_name,
                    "project_id": project_id,
                    "parent_id": parent_id,
                    "draft_name": "1.0",
                    "draft_summary": "Meeting Minutes sync",
                    "content": body,
                })
                rec.document_page_id = doc.id
            else:
                rec.document_page_id.write({
                    "content": body,
                    "project_id": project_id,
                    "parent_id": parent_id or rec.document_page_id.parent_id.id,
                    "draft_name": "1.0",
                    "draft_summary": "Meeting Minutes sync",
                })