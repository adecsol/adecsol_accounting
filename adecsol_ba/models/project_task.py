# -*- coding: utf-8 -*-
# E.1 WBS — project.task extension

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProjectTask(models.Model):
    _inherit = "project.task"

    # ══════════════════════════════════════════════════════════
    #  WBS Task (generated from ba.handover)
    # ══════════════════════════════════════════════════════════
    is_wbs = fields.Boolean(string="Is WBS Task", default=False)
    source_handover_line_id = fields.Many2one(
        "ba.handover.line",
        string="Generated from Handover Line",
        ondelete="set null",
        copy=False,
        index=True,
    )

    # ── Feature Priority ─────────────────────────────────────
    ba_feature_priority = fields.Selection(
        [
            ("critical", "Critical"),
            ("major", "Major"),
            ("minor", "Minor"),
        ],
        string="FSD Priority",
        help="Priority of the feature inherited from the FSD.",
    )

    # ── Checklist ────────────────────────────────────────────
    checklist_ids = fields.One2many(
        "ba.wbs.checklist",
        "task_id",
        string="Checklist",
    )
