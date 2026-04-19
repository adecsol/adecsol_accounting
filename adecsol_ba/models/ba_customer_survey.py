# -*- coding: utf-8 -*-
# A2.CUS_SUR.01 — Customer Survey (AS-IS Analysis)

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BACustomerSurvey(models.Model):
    """Customer Survey — AS-IS Analysis (A2.CUS_SUR.01)."""

    _name = "ba.customer.survey"
    _description = "Customer Survey (AS-IS)"
    _inherit = ["mail.thread", "mail.activity.mixin", "ba.knowledge.mixin"]
    _order = "send_date desc, id desc"

    name = fields.Char(
        string="Survey Title",
        required=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        required=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        tracking=True,
    )
    send_date = fields.Date(
        string="Send Date",
        tracking=True,
    )
    result_date = fields.Date(
        string="Response Date",
        tracking=True,
    )

    attachment_template_ids = fields.Many2many(
        "ir.attachment",
        "ba_survey_template_rel",
        "survey_id",
        "attachment_id",
        string="Template Files (Send to Customer)",
    )
    attachment_responded_ids = fields.Many2many(
        "ir.attachment",
        "ba_survey_responded_rel",
        "survey_id",
        "attachment_id",
        string="Response Files (Filled by Customer)",
        copy=False,
    )
    survey_result = fields.Html(
        string="Survey Result",
        sanitize=False,
        help="Summary of analysis results from customer responses.",
    )
    document_page_id = fields.Many2one(
        "document.page",
        string="Knowledge Article",
    )
    knowledge_template_id = fields.Many2one(
        "mail.template",
        string="Knowledge Template",
        domain="[('model', '=', 'ba.customer.survey')]",
        help="Mail template used to render the Knowledge page content.",
    )
    tobe_page_id = fields.Many2one(
        "document.page",
        string="TO-BE Page",
        domain="[('doc_type','=','tobe')]",
    )
    tobe_count = fields.Integer(
        compute="_compute_tobe_count",
        string="TO-BE",
    )

    @api.depends("tobe_page_id")
    def _compute_tobe_count(self):
        for rec in self:
            rec.tobe_count = 1 if rec.tobe_page_id else 0

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if self.project_id and self.project_id.partner_id:
            self.partner_id = self.project_id.partner_id

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.industry_id:
            items = self.partner_id.industry_id.survey_profile_item_ids
            if items:
                attachments = items.mapped("attachment_ids")
                if attachments:
                    self.attachment_template_ids = [(6, 0, attachments.ids)]

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("responded", "Responded"),
            ("confirmed", "Confirmed"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    attachment_count = fields.Integer(
        compute="_compute_attachment_count",
        string="Files",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )

    @api.depends("attachment_template_ids", "attachment_responded_ids")
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_template_ids) + len(rec.attachment_responded_ids)

    # ── ORM Override ─────────────────────────────────────────
    def write(self, vals):
        """Auto-transition to 'responded' when response files are added."""
        result = super().write(vals)
        if "attachment_responded_ids" in vals:
            auto_respond = self.filtered(
                lambda r: r.state in ("draft", "sent") and r.attachment_responded_ids
            )
            if auto_respond:
                super(BACustomerSurvey, auto_respond).write({
                    "state": "responded",
                    "result_date": fields.Date.context_today(self),
                })
        return result

    # ── Actions ──────────────────────────────────────────────
    def action_send_survey(self):
        """Send the survey to the customer via email."""
        self.ensure_one()
        template = self.env.ref(
            "adecsol_ba.mail_template_customer_survey", raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
        self.write({"state": "sent", "send_date": fields.Date.context_today(self)})

    def action_confirm(self):
        """Confirm survey results, sync Knowledge and lock form."""
        self.ensure_one()
        self.action_post_to_knowledge()
        self.write({"state": "confirmed"})
        # Auto-advance project BA phase
        if self.project_id:
            self.project_id._auto_advance_ba_step()

    def action_mark_responded(self):
        self.write({
            "state": "responded",
            "result_date": fields.Date.context_today(self),
        })

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_create_tobe(self):
        """Create a TO-BE page from a confirmed survey."""
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("TO-BE can only be created from a confirmed survey."))
        if self.tobe_page_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "document.page",
                "res_id": self.tobe_page_id.id,
                "view_mode": "form",
                "target": "current",
            }
        partner_name = self.partner_id.name or "Customer"
        body = Markup()
        parent_id = (
            self.project_id.document_page_category_id.id
            if self.project_id and self.project_id.document_page_category_id
            else False
        )
        tobe_page = self.env["document.page"].create({
            "name": f"TO-BE — {self.project_id.name} / {partner_name}",
            "doc_type": "tobe",
            "project_id": self.project_id.id if self.project_id else False,
            "parent_id": parent_id,
            "draft_name": "1.0",
            "draft_summary": f"TO-BE Design from survey: {self.name}",
            "content": body,
        })
        self.tobe_page_id = tobe_page.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "document.page",
            "res_id": tobe_page.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_post_to_knowledge(self):
        """Create or update a Document Page (Knowledge) from survey_result."""
        for rec in self:
            template = rec.knowledge_template_id
            if not template:
                template = self.env.ref(
                    "adecsol_ba.knowledge_tpl_survey",
                    raise_if_not_found=False,
                )
            if template:
                rec._sync_knowledge_from_template(template, doc_type="survey")
            else:
                # Fallback: hardcoded HTML
                partner_name = rec.partner_id.name or "Customer"
                send_date = str(rec.send_date) if rec.send_date else "N/A"
                result_date = str(rec.result_date) if rec.result_date else "N/A"
                body = Markup(
                    f"<strong>📋 Customer Survey:</strong> {rec.name}<br/>"
                    f"<strong>Project:</strong> {rec.project_id.name}<br/>"
                    f"<strong>Customer:</strong> {partner_name}<br/>"
                    f"<strong>Send Date:</strong> {send_date}<br/>"
                    f"<strong>Response Date:</strong> {result_date}<br/>"
                    f"<hr/>{rec.survey_result or ''}"
                )
                parent_id = (
                    rec.project_id.document_page_category_id.id
                    if rec.project_id and rec.project_id.document_page_category_id
                    else False
                )
                if not rec.document_page_id:
                    doc = self.env["document.page"].create({
                        "name": f"Customer Survey: {rec.name}",
                        "project_id": rec.project_id.id if rec.project_id else False,
                        "parent_id": parent_id,
                        "draft_name": "1.0",
                        "draft_summary": f"Survey Result — {partner_name} / {send_date}",
                        "content": body,
                    })
                    rec.document_page_id = doc.id
                else:
                    rec.document_page_id.write({
                        "content": body,
                        "draft_name": "1.0",
                        "draft_summary": f"Updated survey result — {result_date}",
                        "project_id": rec.project_id.id if rec.project_id else False,
                        "parent_id": parent_id or rec.document_page_id.parent_id.id,
                    })

    # _open_template_preview, _sync_knowledge_from_template,
    # action_open_knowledge_page, action_preview_knowledge_document
    # → inherited from ba.knowledge.mixin

    def action_preview_knowledge_template(self):
        """Preview the Knowledge template in a popup."""
        self.ensure_one()
        template = self.knowledge_template_id or self.env.ref(
            "adecsol_ba.knowledge_tpl_survey", raise_if_not_found=False
        )
        return self._open_template_preview(template, _("Knowledge Template Preview"))
