# -*- coding: utf-8 -*-
# C1.FSD.01 — Functional Specification Document

import uuid

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BAFSD(models.Model):
    """Functional Specification Document (C1.FSD.01).

    Workflow:  Draft → Pending Customer Sign-off → Final Approved
    Internal approval by PM / BA Manager is required before sending to customer.
    """

    _name = "ba.fsd"
    _description = "Functional Specification Document (FSD)"
    _inherit = ["mail.thread", "mail.activity.mixin", "ba.knowledge.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="FSD Title",
        required=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        required=True,
        tracking=True,
    )
    document_page_id = fields.Many2one(
        "document.page",
        string="Knowledge",
    )
    knowledge_template_id = fields.Many2one(
        "mail.template",
        string="Knowledge Template",
        domain="[('model', '=', 'ba.fsd')]",
        help="Mail template used to render the Knowledge page content.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="project_id.partner_id",
        store=True,
        readonly=True,
        tracking=True,
    )
    fitgap_id = fields.Many2one(
        "ba.fitgap",
        string="FIT-GAP",
        tracking=True,
    )
    fitgap_module = fields.Char(
        string="Module",
        related="fitgap_id.fitgap_module",
        readonly=True,
    )

    @api.onchange("fitgap_id")
    def _onchange_fitgap_id(self):
        if self.fitgap_id:
            self.project_id = self.fitgap_id.project_id

    # ── Features (one2many) ──────────────────────────────────
    feature_ids = fields.One2many(
        "ba.fsd.feature",
        "fsd_id",
        string="Feature Table",
    )
    feature_count = fields.Integer(
        compute="_compute_feature_count",
    )
    total_planned_hours = fields.Float(
        string="Total Estimated Hours",
        compute="_compute_total_planned_hours",
        store=True,
    )

    # ── Task link ────────────────────────────────────────────
    fitgap_task_ids = fields.Many2many(
        "project.task",
        "ba_fsd_task_rel",
        "fsd_id",
        "task_id",
        string="Linked Dev Tasks",
    )

    # ── State ────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_signoff", "Pending Customer Sign-off"),
            ("approved", "Final Approved"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    is_locked = fields.Boolean(
        compute="_compute_is_locked",
        string="Locked",
    )

    # ── Project-level role checks (computed) ─────────────────
    current_is_ba_manager = fields.Boolean(
        compute="_compute_current_roles", string="Is BA Manager",
    )
    current_is_pm = fields.Boolean(
        compute="_compute_current_roles", string="Is PM",
    )
    current_is_ba_user = fields.Boolean(
        compute="_compute_current_roles", string="Is BA User",
    )
    current_is_developer = fields.Boolean(
        compute="_compute_current_roles", string="Is Developer",
    )
    current_can_approve = fields.Boolean(
        compute="_compute_current_roles", string="Can Approve",
        help="True if current user is BA Manager or PM for this project.",
    )

    # ── Internal Approval (PM / BA Manager) ──────────────────
    pm_approved = fields.Boolean(
        string="Internal Approved",
        default=False,
        tracking=True,
        copy=False,
        help="Indicates that PM or BA Manager has reviewed and approved this FSD internally.",
    )
    pm_approver_id = fields.Many2one(
        "res.users",
        string="Internal Approver",
        readonly=True,
        copy=False,
        tracking=True,
    )
    pm_approval_date = fields.Datetime(
        string="Internal Approval Date",
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ── Customer Sign-off (Final Approval) ───────────────────
    approver_id = fields.Many2one(
        "res.users",
        string="Final Approver",
        tracking=True,
    )
    approval_date = fields.Date(
        string="Final Approval Date",
        tracking=True,
    )

    # ── Signature ────────────────────────────────────────────
    customer_signature = fields.Binary(
        string="Customer Signature",
    )
    customer_signer_name = fields.Char(string="Signer Name")
    customer_signer_title = fields.Char(string="Signer Title")
    sign_date = fields.Date(string="Sign Date")
    signer_ids = fields.Many2many(
        "res.partner",
        "ba_fsd_signer_rel",
        "fsd_id",
        "partner_id",
        string="Authorized Signers",
        help="Portal users authorized to sign this FSD",
    )

    # ── Content ──────────────────────────────────────────────
    content = fields.Html(
        string="FSD Content",
        sanitize=False,
    )

    # ── Portal ───────────────────────────────────────────────
    portal_share_token = fields.Char(
        string="Portal Token",
        copy=False,
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )

    # ── Content from linked knowledge pages ──────────────────
    fitgap_page_content = fields.Html(
        string="FIT-GAP Content",
        compute="_compute_fitgap_page_content",
        sanitize=False,
    )
    fsd_page_content = fields.Html(
        string="Knowledge Content",
        compute="_compute_fsd_page_content",
        sanitize=False,
    )

    # ── Customer Email Template & Preview ─────────────────────
    customer_template_id = fields.Many2one(
        "mail.template",
        string="Customer Email Template",
        domain="[('model', '=', 'ba.fsd')]",
        help="Template used when sending FSD to customer for sign-off. "
             "If empty, the default 'FSD Signature Request' template is used.",
    )
    customer_preview_html = fields.Html(
        string="Email Preview",
        compute="_compute_customer_preview_html",
        sanitize=False,
    )

    # ── Computes ─────────────────────────────────────────────
    @api.depends("feature_ids")
    def _compute_feature_count(self):
        for rec in self:
            rec.feature_count = len(rec.feature_ids)

    @api.depends("feature_ids.planned_hours")
    def _compute_total_planned_hours(self):
        for rec in self:
            rec.total_planned_hours = sum(rec.feature_ids.mapped("planned_hours"))

    @api.depends("state", "pm_approved")
    def _compute_is_locked(self):
        for rec in self:
            rec.is_locked = rec.pm_approved or rec.state in ("pending_signoff", "approved")

    def _compute_current_roles(self):
        """Compute project-level roles for the current user."""
        uid = self.env.uid
        for rec in self:
            proj = rec.project_id
            rec.current_is_ba_manager = proj.ba_manager_id.id == uid if proj.ba_manager_id else False
            rec.current_is_pm = proj.user_id.id == uid if proj.user_id else False
            rec.current_is_ba_user = uid in proj.ba_user_ids.ids if proj.ba_user_ids else False
            rec.current_is_developer = uid in proj.ba_developer_ids.ids if proj.ba_developer_ids else False
            rec.current_can_approve = rec.current_is_ba_manager or rec.current_is_pm

    def _check_role(self, roles):
        """Check if current user has one of the specified roles for this record's project.
        Args:
            roles: list of role strings: 'ba_manager', 'pm', 'ba_user', 'developer'
        Returns: True if user has at least one of the specified roles.
        """
        self.ensure_one()
        uid = self.env.uid
        proj = self.project_id
        if 'ba_manager' in roles and proj.ba_manager_id.id == uid:
            return True
        if 'pm' in roles and proj.user_id.id == uid:
            return True
        if 'ba_user' in roles and uid in proj.ba_user_ids.ids:
            return True
        if 'developer' in roles and uid in proj.ba_developer_ids.ids:
            return True
        # Superuser always has access
        if self.env.is_superuser():
            return True
        return False

    @api.depends("fitgap_id.document_page_id.content")
    def _compute_fitgap_page_content(self):
        for rec in self:
            if rec.fitgap_id and rec.fitgap_id.document_page_id:
                rec.fitgap_page_content = rec.fitgap_id.document_page_id.content
            else:
                rec.fitgap_page_content = False

    @api.depends("knowledge_template_id", "document_page_id.content",
                 "name", "project_id", "partner_id", "fitgap_module",
                 "feature_ids", "feature_ids.name", "feature_ids.planned_hours")
    def _compute_fsd_page_content(self):
        """Live preview of knowledge template, or fallback to saved content."""
        for rec in self:
            template = rec.knowledge_template_id
            if not template:
                template = self.env.ref(
                    "adecsol_ba.knowledge_tpl_fsd",
                    raise_if_not_found=False,
                )
            if template and rec.id:
                try:
                    rec.fsd_page_content = template._render_field(
                        "body_html", [rec.id]
                    )[rec.id]
                except (ValueError, KeyError):
                    # Fallback: template render failed — use saved content
                    rec.fsd_page_content = rec.document_page_id.content if rec.document_page_id else False
            elif rec.document_page_id:
                rec.fsd_page_content = rec.document_page_id.content
            else:
                rec.fsd_page_content = False

    @api.depends("customer_template_id", "name", "project_id", "partner_id",
                 "feature_ids", "total_planned_hours", "feature_count")
    def _compute_customer_preview_html(self):
        """Live preview of customer email template."""
        for rec in self:
            template = rec.customer_template_id
            if not template:
                template = self.env.ref(
                    "adecsol_ba.mail_template_fsd_signoff",
                    raise_if_not_found=False,
                )
            if template and rec.id:
                try:
                    rec.customer_preview_html = template._render_field(
                        "body_html", [rec.id]
                    )[rec.id]
                except (ValueError, KeyError):
                    rec.customer_preview_html = False
            else:
                rec.customer_preview_html = False

    # _open_template_preview, _sync_knowledge_from_template,
    # action_open_knowledge_page, action_preview_knowledge_document
    # → inherited from ba.knowledge.mixin

    def action_preview_knowledge_template(self):
        """Preview the Knowledge template in a popup."""
        self.ensure_one()
        template = self.knowledge_template_id or self.env.ref(
            "adecsol_ba.knowledge_tpl_fsd", raise_if_not_found=False
        )
        return self._open_template_preview(template, _("Knowledge Template Preview"))

    def action_preview_customer_template(self):
        """Preview the Customer Email template in a popup."""
        self.ensure_one()
        template = self.customer_template_id or self.env.ref(
            "adecsol_ba.mail_template_fsd_signoff", raise_if_not_found=False
        )
        return self._open_template_preview(template, _("Customer Email Preview"))



    # ══════════════════════════════════════════════════════════
    #  Actions
    # ══════════════════════════════════════════════════════════

    def action_pm_approve(self):
        """Internal approval by PM or BA Manager.
        Sets pm_approved=True and records who approved.
        Required before sending to customer.
        """
        self.ensure_one()
        if not self._check_role(['ba_manager', 'pm']):
            raise UserError(_("Only the BA Manager or Project Manager of this project can approve the FSD internally."))
        if not self.feature_ids:
            raise UserError(_("At least one feature is required before internal approval."))
        self.action_sync_to_knowledge()
        self.write({
            "pm_approved": True,
            "pm_approver_id": self.env.uid,
            "pm_approval_date": fields.Datetime.now(),
        })
        self.message_post(
            body=Markup(
                f"✅ Internal approval by <b>{self.env.user.name}</b>. "
                f"FSD is ready to be sent to customer for sign-off."
            ),
            subtype_xmlid="mail.mt_comment",
        )

    def action_revoke_approval(self):
        """Revoke internal approval (PM / BA Manager).
        Allows re-editing the FSD.
        """
        self.ensure_one()
        if not self._check_role(['ba_manager', 'pm']):
            raise UserError(_("Only the BA Manager or Project Manager of this project can revoke the internal approval."))
        if self.state != "draft":
            raise UserError(_("Cannot revoke approval once FSD has been sent to customer."))
        self.write({
            "pm_approved": False,
            "pm_approver_id": False,
            "pm_approval_date": False,
        })
        self.message_post(
            body=Markup(
                f"↩ Internal approval revoked by <b>{self.env.user.name}</b>. "
                f"FSD is back in editable draft state."
            ),
            subtype_xmlid="mail.mt_comment",
        )

    def action_send_for_signoff(self):
        """Send FSD to customer for sign-off.
        Requires internal approval first.
        Allowed: BA Manager only.
        """
        for rec in self:
            if not rec._check_role(['ba_manager']):
                raise UserError(_("Only the BA Manager of project '%s' can send FSD for customer sign-off.") % rec.project_id.name)
            if not rec.pm_approved:
                raise UserError(
                    _("FSD '%s' must be internally approved by PM or BA Manager before sending to customer.")
                    % rec.name
                )
            if not rec.feature_ids:
                raise UserError(_("At least one feature is required before sending for sign-off."))
            if not rec.portal_share_token:
                rec.portal_share_token = self.env["ir.sequence"].next_by_code(
                    "ba.fsd.token"
                ) or str(uuid.uuid4()).replace("-", "")[:16]
            rec.state = "pending_signoff"
            rec.message_post(
                body=Markup(
                    f"📧 FSD sent to customer for sign-off by <b>{self.env.user.name}</b>."
                ),
                subtype_xmlid="mail.mt_comment",
            )
            # Use selected template or fallback to default
            template = rec.customer_template_id or self.env.ref(
                "adecsol_ba.mail_template_fsd_signoff", raise_if_not_found=False
            )
            if template:
                template.send_mail(rec.id, force_send=True)
            # Auto-advance project BA phase
            if rec.project_id:
                rec.project_id._auto_advance_ba_step()

    def action_final_approve(self):
        """Final approval after customer signs.
        Locks the FSD entirely and creates handover tasks.
        Allowed: BA Manager only.
        """
        self.ensure_one()
        if not self._check_role(['ba_manager']):
            raise UserError(_("Only the BA Manager of this project can finalize FSD approval."))
        self.action_sync_to_knowledge()
        self.write({
            "state": "approved",
            "approver_id": self.env.uid,
            "approval_date": fields.Date.context_today(self),
        })
        self.message_post(
            body=Markup(
                f"🔒 FSD finalized by <b>{self.env.user.name}</b>. "
                f"Document is now locked. Handover tasks will be created."
            ),
            subtype_xmlid="mail.mt_comment",
        )
        self.action_create_handover()
        # Auto-advance project BA phase
        if self.project_id:
            self.project_id._auto_advance_ba_step()

    def action_reset_draft(self):
        """Reset to draft. Allowed: BA Manager only."""
        for rec in self:
            if not rec._check_role(['ba_manager']):
                raise UserError(_("Only the BA Manager of this project can reset an FSD document to draft."))
        self.write({
            "state": "draft",
            "pm_approved": False,
            "pm_approver_id": False,
            "pm_approval_date": False,
            "customer_signature": False,
            "customer_signer_name": False,
            "sign_date": False,
        })

    def action_sign(self):
        """Called when customer signs (backend or portal)."""
        for rec in self:
            # Authorization: only authorized signers or BA Manager/PM can trigger signing
            if rec.signer_ids and self.env.user.partner_id not in rec.signer_ids:
                if not rec._check_role(['ba_manager', 'pm']):
                    raise UserError(_("You are not authorized to sign this FSD."))
            rec.action_sync_to_knowledge()
            rec.write({
                "state": "approved",
                "sign_date": fields.Date.context_today(self),
                "approver_id": self.env.uid,
                "approval_date": fields.Date.context_today(self),
            })
            rec.message_post(
                body=Markup(
                    f"✅ Customer <b>{rec.customer_signer_name or 'N/A'}</b> "
                    f"has signed the FSD. The Dev team can start implementation."
                ),
                subtype_xmlid="mail.mt_comment",
            )

    # ── Handover link ───────────────────────────────────────────
    handover_ids = fields.One2many(
        "ba.handover",
        "fsd_id",
        string="Technical Handovers",
    )
    handover_count = fields.Integer(
        compute="_compute_handover_count"
    )

    def _compute_handover_count(self):
        for rec in self:
            rec.handover_count = len(rec.handover_ids)

    def action_create_handover(self):
        """Create one Handover per feature in the FSD."""
        self.ensure_one()
        if not self.feature_ids:
            raise UserError(_("No features found in the FSD to create handovers."))
        Handover = self.env["ba.handover"]
        created = Handover
        for feature in self.feature_ids:
            existing = Handover.search([
                ('fsd_id', '=', self.id),
                ('feature_id', '=', feature.id),
            ], limit=1)
            if existing:
                continue
            created |= Handover.create({
                "name": f"Handover: {feature.name}",
                "project_id": self.project_id.id,
                "fsd_id": self.id,
                "feature_id": feature.id,
                "planned_hours": feature.planned_hours,
            })
        if not created:
            raise UserError(_("All features already have a corresponding handover."))
        if len(created) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "ba.handover",
                "res_id": created.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"Technical Handover — {self.name}",
            "res_model": "ba.handover",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
            "target": "current",
        }

    def action_open_handover_tasks(self):
        self.ensure_one()
        if len(self.handover_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": f"Technical Handover — {self.name}",
                "res_model": "ba.handover",
                "view_mode": "form",
                "res_id": self.handover_ids[0].id,
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"Technical Handover — {self.name}",
            "res_model": "ba.handover",
            "view_mode": "list,form",
            "domain": [("id", "in", self.handover_ids.ids)],
            "target": "current",
        }

    def action_sync_to_knowledge(self):
        """Sync/generate FSD content to linked Knowledge (document.page)."""
        for rec in self:
            template = rec.knowledge_template_id
            if not template:
                template = self.env.ref(
                    "adecsol_ba.knowledge_tpl_fsd",
                    raise_if_not_found=False,
                )
            if template:
                rec._sync_knowledge_from_template(template, doc_type="fsd")
            else:
                # Fallback: hardcoded HTML
                project_name = rec.project_id.name if rec.project_id else "N/A"
                partner_name = rec.partner_id.name if rec.partner_id else "N/A"
                module_name = rec.fitgap_module or "N/A"

                if rec.feature_ids:
                    rows = ""
                    for feat in rec.feature_ids:
                        rows += (
                            f"<tr>"
                            f"<td>{feat.name or ''}</td>"
                            f"<td>{feat.description or ''}</td>"
                            f"<td>{feat.logic_description or ''}</td>"
                            f"<td>{feat.planned_hours or 0:.1f}h</td>"
                            f"</tr>"
                        )
                    features_html = Markup(
                        "<table border='1' style='border-collapse:collapse;width:100%'>"
                        "<thead><tr>"
                        "<th>Feature</th><th>Description</th><th>Logic</th><th>Est. Hours</th>"
                        "</tr></thead>"
                        f"<tbody>{rows}</tbody></table>"
                    )
                else:
                    features_html = Markup("<p><em>(No features yet)</em></p>")

                body = Markup(
                    f"<h2>\U0001f4c4 FSD: {rec.name}</h2>"
                    f"<p><strong>Project:</strong> {project_name}</p>"
                    f"<p><strong>Customer:</strong> {partner_name}</p>"
                    f"<p><strong>Module:</strong> {module_name}</p>"
                    f"<hr/>"
                    f"<h3>\U0001f4cb Feature List</h3>"
                    f"{features_html}"
                )

                parent_id = (
                    rec.project_id.document_page_category_id.id
                    if rec.project_id and rec.project_id.document_page_category_id
                    else False
                )
                project_id_val = rec.project_id.id if rec.project_id else False
                draft_summary = f"FSD \u2014 {project_name} / {partner_name}"

                if rec.document_page_id:
                    rec.document_page_id.write({
                        "content": body,
                        "draft_name": "1.0",
                        "draft_summary": draft_summary,
                        "project_id": project_id_val,
                        "parent_id": parent_id or rec.document_page_id.parent_id.id,
                    })
                else:
                    new_page = self.env["document.page"].create({
                        "name": f"FSD: {rec.name}",
                        "doc_type": "fsd",
                        "project_id": project_id_val,
                        "parent_id": parent_id,
                        "draft_name": "1.0",
                        "draft_summary": draft_summary,
                        "content": body,
                    })
                    rec.document_page_id = new_page.id
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Successful"),
                "message": _("FSD content has been updated in Knowledge."),
                "type": "success",
                "sticky": False,
            },
        }

    # _sync_knowledge_from_template → inherited from ba.knowledge.mixin
