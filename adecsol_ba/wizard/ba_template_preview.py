# -*- coding: utf-8 -*-
from odoo import fields, models


class BATemplatePreview(models.TransientModel):
    """Popup wizard to preview rendered mail.template content."""

    _name = "ba.template.preview"
    _description = "Template Preview"

    preview_html = fields.Html(
        string="Preview",
        sanitize=False,
        readonly=True,
    )
    preview_subject = fields.Char(
        string="Subject / Page Name",
        readonly=True,
    )
