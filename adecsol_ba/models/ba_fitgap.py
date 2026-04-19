# -*- coding: utf-8 -*-
# B2.FIT_GAP.01 — FIT-GAP Analysis

from odoo import api, fields, models, _


class BAFITGAP(models.Model):
    """FIT-GAP Analysis (B2.FIT_GAP.01)."""

    _name = "ba.fitgap"
    _description = "FIT-GAP Analysis"
    _inherit = ["mail.thread", "mail.activity.mixin", "ba.knowledge.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Analysis Name",
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
        related="project_id.partner_id",
        store=True,
        readonly=True,
        tracking=True,
    )
    document_page_id = fields.Many2one(
        "document.page",
        string="Knowledge",
    )
    knowledge_template_id = fields.Many2one(
        "mail.template",
        string="Knowledge Template",
        domain="[('model', '=', 'ba.fitgap')]",
        help="Mail template used to render the Knowledge page content.",
    )
    tobe_page_id = fields.Many2one(
        "document.page",
        string="Linked TO-BE Page",
        domain="[('doc_type','=','tobe')]",
    )
    tobe_content = fields.Html(
        string="TO-BE Content",
        related="tobe_page_id.content",
        readonly=True,
    )

    priority = fields.Selection(
        [
            ("critical", "🔴 Critical"),
            ("high", "🟠 High"),
            ("medium", "🟡 Medium"),
            ("low", "🟢 Low"),
        ],
        string="Priority",
        default="medium",
        tracking=True,
    )
    fitgap_module = fields.Char(
        string="Module",
        help="Related Odoo module.",
    )
    gap_type = fields.Selection(
        [
            ("config", "Configuration (Config)"),
            ("customization", "Customization"),
            ("new_dev", "New Development"),
            ("integration", "Integration"),
            ("report", "Report"),
            ("training", "Training"),
            ("none", "Not Applicable (FIT)"),
        ],
        string="GAP Type",
        default="none",
    )

    fit_content = fields.Html(
        string="FIT (Covered)",
        sanitize=False,
    )
    gap_content = fields.Html(
        string="GAP (To Develop)",
        sanitize=False,
    )
    note = fields.Text(
        string="Notes",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    def action_confirm(self):
        """Confirm FIT-GAP analysis and sync to Knowledge."""
        self.ensure_one()
        self.action_sync_to_knowledge()
        self.write({"state": "confirmed"})
        # Auto-advance project BA phase
        if self.project_id:
            self.project_id._auto_advance_ba_step()

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_sync_to_knowledge(self):
        """Sync FIT-GAP content to linked Knowledge page."""
        from markupsafe import Markup
        for rec in self:
            template = rec.knowledge_template_id
            if not template:
                template = self.env.ref(
                    "adecsol_ba.knowledge_tpl_fitgap",
                    raise_if_not_found=False,
                )
            if template:
                rec._sync_knowledge_from_template(template, doc_type="fitgap")
            else:
                # Fallback: hardcoded HTML
                fit_section = rec.fit_content or Markup("<p><em>(No FIT content yet)</em></p>")
                gap_section = rec.gap_content or Markup("<p><em>(No GAP content yet)</em></p>")
                project_name = rec.project_id.name if rec.project_id else "N/A"
                module_name = rec.fitgap_module or "N/A"

                body = Markup(
                    f"<h2>📋 FIT-GAP Analysis: {rec.name}</h2>"
                    f"<p><strong>Project:</strong> {project_name}</p>"
                    f"<p><strong>Module:</strong> {module_name}</p>"
                    f"<hr/>"
                    f"<h3>✅ FIT — Covered Features</h3>"
                    f"{fit_section}"
                    f"<hr/>"
                    f"<h3>🔧 GAP — Custom / Development Required</h3>"
                    f"{gap_section}"
                )

                parent_id = (
                    rec.project_id.document_page_category_id.id
                    if rec.project_id and rec.project_id.document_page_category_id
                    else False
                )

                if not rec.document_page_id:
                    doc = self.env["document.page"].create({
                        "name": f"FIT-GAP: {rec.name}",
                        "project_id": rec.project_id.id if rec.project_id else False,
                        "parent_id": parent_id,
                        "draft_name": "1.0",
                        "draft_summary": f"FIT-GAP for module {module_name}",
                        "content": body,
                        "doc_type": "fitgap",
                    })
                    rec.document_page_id = doc.id
                else:
                    rec.document_page_id.write({
                        "content": body,
                        "draft_summary": f"Updated FIT-GAP — Module {module_name}",
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
            "adecsol_ba.knowledge_tpl_fitgap", raise_if_not_found=False
        )
        return self._open_template_preview(template, _("Knowledge Template Preview"))

    def action_open_tobe_page(self):
        """Open the linked TO-BE document page."""
        self.ensure_one()
        if not self.tobe_page_id:
            return
        return {
            "type": "ir.actions.act_window",
            "res_model": "document.page",
            "res_id": self.tobe_page_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # ── FSD Link ──────────────────────────────────────────────
    fsd_ids = fields.One2many(
        "ba.fsd", "fitgap_id",
        string="Linked FSD Documents",
    )
    fsd_count = fields.Integer(
        compute="_compute_fsd_count"
    )

    def _compute_fsd_count(self):
        for rec in self:
            rec.fsd_count = len(rec.fsd_ids)

    def action_create_fsd(self):
        self.ensure_one()
        fsd = self.env["ba.fsd"].create({
            "name": f"FSD — {self.name}",
            "fitgap_id": self.id,
            "project_id": self.project_id.id,
            "document_page_id": self.document_page_id.id if self.document_page_id else False,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "ba.fsd",
            "res_id": fsd.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_fsd_list(self):
        self.ensure_one()
        if len(self.fsd_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": f"FSD — {self.name}",
                "res_model": "ba.fsd",
                "view_mode": "form",
                "res_id": self.fsd_ids[0].id,
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"FSD — {self.name}",
            "res_model": "ba.fsd",
            "view_mode": "list,form",
            "domain": [("fitgap_id", "=", self.id)],
            "target": "current",
        }
