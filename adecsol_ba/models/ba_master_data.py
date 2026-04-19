# -*- coding: utf-8 -*-
# D1.MasterData.01 — Master Data Requirements

from odoo import api, fields, models


class BAMasterDataLine(models.Model):
    """Master Data requirement detail line."""

    _name = "ba.master.data.line"
    _description = "Master Data Checklist Line"
    _order = "sequence, id"

    master_data_id = fields.Many2one(
        "ba.master.data",
        string="Master Data",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Requirement", required=True)
    description = fields.Text(string="Description")
    req_type = fields.Selection(
        [
            ("available", "Available"),
            ("custom", "Custom"),
            ("integration", "Integration"),
        ],
        string="Type",
        default="available",
    )
    solution = fields.Text(string="Solution")
    note = fields.Text(string="Notes")


class BAMasterData(models.Model):
    """Master Data Requirements Management (D1.MasterData.01)."""

    _name = "ba.master.data"
    _description = "Master Data Requirement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Requirement Name", required=True, tracking=True)
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        required=True,
        tracking=True,
    )
    object_type = fields.Selection(
        [
            ("partner", "Partner (res.partner)"),
            ("product", "Product (product.template)"),
            ("account", "Account (account.account)"),
            ("other", "Other"),
        ],
        string="Data Object",
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        "ba.master.data.line",
        "master_data_id",
        string="Field List",
    )
    import_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("validated", "Validated"),
            ("imported", "Imported"),
            ("error", "Error"),
        ],
        string="Import Status",
        default="pending",
        tracking=True,
    )
    task_id = fields.Many2one(
        "project.task",
        string="Linked Task",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Attachments",
    )
    note = fields.Html(string="Notes")
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )

    def action_validate(self):
        self.write({"import_status": "validated"})

    def action_mark_imported(self):
        self.write({"import_status": "imported"})

    def action_mark_error(self):
        self.write({"import_status": "error"})

    def action_reset(self):
        self.write({"import_status": "pending"})
