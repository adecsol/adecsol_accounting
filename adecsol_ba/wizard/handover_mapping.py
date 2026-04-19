# -*- coding: utf-8 -*-
# D.2 — Wizard: Import FSD Features → Handover Lines

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BAHandoverMappingWizard(models.TransientModel):
    """Wizard to import FSD features into Handover lines."""

    _name = "ba.handover.mapping.wizard"
    _description = "Import FSD → Handover Mapping"

    task_id = fields.Many2one(
        "project.task",
        string="Handover Task",
        required=True,
    )
    fsd_id = fields.Many2one(
        "ba.fsd",
        string="Source FSD Document",
        required=True,
    )
    feature_ids = fields.Many2many(
        "ba.fsd.feature",
        string="Features to import",
    )
    import_all = fields.Boolean(
        string="Import All",
        default=True,
    )

    @api.onchange("fsd_id")
    def _onchange_fsd_id(self):
        if self.fsd_id:
            self.feature_ids = self.fsd_id.feature_ids
        else:
            self.feature_ids = False

    @api.onchange("import_all")
    def _onchange_import_all(self):
        if self.import_all and self.fsd_id:
            self.feature_ids = self.fsd_id.feature_ids

    def action_import(self):
        """Create handover lines from selected FSD features."""
        self.ensure_one()
        if self.task_id.handover_state == "confirmed":
            raise UserError(
                _("Handover is confirmed. Reopen draft on handover task to import more from FSD.")
            )
        features = self.feature_ids if not self.import_all else self.fsd_id.feature_ids

        vals_list = []
        for feat in features:
            desc = (feat.description or "").strip()
            vals_list.append(
                {
                    "task_id": self.task_id.id,
                    "sequence": feat.sequence,
                    "feature_name": feat.name,
                    "priority": feat.priority,
                    "planned_hours": feat.planned_hours,
                    "source_feature_id": feat.id,
                    "objective": "\n\n".join(
                        p
                        for p in (
                            desc,
                            f"Module: {feat.module_name or 'N/A'}",
                            f"FIT/GAP: {feat.fit_gap}",
                            (feat.note or "").strip(),
                        )
                        if p
                    ),
                }
            )

        if vals_list:
            self.env["ba.handover.line"].create(vals_list)

        # Update handover_fsd_id on the task
        self.task_id.handover_fsd_id = self.fsd_id.id

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Import Successful",
                "message": f"Imported {len(vals_list)} features from FSD to handover.",
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
