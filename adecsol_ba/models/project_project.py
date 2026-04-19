# -*- coding: utf-8 -*-
# Project extension for BA Process

from ast import literal_eval

from odoo import _, api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    # ── BA Role Configuration ────────────────────────────────
    # PM = user_id (existing Odoo field on project.project)
    ba_manager_id = fields.Many2one(
        "res.users", string="BA Manager",
        tracking=True,
        help="BA Manager for this project. Can approve FSD, manage workflow stages.",
    )
    ba_user_ids = fields.Many2many(
        "res.users", "project_ba_user_rel", "project_id", "user_id",
        string="BA Users",
        help="BA staff assigned to this project. Can create/edit BA documents.",
    )
    ba_developer_ids = fields.Many2many(
        "res.users", "project_ba_developer_rel", "project_id", "user_id",
        string="Developers",
        help="Developers assigned to this project. Read-only access to BA docs, R/W on chatter.",
    )

    # ── BA Relations ─────────────────────────────────────────
    team_ids = fields.One2many(
        "ba.project.team", "project_id", string="Project Teams",
    )

    mom_ids = fields.One2many(
        "ba.mom", "project_id", string="Meeting Minutes",
    )
    mom_count = fields.Integer(compute="_compute_mom_count")

    survey_ids = fields.One2many(
        "ba.customer.survey", "project_id", string="Customer Surveys",
    )
    survey_count = fields.Integer(compute="_compute_survey_count")

    fsd_ids = fields.One2many(
        "ba.fsd", "project_id", string="FSD Documents",
    )
    fsd_count = fields.Integer(compute="_compute_fsd_count")

    fitgap_ids = fields.One2many(
        "ba.fitgap", "project_id", string="FIT-GAP Analysis",
    )
    fitgap_count = fields.Integer(compute="_compute_fitgap_count")

    master_data_ids = fields.One2many(
        "ba.master.data", "project_id", string="Master Data",
    )
    master_data_count = fields.Integer(compute="_compute_master_data_count")

    handover_ids = fields.One2many(
        "ba.handover", "project_id", string="Technical Handovers",
    )
    handover_count = fields.Integer(compute="_compute_handover_count")

    document_page_count = fields.Integer(compute="_compute_document_page_count")

    # ── Knowledge category (auto-created) ───────────────────
    document_page_category_id = fields.Many2one(
        "document.page",
        string="Knowledge Category",
        domain="[('type','=','category')]",
        help="document.page category automatically created for this project.",
        copy=False,
    )

    # ── BA Process Status ────────────────────────────────────
    ba_current_step = fields.Selection([
        ('survey', 'Survey'),
        ('design', 'Design'),
        ('fsd_data', 'FSD & Data'),
        ('approval_handover', 'Approval & Handover'),
        ('plan_update', 'Plan Update'),
    ], string="Current Phase", default="survey", tracking=True)

    has_mom = fields.Boolean(compute="_compute_ba_process_status")
    has_survey = fields.Boolean(compute="_compute_ba_process_status")
    has_tobe = fields.Boolean(compute="_compute_ba_process_status")
    has_fitgap = fields.Boolean(compute="_compute_ba_process_status")
    has_fsd = fields.Boolean(compute="_compute_ba_process_status")
    has_master_data = fields.Boolean(compute="_compute_ba_process_status")
    has_signoff = fields.Boolean(compute="_compute_ba_process_status")
    has_handover = fields.Boolean(compute="_compute_ba_process_status")
    has_wbs = fields.Boolean(compute="_compute_ba_process_status")

    def _compute_ba_process_status(self):
        if not self.ids:
            for rec in self:
                rec.has_mom = rec.has_survey = rec.has_tobe = False
                rec.has_fitgap = rec.has_fsd = rec.has_master_data = False
                rec.has_signoff = rec.has_handover = rec.has_wbs = False
            return
        # sudo: bypass ACL to aggregate cross-role counts for BA dashboard status
        sudo_env = self.sudo().env
        project_ids = self.ids

        # Batch count all child records in single queries
        def _group_count(model, domain_extra=None):
            domain = [('project_id', 'in', project_ids)]
            if domain_extra:
                domain += domain_extra
            data = sudo_env[model].read_group(domain, ['project_id'], ['project_id'])
            return {d['project_id'][0]: d['project_id_count'] for d in data}

        mom_map = _group_count('ba.mom')
        survey_map = _group_count('ba.customer.survey')
        tobe_map = _group_count('document.page', [('doc_type', '=', 'tobe')])
        fitgap_map = _group_count('ba.fitgap')
        fsd_map = _group_count('ba.fsd')
        master_data_map = _group_count('ba.master.data')
        signoff_map = _group_count('ba.fsd', [('state', 'in', ['pending_signoff', 'approved'])])
        handover_map = _group_count('ba.handover')
        wbs_map = _group_count('project.task', [('is_wbs', '=', True)])

        for rec in self:
            rec.has_mom = bool(mom_map.get(rec.id))
            rec.has_survey = bool(survey_map.get(rec.id))
            rec.has_tobe = bool(tobe_map.get(rec.id))
            rec.has_fitgap = bool(fitgap_map.get(rec.id))
            rec.has_fsd = bool(fsd_map.get(rec.id))
            rec.has_master_data = bool(master_data_map.get(rec.id))
            rec.has_signoff = bool(signoff_map.get(rec.id))
            rec.has_handover = bool(handover_map.get(rec.id))
            rec.has_wbs = bool(wbs_map.get(rec.id))

    def _compute_mom_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['ba.mom'].sudo().read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.mom_count = mapped.get(rec.id, 0)

    def _compute_survey_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['ba.customer.survey'].sudo().read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.survey_count = mapped.get(rec.id, 0)

    def _compute_fsd_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['ba.fsd'].sudo().read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.fsd_count = mapped.get(rec.id, 0)

    def _compute_fitgap_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['ba.fitgap'].sudo().read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.fitgap_count = mapped.get(rec.id, 0)

    def _compute_master_data_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['ba.master.data'].sudo().read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.master_data_count = mapped.get(rec.id, 0)

    def _compute_handover_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['ba.handover'].sudo().read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.handover_count = mapped.get(rec.id, 0)

    def _compute_document_page_count(self):
        # sudo: bypass ACL to count records across all BA roles for smart button
        data = self.env['document.page'].sudo().read_group(
            [('project_id', 'in', self.ids), ('type', '!=', 'category')],
            ['project_id'], ['project_id'])
        mapped = {d['project_id'][0]: d['project_id_count'] for d in data}
        for rec in self:
            rec.document_page_count = mapped.get(rec.id, 0)

    # ── Lifecycle ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create corresponding document.page category when a new project is created."""
        records = super().create(vals_list)
        for rec in records:
            if not rec.document_page_category_id:
                category = self.env["document.page"].create({
                    "name": rec.name,
                    "type": "category",
                    "project_id": rec.id,
                    "draft_name": "1.0",
                    "draft_summary": f"Auto category for project {rec.name}",
                })
                rec.document_page_category_id = category.id
        records._subscribe_ba_roles()
        return records

    def write(self, vals):
        """Sync category name when project is renamed."""
        result = super().write(vals)
        if "name" in vals:
            for rec in self:
                if rec.document_page_category_id:
                    rec.document_page_category_id.name = rec.name
        if any(f in vals for f in ['ba_manager_id', 'ba_user_ids', 'ba_developer_ids']):
            self._subscribe_ba_roles()
        return result

    def _subscribe_ba_roles(self):
        """Automatically add assigned BA staff as followers of the project."""
        for rec in self:
            partners = self.env['res.partner'].browse()
            if rec.ba_manager_id:
                partners |= rec.ba_manager_id.partner_id
            if rec.ba_user_ids:
                partners |= rec.ba_user_ids.mapped('partner_id')
            if rec.ba_developer_ids:
                partners |= rec.ba_developer_ids.mapped('partner_id')
            if partners:
                rec.message_subscribe(partner_ids=partners.ids)

    # ── Auto-advance BA Phase ─────────────────────────────────
    def _auto_advance_ba_step(self):
        """Auto-advance ba_current_step based on actual data state.
        Called from child models after key transitions.
        Logic:
          - has confirmed handover → plan_update
          - has FSD pending/approved → approval_handover
          - has FSD draft or FIT-GAP confirmed → fsd_data
          - has TO-BE or FIT-GAP → design
          - default → survey
        """
        for rec in self:
            # sudo: bypass ACL to query child records across all roles for phase detection
            sudo_env = rec.sudo().env
            pid = rec.id

            # Check from the end of the workflow backward
            has_confirmed_handover = sudo_env['ba.handover'].search_count([
                ('project_id', '=', pid), ('state', '=', 'confirmed')
            ])
            if has_confirmed_handover:
                if rec.ba_current_step != 'plan_update':
                    rec.ba_current_step = 'plan_update'
                continue

            has_signoff = sudo_env['ba.fsd'].search_count([
                ('project_id', '=', pid),
                ('state', 'in', ['pending_signoff', 'approved']),
            ])
            has_draft_handover = sudo_env['ba.handover'].search_count([
                ('project_id', '=', pid), ('state', '=', 'draft')
            ])
            if has_signoff or has_draft_handover:
                if rec.ba_current_step not in ('approval_handover', 'plan_update'):
                    rec.ba_current_step = 'approval_handover'
                continue

            has_fsd = sudo_env['ba.fsd'].search_count([('project_id', '=', pid)])
            has_fitgap_confirmed = sudo_env['ba.fitgap'].search_count([
                ('project_id', '=', pid), ('state', '=', 'confirmed')
            ])
            if has_fsd or has_fitgap_confirmed:
                if rec.ba_current_step not in ('fsd_data', 'approval_handover', 'plan_update'):
                    rec.ba_current_step = 'fsd_data'
                continue

            has_tobe = sudo_env['document.page'].search_count([
                ('project_id', '=', pid), ('doc_type', '=', 'tobe')
            ])
            has_fitgap = sudo_env['ba.fitgap'].search_count([('project_id', '=', pid)])
            if has_tobe or has_fitgap:
                if rec.ba_current_step not in ('design', 'fsd_data', 'approval_handover', 'plan_update'):
                    rec.ba_current_step = 'design'
                continue
            # Default: stay at survey (only advance forward, never revert)

    # ── Dashboard Computed Fields ─────────────────────────────
    pending_fsd_count = fields.Integer(
        compute="_compute_dashboard_counts",
        string="Pending FSD Sign-off",
    )
    pending_survey_count = fields.Integer(
        compute="_compute_dashboard_counts",
        string="Awaiting Survey Response",
    )
    draft_handover_count = fields.Integer(
        compute="_compute_dashboard_counts",
        string="Draft Handovers",
    )
    ba_progress = fields.Integer(
        compute="_compute_dashboard_counts",
        string="BA Progress (%)",
    )

    def _compute_dashboard_counts(self):
        if not self.ids:
            for rec in self:
                rec.pending_fsd_count = rec.pending_survey_count = 0
                rec.draft_handover_count = rec.ba_progress = 0
            return
        # sudo: bypass ACL to aggregate dashboard counts across all BA roles
        sudo_env = self.sudo().env
        project_ids = self.ids

        fsd_pending = sudo_env['ba.fsd'].read_group(
            [('project_id', 'in', project_ids), ('state', '=', 'pending_signoff')],
            ['project_id'], ['project_id'])
        fsd_pending_map = {d['project_id'][0]: d['project_id_count'] for d in fsd_pending}

        survey_pending = sudo_env['ba.customer.survey'].read_group(
            [('project_id', 'in', project_ids), ('state', 'in', ['draft', 'sent'])],
            ['project_id'], ['project_id'])
        survey_pending_map = {d['project_id'][0]: d['project_id_count'] for d in survey_pending}

        handover_draft = sudo_env['ba.handover'].read_group(
            [('project_id', 'in', project_ids), ('state', '=', 'draft')],
            ['project_id'], ['project_id'])
        handover_draft_map = {d['project_id'][0]: d['project_id_count'] for d in handover_draft}

        step_progress = {
            'survey': 10, 'design': 30, 'fsd_data': 50,
            'approval_handover': 75, 'plan_update': 95,
        }

        for rec in self:
            rec.pending_fsd_count = fsd_pending_map.get(rec.id, 0)
            rec.pending_survey_count = survey_pending_map.get(rec.id, 0)
            rec.draft_handover_count = handover_draft_map.get(rec.id, 0)
            rec.ba_progress = step_progress.get(rec.ba_current_step, 0)

    # ── Dashboard Navigation Actions ─────────────────────────
    def action_dashboard_view_pending_fsd(self):
        """Open FSD list filtered to pending sign-off for this project."""
        self.ensure_one()
        return {
            'name': f'Pending FSD — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.fsd',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id), ('state', '=', 'pending_signoff')],
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    def action_dashboard_view_pending_survey(self):
        """Open Survey list filtered to draft/sent for this project."""
        self.ensure_one()
        return {
            'name': f'Pending Survey — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.customer.survey',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id), ('state', 'in', ['draft', 'sent'])],
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    def action_dashboard_view_draft_handover(self):
        """Open Handover list filtered to draft for this project."""
        self.ensure_one()
        return {
            'name': f'Draft Handover — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.handover',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id), ('state', '=', 'draft')],
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    # ── Actions ───────────────────────────────────────────────
    def action_view_mom(self):
        """Open MoM list for this project with domain + default context."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("adecsol_ba.ba_mom_action")
        action = dict(action)
        action["domain"] = [("project_id", "=", self.id)]
        ctx = action.get("context")
        if isinstance(ctx, str):
            ctx = dict(literal_eval(ctx or "{}"))
        else:
            ctx = dict(ctx or {})
        ctx.update(
            {
                "default_project_id": self.id,
                "search_default_project_id": self.id,
            }
        )
        action["context"] = ctx
        if self.mom_count == 1:
            action["views"] = [(False, "form")]
            # sudo: read record ID to navigate — user ACL checked by ORM on form open
            action["res_id"] = self.sudo().mom_ids[0].id
        return action

    def action_view_survey(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("adecsol_ba.ba_customer_survey_action")
        action = dict(action)
        action["domain"] = [("project_id", "=", self.id)]
        ctx = action.get("context")
        if isinstance(ctx, str):
            ctx = dict(literal_eval(ctx or "{}"))
        else:
            ctx = dict(ctx or {})
        ctx.update({
            "default_project_id": self.id,
            "search_default_project_id": self.id,
        })
        action["context"] = ctx
        if self.survey_count == 1:
            action["views"] = [(False, "form")]
            # sudo: read record ID to navigate — user ACL checked by ORM on form open
            action["res_id"] = self.sudo().survey_ids[0].id
        return action

    def action_view_fsd(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("adecsol_ba.ba_fsd_action")
        action = dict(action)
        action["domain"] = [("project_id", "=", self.id)]
        ctx = action.get("context")
        if isinstance(ctx, str):
            ctx = dict(literal_eval(ctx or "{}"))
        else:
            ctx = dict(ctx or {})
        ctx.update({
            "default_project_id": self.id,
            "search_default_project_id": self.id,
        })
        action["context"] = ctx
        if self.fsd_count == 1:
            action["views"] = [(False, "form")]
            # sudo: read record ID to navigate — user ACL checked by ORM on form open
            action["res_id"] = self.sudo().fsd_ids[0].id
        return action

    def action_view_fitgap(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("adecsol_ba.ba_fitgap_action")
        action = dict(action)
        action["domain"] = [("project_id", "=", self.id)]
        ctx = action.get("context")
        if isinstance(ctx, str):
            ctx = dict(literal_eval(ctx or "{}"))
        else:
            ctx = dict(ctx or {})
        ctx.update({
            "default_project_id": self.id,
            "search_default_project_id": self.id,
        })
        action["context"] = ctx
        if self.fitgap_count == 1:
            action["views"] = [(False, "form")]
            # sudo: read record ID to navigate — user ACL checked by ORM on form open
            action["res_id"] = self.sudo().fitgap_ids[0].id
        return action

    def action_view_master_data(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("adecsol_ba.ba_master_data_action")
        action = dict(action)
        action["domain"] = [("project_id", "=", self.id)]
        ctx = action.get("context")
        if isinstance(ctx, str):
            ctx = dict(literal_eval(ctx or "{}"))
        else:
            ctx = dict(ctx or {})
        ctx.update({
            "default_project_id": self.id,
            "search_default_project_id": self.id,
        })
        action["context"] = ctx
        if self.master_data_count == 1:
            action["views"] = [(False, "form")]
            # sudo: read record ID to navigate — user ACL checked by ORM on form open
            action["res_id"] = self.sudo().master_data_ids[0].id
        return action

    def action_view_knowledge(self):
        """Open Knowledge list for this project."""
        self.ensure_one()
        domain = [("project_id", "=", self.id)]
        docs = self.env["document.page"].search(domain)
        if len(docs) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": f"Knowledge — {self.name}",
                "res_model": "document.page",
                "view_mode": "form",
                "res_id": docs[0].id,
                "context": {
                    "default_project_id": self.id,
                    "default_parent_id": self.document_page_category_id.id if self.document_page_category_id else False,
                    "default_doc_type": "tobe",
                    "default_draft_name": "1.0",
                    "default_draft_summary": "TO-BE System Design",
                },
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"Knowledge — {self.name}",
            "res_model": "document.page",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_project_id": self.id,
                "default_parent_id": self.document_page_category_id.id if self.document_page_category_id else False,
                "default_doc_type": "tobe",
                "default_draft_name": "1.0",
                "default_draft_summary": "TO-BE System Design",
            },
            "target": "current",
        }

    def action_quick_mom_role(self):
        """Open a new MoM form with project + role members pre-filled."""
        self.ensure_one()
        role_field = self.env.context.get('role_field')
        attendee_ids = []
        if role_field and hasattr(self, role_field):
            users = getattr(self, role_field)
            if users:
                attendee_ids = users.mapped('partner_id').ids
        return {
            "type": "ir.actions.act_window",
            "name": _("New Meeting Minutes"),
            "res_model": "ba.mom",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_attendee_ids": attendee_ids,
            },
        }

    def action_create_knowledge_category(self):
        """Manually create Knowledge Category for older projects without one."""
        self.ensure_one()
        if self.document_page_category_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "document.page",
                "res_id": self.document_page_category_id.id,
                "view_mode": "form",
                "target": "current",
            }
        category = self.env["document.page"].create({
            "name": self.name,
            "type": "category",
            "project_id": self.id,
            "draft_name": "1.0",
            "draft_summary": f"Knowledge Category for project {self.name}",
        })
        self.document_page_category_id = category.id
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "✅ Knowledge Category Created",
                "message": f"Category '{self.name}' has been created in Knowledge.",
                "type": "success",
                "sticky": False,
            },
        }

    # ── BA Workflow Actions ──────────────────────────────────
    def action_quick_create_survey(self):
        return {
            'name': 'New Survey',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.customer.survey',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'new',
        }

    def action_quick_create_tobe(self):
        category_id = self.document_page_category_id.id if self.document_page_category_id else False
        return {
            'name': 'New TO-BE',
            'type': 'ir.actions.act_window',
            'res_model': 'document.page',
            'view_mode': 'form',
            'context': {
                'default_project_id': self.id,
                'default_doc_type': 'tobe',
                'default_parent_id': category_id,
                'default_category_id': category_id,
            },
            'target': 'new',
        }

    def action_quick_create_fitgap(self):
        return {
            'name': 'New FIT-GAP',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.fitgap',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'new',
        }

    def action_quick_create_fsd(self):
        return {
            'name': 'New FSD',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.fsd',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'new',
        }

    def action_quick_create_handover(self):
        return {
            'name': 'New Technical Handover',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.handover',
            'view_mode': 'form',
            'context': {
                'default_project_id': self.id,
            },
            'target': 'new',
        }

    def action_open_tobe_list(self):
        self.ensure_one()
        domain = [('project_id', '=', self.id), ('doc_type', '=', 'tobe')]
        docs = self.env["document.page"].search(domain)
        if len(docs) == 1:
            return {
                'name': 'TO-BE List',
                'type': 'ir.actions.act_window',
                'res_model': 'document.page',
                'view_mode': 'form',
                'res_id': docs[0].id,
                'context': {'default_project_id': self.id, 'default_doc_type': 'tobe'},
                'target': 'current',
            }
        return {
            'name': 'TO-BE List',
            'type': 'ir.actions.act_window',
            'res_model': 'document.page',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_project_id': self.id, 'default_doc_type': 'tobe'},
            'target': 'current',
        }

    def action_open_handover_list(self):
        self.ensure_one()
        if self.handover_count == 1:
            return {
                'name': 'Technical Handover',
                'type': 'ir.actions.act_window',
                'res_model': 'ba.handover',
                'view_mode': 'form',
                # sudo: read record ID to navigate — user ACL checked by ORM on form open
                'res_id': self.sudo().handover_ids[0].id,
                'context': {'default_project_id': self.id},
                'target': 'current',
            }
        return {
            'name': 'Technical Handover List',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.handover',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
            'target': 'current',
        }

    def action_quick_create_mom(self):
        return {
            'name': 'New Meeting Minutes',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.mom',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'new',
        }

    def action_quick_create_master_data(self):
        return {
            'name': 'New Master Data',
            'type': 'ir.actions.act_window',
            'res_model': 'ba.master.data',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'new',
        }

    def action_quick_create_wbs(self):
        return {
            'name': 'New WBS Task',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'form',
            'context': {'default_project_id': self.id, 'default_is_wbs': True},
            'target': 'new',
        }
    
    def action_open_wbs_list(self):
        self.ensure_one()
        domain = [('project_id', '=', self.id), ('is_wbs', '=', True)]
        tasks = self.env["project.task"].search(domain)
        if len(tasks) == 1:
            return {
                'name': 'WBS Task List',
                'type': 'ir.actions.act_window',
                'res_model': 'project.task',
                'view_mode': 'form',
                'res_id': tasks[0].id,
                'context': {'default_project_id': self.id, 'default_is_wbs': True},
                'target': 'current',
            }
        return {
            'name': 'WBS Task List',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_project_id': self.id, 'default_is_wbs': True},
            'target': 'current',
        }

    def action_goto_wbs_page(self):
        """Navigate to the WBS page tab within the project form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'goto_wbs_page',
            'context': {'project_id': self.id},
        }


