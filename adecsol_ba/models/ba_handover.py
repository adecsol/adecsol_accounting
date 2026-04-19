# -*- coding: utf-8 -*-
# D2.TRAN_DEV.01 — Technical Handover

from markupsafe import Markup, escape

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError


class BAHandover(models.Model):
    _name = "ba.handover"
    _description = "Technical Handover"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Handover Name", required=True, default="New Handover", tracking=True)
    project_id = fields.Many2one("project.project", string="Project", required=True, tracking=True)
    fsd_id = fields.Many2one("ba.fsd", string="FSD Document", tracking=True)
    feature_id = fields.Many2one("ba.fsd.feature", string="Feature", domain="[('fsd_id', '=', fsd_id)]", tracking=True)
    date = fields.Date(string="Handover Date", default=fields.Date.context_today, tracking=True)
    assignee_id = fields.Many2one(
        "res.users",
        string="Assignee",
        tracking=True,
        help="Person responsible for this handover.",
    )
    planned_hours = fields.Float(
        string="Planned Hours",
        tracking=True,
        help="Total estimated hours for this handover. Required before confirmation.",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string="Status", default='draft', tracking=True)

    current_can_confirm = fields.Boolean(
        compute="_compute_current_can_confirm", string="Can Confirm",
        help="Roles configured on the project: PM or BA Manager.",
    )

    def _compute_current_can_confirm(self):
        uid = self.env.uid
        for rec in self:
            proj = rec.project_id
            is_manager = proj.ba_manager_id.id == uid if proj.ba_manager_id else False
            is_pm = proj.user_id.id == uid if proj.user_id else False
            rec.current_can_confirm = is_manager or is_pm

    # Link to the generated parent task
    task_id = fields.Many2one(
        "project.task",
        string="Generated Task",
        ondelete="set null",
        copy=False,
        readonly=True,
        help="Parent task created upon confirmation.",
    )

    handover_line_ids = fields.One2many(
        "ba.handover.line", "handover_id", string="Handover Details"
    )
    note = fields.Html(string="General Notes")
    feature_content = fields.Html(
        string="Feature Info",
        compute="_compute_feature_content",
        sanitize=False,
    )

    # @api.depends — deep chain on feature fields: acceptable for non-stored compute
    @api.depends("feature_id", "feature_id.name", "feature_id.description",
                 "feature_id.logic_description", "feature_id.api_specification",
                 "feature_id.planned_hours", "feature_id.priority",
                 "feature_id.module_name", "feature_id.note")
    def _compute_feature_content(self):
        for rec in self:
            feat = rec.feature_id
            if not feat:
                rec.feature_content = False
                continue
            # escape() to prevent XSS from user-supplied field values
            rows = []
            rows.append(f"<tr><th style='width:200px'>Feature Name</th><td><b>{escape(feat.name or '')}</b></td></tr>")
            if feat.description:
                rows.append(f"<tr><th>Description</th><td>{escape(feat.description)}</td></tr>")
            if feat.logic_description:
                rows.append(f"<tr><th>Business Logic</th><td>{escape(feat.logic_description)}</td></tr>")
            if feat.api_specification:
                rows.append(f"<tr><th>API Specification</th><td>{escape(feat.api_specification)}</td></tr>")
            if feat.module_name:
                rows.append(f"<tr><th>Related Module</th><td>{escape(feat.module_name)}</td></tr>")
            priority_map = {'critical': 'Critical', 'major': 'Major', 'minor': 'Minor'}
            if feat.priority:
                rows.append(f"<tr><th>Priority</th><td>{priority_map.get(feat.priority, feat.priority)}</td></tr>")
            if feat.planned_hours:
                rows.append(f"<tr><th>Est. Hours (Dev)</th><td>{feat.planned_hours}</td></tr>")
            if feat.note:
                rows.append(f"<tr><th>Notes</th><td>{escape(feat.note)}</td></tr>")
            html = f"<table class='table table-bordered table-sm'>{''.join(rows)}</table>"
            rec.feature_content = Markup(html)

    def action_confirm(self):
        """Confirm the handover: validate planned hours, create parent task + subtasks.
        Only BA Manager or PM (configured on the project) can confirm.
        """
        for rec in self:
            uid = rec.env.uid
            proj = rec.project_id
            is_manager = proj.ba_manager_id.id == uid
            is_pm = proj.user_id.id == uid
            if not is_manager and not is_pm and not rec.env.is_superuser():
                # UserError for authorization — not a field constraint
                raise UserError(
                    _("Only the BA Manager or Project Manager of project '%s' can confirm a handover.") % proj.name
                )
            if rec.state == 'confirmed':
                continue

            # ── Validate required fields ────────────────────────
            if not rec.planned_hours or rec.planned_hours <= 0:
                raise ValidationError(
                    _("Cannot confirm handover '%s': Planned Hours must be filled in before confirmation.")
                    % rec.name
                )
            if not rec.assignee_id:
                raise ValidationError(
                    _("Cannot confirm handover '%s': Assignee must be set before confirmation.")
                    % rec.name
                )

            # ── Build parent task description ─────────────────
            desc_parts = []
            if rec.fsd_id:
                desc_parts.append(f"<b>FSD:</b> {escape(rec.fsd_id.name or '')}")
            if rec.feature_id:
                desc_parts.append(f"<b>Feature:</b> {escape(rec.feature_id.name or '')}")
            if rec.note:
                desc_parts.append(f"<b>Notes:</b><br/>{rec.note}")
            parent_desc = "<br/>".join(desc_parts) if desc_parts else ''

            # ── Create parent task from handover ──────────────
            task_vals = {
                'name': rec.name,
                'project_id': rec.project_id.id,
                'description': parent_desc,
                'is_wbs': True,
                'allocated_hours': rec.planned_hours,
                'ba_feature_priority': rec.feature_id.priority,
            }
            if rec.assignee_id:
                # v18: use Command for x2many writes
                task_vals['user_ids'] = [Command.set([rec.assignee_id.id])]
            parent_task = self.env['project.task'].create(task_vals)
            rec.task_id = parent_task.id

            # ── Batch create subtasks from handover lines ─────
            subtask_vals_list = []
            lines_to_link = []
            for line in rec.handover_line_ids:
                if line.generated_task_id:
                    continue  # already has a generated subtask

                parts = []
                if line.objective:
                    parts.append(f"<b>Objective:</b> {escape(line.objective)}")
                if line.iso_9001:
                    parts.append(f"<b>ISO 9001:</b> {escape(line.iso_9001)}")
                if line.iso_27001:
                    parts.append(f"<b>ISO 27001:</b> {escape(line.iso_27001)}")
                if line.odoo_std_module:
                    parts.append(f"<b>Odoo V18 Std:</b> {escape(line.odoo_std_module)}")
                if line.oca_module:
                    parts.append(f"<b>OCA:</b> {escape(line.oca_module)}")
                if line.custom_work:
                    parts.append(f"<b>Custom Dev:</b> {line.custom_work}")
                if line.depend:
                    parts.append(f"<b>Dependencies:</b> {escape(line.depend)}")
                if line.inherit_model:
                    parts.append(f"<b>Inherit:</b> {escape(line.inherit_model)}")
                if line.community_note:
                    parts.append(f"<b>Community Note:</b> {escape(line.community_note)}")
                if line.adec_module:
                    parts.append(f"<b>ADEC Module:</b> {escape(line.adec_module)}")
                if line.note:
                    parts.append(f"<b>Notes:</b> {escape(line.note)}")
                desc = "<br/>".join(parts) if parts else ''

                subtask_vals_list.append({
                    'name': line.objective or f"Subtask: {rec.name}",
                    'project_id': rec.project_id.id,
                    'parent_id': parent_task.id,
                    'description': desc,
                    'is_wbs': True,
                    'source_handover_line_id': line.id,
                    # v18: use Command for x2many writes
                    'user_ids': [Command.set([rec.assignee_id.id])],
                    'ba_feature_priority': rec.feature_id.priority,
                })
                lines_to_link.append(line)

            # Batch create all subtasks at once (performance)
            if subtask_vals_list:
                subtasks = self.env['project.task'].create(subtask_vals_list)
                for line, subtask in zip(lines_to_link, subtasks):
                    line.generated_task_id = subtask.id

            rec.state = 'confirmed'
            # Auto-advance project BA phase
            if rec.project_id:
                rec.project_id._auto_advance_ba_step()

    def action_view_task(self):
        """Open the generated parent task."""
        self.ensure_one()
        if not self.task_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_form(self):
        """Open this handover record in a popup dialog for detailed editing."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ba.handover',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
