# -*- coding: utf-8 -*-
# D2.TRAN_DEV.01 — Handover Line (technical handover detail)

from odoo import fields, models


class BAHandoverLine(models.Model):
    """Technical Handover Detail Line for Developer (D2.TRAN_DEV.01)."""

    _name = "ba.handover.line"
    _description = "Technical Handover Line"
    _order = "sequence, id"

    handover_id = fields.Many2one(
        "ba.handover",
        string="Handover",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    task_id = fields.Many2one(
        "project.task",
        string="Dev Task",
        help="Manual reference to a dev task (Work Content).",
    )
    generated_task_id = fields.Many2one(
        "project.task",
        string="Generated Subtask",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="Subtask auto-created when handover is confirmed.",
    )

    # ── Objective ───────────────────────────────────────────
    objective = fields.Text(
        string="Objective (Proposed Feature)",
    )

    # ── ISO Compliance ───────────────────────────────────────
    iso_9001 = fields.Text(
        string="ISO 9001 Compliance",
    )
    iso_27001 = fields.Text(
        string="ISO 27001 Compliance",
    )

    # ── Task & Technical Details ─────────────────────────────
    task_detail = fields.Html(
        string="Task Detail (Dev)",
        sanitize=False,
    )
    odoo_std_module = fields.Char(
        string="Odoo V18 Std Module & Link",
        help="Standard Odoo v18 module name and docs link.",
    )
    oca_module = fields.Char(
        string="OCA Module & Link",
        help="OCA module name and GitHub link.",
    )
    custom_work = fields.Html(
        string="Custom Work (Dev Tasks)",
        sanitize=False,
        help="Detailed custom development tasks.",
    )
    depend = fields.Char(
        string="Dependencies",
        help="Required modules (comma-separated).",
    )
    inherit_model = fields.Char(
        string="Inherit (Model/Class)",
        help="Model or Class to inherit.",
    )
    community_note = fields.Text(
        string="Community / Open Source Notes",
    )
    adec_module = fields.Char(
        string="ADEC Internal Module",
        help="Internal ADEC module name if applicable.",
    )
    note = fields.Text(string="Notes")

    # ── Legacy fields (backward compat) ──────────────────────
    feature_name = fields.Char(string="Feature")
    priority = fields.Selection(
        [
            ("critical", "Critical"),
            ("major", "Major"),
            ("minor", "Minor"),
        ],
        string="Priority",
        default="major",
    )
    planned_hours = fields.Float(string="Estimated Hours")
