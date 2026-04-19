# -*- coding: utf-8 -*-
# B.1 — TO-BE Design: Extend document.page

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentPage(models.Model):
    _inherit = "document.page"

    doc_type = fields.Selection(
        [
            ("mom", "Meeting Minutes (MoM)"),
            ("fsd", "FSD Document"),
            ("survey", "Survey"),
            ("tobe", "TO-BE Design"),
            ("fitgap", "FIT-GAP Analysis"),
            ("other", "Other"),
        ],
        string="Document Type",
        default="other",
    )
    drawio_url = fields.Char(
        string="Draw.io / Lucidchart URL",
        help="Paste the embed URL of your Draw.io or Lucidchart diagram.",
    )
    drawio_embed = fields.Html(
        string="Embedded Diagram",
        compute="_compute_drawio_embed",
        sanitize=False,
    )

    fitgap_ids = fields.One2many(
        "ba.fitgap",
        "tobe_page_id",
        string="Linked FIT-GAP",
    )
    fitgap_count = fields.Integer(
        compute="_compute_fitgap_count",
        string="FIT-GAP Count",
    )

    @api.depends("fitgap_ids")
    def _compute_fitgap_count(self):
        for rec in self:
            rec.fitgap_count = len(rec.fitgap_ids)

    @api.depends("drawio_url")
    def _compute_drawio_embed(self):
        for rec in self:
            if rec.drawio_url:
                rec.drawio_embed = (
                    f'<iframe src="{rec.drawio_url}" '
                    f'width="100%" height="600" frameborder="0" '
                    f'style="border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);">'
                    f"</iframe>"
                )
            else:
                rec.drawio_embed = False

    # ── Onchange: select project → auto-fill parent_id (category) ──
    @api.onchange("project_id")
    def _onchange_project_id_set_category(self):
        """Auto-fill parent_id (category) when selecting a project."""
        if self.project_id and self.project_id.document_page_category_id:
            # Only fill if parent_id is empty or not this project's category
            category = self.project_id.document_page_category_id
            if not self.parent_id or self.parent_id != category:
                self.parent_id = category

    # ── CRUD: auto-fill parent_id when there is a project but missing category ──
    def _get_category_from_project(self, project_id_val):
        """Return project's category ID, or False."""
        if not project_id_val:
            return False
        project = self.env["project.project"].browse(project_id_val)
        if project.document_page_category_id:
            return project.document_page_category_id.id
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """If project_id exists but no parent_id → auto-fill parent_id = project's category."""
        for vals in vals_list:
            project_id = vals.get("project_id")
            if project_id and not vals.get("parent_id"):
                category_id = self._get_category_from_project(project_id)
                if category_id:
                    vals["parent_id"] = category_id
        return super().create(vals_list)

    def write(self, vals):
        """If project_id is updated without passing parent_id → auto-fill if missing."""
        if "project_id" in vals and "parent_id" not in vals:
            new_category = self._get_category_from_project(vals.get("project_id"))
            if new_category:
                vals = dict(vals, parent_id=new_category)
        return super().write(vals)

    def _create_history(self, vals):
        """Override: Block approval submission if TO-BE page has no diagram link."""
        for rec in self:
            if rec.doc_type == "tobe" and not rec.drawio_url:
                if rec.is_approval_required:
                    raise UserError(
                        _("TO-BE page must have an attached diagram link (Draw.io/Lucidchart) "
                          "before requesting approval.")
                    )
        return super()._create_history(vals)

    # ── Actions ──────────────────────────────────────────────
    def action_create_fitgap(self):
        """Create new ba.fitgap record linked to this TO-BE page and open form."""
        self.ensure_one()
        if self.doc_type != "tobe":
            raise UserError(_("Can only create FIT-GAP from TO-BE page."))
        # Get project_id from the project field (via document_page_project)
        project_id = self.project_id.id if self.project_id else False
        fitgap = self.env["ba.fitgap"].create({
            "name": f"FIT-GAP Analysis from {self.name}",
            "tobe_page_id": self.id,
            "project_id": project_id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "ba.fitgap",
            "res_id": fitgap.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_fitgap_list(self):
        """Open FIT-GAP list linked with this TO-BE."""
        self.ensure_one()
        if self.fitgap_count == 1:
            return {
                "type": "ir.actions.act_window",
                "name": f"FIT-GAP — {self.name}",
                "res_model": "ba.fitgap",
                "view_mode": "form",
                "res_id": self.fitgap_ids[0].id,
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"FIT-GAP — {self.name}",
            "res_model": "ba.fitgap",
            "view_mode": "list,form",
            "domain": [("tobe_page_id", "=", self.id)],
            "target": "current",
        }
