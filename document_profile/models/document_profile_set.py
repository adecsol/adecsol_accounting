# -*- coding: utf-8 -*-
import base64
import io
import re
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DocumentProfileSet(models.Model):
    _name = "document.profile.set"
    _description = "Document Profile Set"
    _order = "name, id"

    name = fields.Char(string="Profile Set Name", required=True)
    active = fields.Boolean(
        default=True,
        string="Active",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        help="Leave empty to apply to all companies.",
    )
    dossier_code_format = fields.Char(
        string="Dossier Code Format",
        required=True,
        help="One format placeholder for the dossier sequence number "
        "(e.g. ADE.FIN.05.%02d → ADE.FIN.05.01).",
    )
    file_code_format = fields.Char(
        string="File Code Format",
        required=True,
        default="%s-%s",
        help="Two %s placeholders: dossier code and reference key (e.g. ADE.FIN.05.01-05). "
        "Used on «Files by code» lines in each dossier; other addons may use the same "
        "convention to infer file codes from report references.",
    )
    dossier_code_format_locked = fields.Boolean(
        string="Dossier Code Format Locked",
        default=False,
        help="When set, the dossier code format cannot be edited until unlocked.",
    )
    file_code_format_locked = fields.Boolean(
        string="File Code Format Locked",
        default=False,
        help="When set, the file code format cannot be edited until unlocked.",
    )
    dossier_ids = fields.One2many(
        "document.profile.dossier",
        "profile_set_id",
        string="Dossiers",
    )
    item_ids = fields.One2many(
        "document.profile.item",
        "profile_set_id",
        string="Files by Code",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for i, vals in enumerate(vals_list):
            vals_list[i] = self._strip_format_fields(dict(vals))
        return super().create(vals_list)

    def write(self, vals):
        vals = self._strip_format_fields(dict(vals))
        self._check_locked_format_fields_write(vals)
        return super().write(vals)

    def _check_locked_format_fields_write(self, vals):
        if not vals:
            return
        for rec in self:
            dossier_locked = vals.get("dossier_code_format_locked", rec.dossier_code_format_locked)
            if "dossier_code_format" in vals and dossier_locked:
                if vals["dossier_code_format"] != rec.dossier_code_format:
                    raise ValidationError(
                        _("You cannot change the dossier code format while it is locked."),
                    )
            file_locked = vals.get("file_code_format_locked", rec.file_code_format_locked)
            if "file_code_format" in vals and file_locked:
                if vals["file_code_format"] != rec.file_code_format:
                    raise ValidationError(
                        _("You cannot change the file code format while it is locked."),
                    )

    @staticmethod
    def _document_profile_zip_path_segment(label):
        label = (label or "").strip() or "unknown"
        cleaned = re.sub(r"[\s/\\:*?\"<>|]+", "_", label)
        return (cleaned or "unknown")[:120]

    @api.model
    def _strip_format_fields(self, vals):
        if vals.get("dossier_code_format") is not None:
            vals["dossier_code_format"] = (vals.get("dossier_code_format") or "").strip()
        if vals.get("file_code_format") is not None:
            vals["file_code_format"] = (vals.get("file_code_format") or "").strip()
        return vals

    @api.constrains("dossier_code_format")
    def _check_dossier_code_format(self):
        for rec in self:
            fmt = (rec.dossier_code_format or "").strip()
            if not fmt:
                raise ValidationError(_("You must enter a dossier code format."))
            try:
                fmt % (1,)
            except (TypeError, ValueError) as e:
                raise ValidationError(
                    _(
                        "The dossier code format must have exactly one placeholder "
                        "(e.g. ADE.FIN.05.%02d).",
                    ),
                ) from e
            dup = self.with_context(active_test=False).search_count(
                [
                    ("id", "!=", rec.id),
                    ("dossier_code_format", "=", fmt),
                ],
            )
            if dup:
                raise ValidationError(
                    _(
                        "The dossier code format must be unique: another profile set "
                        "already uses this pattern.",
                    ),
                )

    def _next_dossier_sequence(self):
        self.ensure_one()
        Dossier = self.env["document.profile.dossier"].with_context(active_test=False)
        nums = Dossier.search([("profile_set_id", "=", self.id)]).mapped(
            "sequence_number",
        )
        return (max(nums) if nums else 0) + 1

    def action_archive(self):
        return self.write({"active": False})

    def action_unarchive(self):
        return self.write({"active": True})

    def action_toggle_dossier_code_format_lock(self):
        self.ensure_one()
        self.write({"dossier_code_format_locked": not self.dossier_code_format_locked})

    def action_toggle_file_code_format_lock(self):
        self.ensure_one()
        self.write({"file_code_format_locked": not self.file_code_format_locked})

    def action_download_all_files(self):
        """Zip every binary attachment on «Files by code» lines (all dossiers in this set)."""
        self.ensure_one()
        buffer = io.BytesIO()
        file_count = 0
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            items = self.item_ids.sorted(
                key=lambda r: (
                    r.dossier_id.sequence_number,
                    r.dossier_id.id,
                    r.sequence,
                    r.id,
                ),
            )
            for item in items:
                dossier = item.dossier_id
                dossier_seg = self._document_profile_zip_path_segment(
                    (dossier.name or "").strip() or dossier.code,
                )
                line_seg = self._document_profile_zip_path_segment(
                    (item.name or "").strip()
                    or item.code
                    or item.reference_key
                    or str(item.id),
                )
                for att in item.attachment_ids:
                    if att.type != "binary":
                        continue
                    data = att.raw
                    if not data:
                        continue
                    base = self._document_profile_zip_path_segment(att.name) or "file"
                    arcname = "%s/%s/%s_%s" % (dossier_seg, line_seg, att.id, base)
                    zf.writestr(arcname, data)
                    file_count += 1
        if not file_count:
            raise UserError(_("There are no files attached to this profile set."))
        buffer.seek(0)
        zip_name = "%s.zip" % self._document_profile_zip_path_segment(self.name)
        export = self.env["ir.attachment"].create(
            {
                "name": zip_name,
                "type": "binary",
                "datas": base64.b64encode(buffer.getvalue()),
                "mimetype": "application/zip",
            },
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % export.id,
            "target": "new",
        }

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("active", True)
        default.setdefault("dossier_code_format_locked", False)
        default.setdefault("file_code_format_locked", False)
        default["dossier_code_format"] = "%s (copy)" % self.dossier_code_format
        return super().copy(default)
