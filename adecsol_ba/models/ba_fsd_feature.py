# -*- coding: utf-8 -*-
# C1.FSD.01 — FSD Feature Line

from odoo import fields, models


class BAFSDFeature(models.Model):
    """Feature detail line inside an FSD document."""

    _name = "ba.fsd.feature"
    _description = "FSD Feature Line"
    _order = "sequence, id"

    fsd_id = fields.Many2one(
        "ba.fsd",
        string="FSD Document",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="No.", default=10)
    name = fields.Char(string="Feature Name", required=True)
    description = fields.Text(string="Detailed Description")
    logic_description = fields.Text(
        string="Logic",
        help="Business logic description for this feature.",
    )
    api_specification = fields.Text(
        string="API",
        help="API endpoint, request/response specification.",
    )
    fit_gap = fields.Selection(
        [("fit", "FIT"), ("gap", "GAP")],
        string="FIT/GAP",
        default="fit",
    )
    priority = fields.Selection(
        [
            ("critical", "Critical"),
            ("major", "Major"),
            ("minor", "Minor"),
        ],
        string="Priority",
        default="major",
    )
    planned_hours = fields.Float(string="Est. Hours (Dev)")
    module_name = fields.Char(string="Related Module")
    customer_confirmed = fields.Boolean(
        string="Customer Confirmed",
        default=False,
    )
    task_id = fields.Many2one(
        "project.task",
        string="Dev Task",
        help="Task created for Developer when feature is a GAP.",
    )
    note = fields.Text(string="Notes")
