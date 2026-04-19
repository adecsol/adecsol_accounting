# -*- coding: utf-8 -*-
# Shared mixin — DRY template preview + knowledge sync logic

from odoo import _, models
from odoo.exceptions import UserError


class BAKnowledgeMixin(models.AbstractModel):
    """Shared logic for models that sync content to Knowledge (document.page)
    and support mail.template preview popups.

    Inheriting model MUST have:
      - document_page_id  (Many2one → document.page)
      - project_id        (Many2one → project.project)
    """

    _name = "ba.knowledge.mixin"
    _description = "BA Knowledge Sync Mixin"

    def _open_template_preview(self, template, title="Template Preview"):
        """Render a mail.template and open it in a preview popup."""
        self.ensure_one()
        if not template:
            raise UserError(_("No template selected."))
        body = template._render_field("body_html", [self.id])[self.id]
        subject = template._render_field("subject", [self.id])[self.id]
        wizard = self.env["ba.template.preview"].create({
            "preview_html": body,
            "preview_subject": subject,
        })
        return {
            "name": title,
            "type": "ir.actions.act_window",
            "res_model": "ba.template.preview",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _sync_knowledge_from_template(self, template, doc_type="other"):
        """Render a mail.template and create/update the linked Knowledge page."""
        self.ensure_one()
        body = template._render_field("body_html", [self.id])[self.id]
        page_name = template._render_field("subject", [self.id])[self.id]
        parent_id = (
            self.project_id.document_page_category_id.id
            if self.project_id and self.project_id.document_page_category_id
            else False
        )
        project_id_val = self.project_id.id if self.project_id else False
        if self.document_page_id:
            self.document_page_id.write({
                "content": body,
                "draft_name": "1.0",
                "draft_summary": page_name,
                "project_id": project_id_val,
                "parent_id": parent_id or self.document_page_id.parent_id.id,
            })
        else:
            doc = self.env["document.page"].create({
                "name": page_name,
                "doc_type": doc_type,
                "project_id": project_id_val,
                "parent_id": parent_id,
                "draft_name": "1.0",
                "draft_summary": page_name,
                "content": body,
            })
            self.document_page_id = doc.id

    def action_preview_knowledge_document(self):
        """Preview the synced Knowledge document content in a popup."""
        self.ensure_one()
        if not self.document_page_id:
            raise UserError(_("No Knowledge document synced yet."))
        wizard = self.env["ba.template.preview"].create({
            "preview_html": self.document_page_id.content,
            "preview_subject": self.document_page_id.name,
        })
        return {
            "name": _("Knowledge Document Preview"),
            "type": "ir.actions.act_window",
            "res_model": "ba.template.preview",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_knowledge_page(self):
        """Open the linked Knowledge page."""
        self.ensure_one()
        if not self.document_page_id:
            return
        return {
            "type": "ir.actions.act_window",
            "res_model": "document.page",
            "res_id": self.document_page_id.id,
            "view_mode": "form",
            "target": "current",
        }
