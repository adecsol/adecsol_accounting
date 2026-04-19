# -*- coding: utf-8 -*-
# E1.WBS.01 — WBS Checklist Item

from odoo import fields, models


class BAWBSChecklist(models.Model):
    """Checklist item for WBS Task (E1.WBS.01)."""

    _name = "ba.wbs.checklist"
    _description = "WBS Checklist Item"
    _order = "sequence, id"

    task_id = fields.Many2one(
        "project.task",
        string="WBS Task",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Name", required=True)
    assignee_id = fields.Many2one(
        "res.users",
        string="Assignee",
    )
    deadline = fields.Date(string="Deadline")
    state = fields.Selection(
        [
            ("todo", "To Do"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ],
        string="Status",
        default="todo",
    )
    description = fields.Text(string="Description")
    priority = fields.Selection(
        [
            ("critical", "Critical"),
            ("major", "Major"),
            ("minor", "Minor"),
        ],
        string="Priority",
        default="major",
    )
