# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def document_profile_normalize_ref(value):
    """Normalize external reference values (e.g. 5 → 05) when deriving file codes."""
    s = (value or "").strip()
    if s.isdigit():
        return s.zfill(2)
    return s


document_profile_normalize_tm_ref = document_profile_normalize_ref


class DocumentProfileItem(models.Model):
    _name = "document.profile.item"
    _description = "File code and attachments (per dossier / profile set)"
    _order = "profile_set_id, dossier_id, sequence, id"

    profile_set_id = fields.Many2one(
        "document.profile.set",
        string="Profile Set",
        required=True,
        ondelete="cascade",
        index=True,
    )
    dossier_id = fields.Many2one(
        "document.profile.dossier",
        string="Dossier",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('profile_set_id', '=', profile_set_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="profile_set_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    reference_key = fields.Char(
        string="Reference",
        help="Reference segment used in «File Code Format» (e.g. 05). "
        "Defaults increment within the same dossier to avoid duplicate file codes. "
        "Changing dossier or file formats on the profile set will recompute file codes.",
    )
    code = fields.Char(
        string="File Code",
        compute="_compute_code",
        store=True,
        readonly=True,
        index=True,
        help="Computed from dossier code, «File Code Format», and reference "
        "(e.g. explanation 05 → ADE.FIN.05.01-05). Adjust via the Reference field.",
    )
    name = fields.Char(string="Description")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "document_profile_item_attachment_rel",
        "item_id",
        "attachment_id",
        string="Attachments",
    )

    _sql_constraints = [
        (
            "document_profile_item_code_uniq",
            "unique(code)",
            _("The file code must be unique across the database."),
        ),
    ]

    @api.model
    def _max_numeric_reference_key_for_dossier(self, dossier_id):
        """Largest integer among reference keys that are digits only (01, 2, 99…)."""
        max_n = 0
        for key in self.search([("dossier_id", "=", dossier_id)]).mapped(
            "reference_key",
        ):
            k = (key or "").strip()
            if k.isdigit():
                max_n = max(max_n, int(k))
        return max_n

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "reference_key" not in fields_list:
            return res
        if (res.get("reference_key") or "").strip():
            return res
        dossier_id = res.get("dossier_id") or self.env.context.get("default_dossier_id")
        if dossier_id:
            n = self._max_numeric_reference_key_for_dossier(dossier_id) + 1
            res["reference_key"] = document_profile_normalize_ref(str(n))
        return res

    @api.model
    def _reference_key_from_code(self, dossier, profile_set, full_code):
        """Infer reference from a full file code string (heuristic, dossier code first)."""
        c = (full_code or "").strip()
        if not c:
            return ""
        dc = (dossier.code or "").strip() if dossier else ""
        if dc and c.startswith(dc):
            rest = c[len(dc) :].lstrip("-_/. ")
            if rest:
                return document_profile_normalize_ref(rest)
        if "-" in c:
            last = c.rsplit("-", 1)[-1].strip()
            if last:
                return document_profile_normalize_ref(last)
        return document_profile_normalize_ref(c)

    @api.depends(
        "dossier_id",
        "dossier_id.code",
        "profile_set_id",
        "profile_set_id.file_code_format",
        "reference_key",
    )
    def _compute_code(self):
        for rec in self:
            key = document_profile_normalize_ref(rec.reference_key)
            dc = (rec.dossier_id.code or "").strip()
            fmt = (rec.profile_set_id.file_code_format or "%s-%s").strip()
            if not key:
                rec.code = ""
                continue
            try:
                rec.code = fmt % (dc, key)
            except (TypeError, ValueError):
                rec.code = "%s-%s" % (dc, key)

    @api.constrains("reference_key")
    def _check_reference_key(self):
        for rec in self:
            if not (rec.reference_key or "").strip():
                raise ValidationError(_("You must enter a reference."))

    @api.constrains("dossier_id", "profile_set_id")
    def _check_dossier_belongs_to_set(self):
        for rec in self:
            if rec.dossier_id.profile_set_id != rec.profile_set_id:
                raise ValidationError(
                    _("The dossier must belong to the selected profile set."),
                )

    @api.model_create_multi
    def create(self, vals_list):
        pending_next = {}
        for i, orig in enumerate(vals_list):
            vals = dict(orig)
            vals.pop("code", None)
            if vals.get("dossier_id"):
                dossier = self.env["document.profile.dossier"].browse(
                    vals["dossier_id"],
                )
                if not dossier.exists():
                    raise ValidationError(_("Invalid dossier."))
                ps = vals.get("profile_set_id")
                if ps and ps != dossier.profile_set_id.id:
                    raise ValidationError(
                        _("The dossier does not belong to the profile set of this line."),
                    )
                if not ps:
                    vals["profile_set_id"] = dossier.profile_set_id.id
            vals["reference_key"] = (vals.get("reference_key") or "").strip()
            if not vals.get("reference_key"):
                did = vals.get("dossier_id")
                if not did:
                    raise ValidationError(_("You must enter a reference."))
                if did not in pending_next:
                    pending_next[did] = self._max_numeric_reference_key_for_dossier(did)
                pending_next[did] += 1
                vals["reference_key"] = document_profile_normalize_ref(
                    str(pending_next[did]),
                )
            vals_list[i] = vals
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        vals.pop("code", None)
        if "reference_key" in vals and vals.get("reference_key") is not None:
            vals["reference_key"] = (vals.get("reference_key") or "").strip()
        return super().write(vals)
