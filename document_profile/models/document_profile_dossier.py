# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .document_profile_item import document_profile_normalize_ref


def document_profile_format_dossier_code(fmt, sequence_number):
    """Apply «Dossier Code Format» with a single numeric argument; never raises."""
    fmt = (fmt or "").strip()
    if not fmt:
        return ""
    n = int(sequence_number or 0)
    for args in ((n,), (str(n).zfill(2),), (str(n),)):
        try:
            return fmt % args
        except (TypeError, ValueError):
            continue
    base = fmt.rstrip(" .-_")
    return "%s-%02d" % (base, n)


class DocumentProfileDossier(models.Model):
    _name = "document.profile.dossier"
    _description = "Dossier"
    _order = "profile_set_id, sequence_number, id"

    profile_set_id = fields.Many2one(
        "document.profile.set",
        string="Profile Set",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="profile_set_id.company_id",
        store=True,
        readonly=True,
    )
    name = fields.Char(string="Dossier Name", required=True)
    active = fields.Boolean(
        default=True,
        string="Active",
    )
    sequence_number = fields.Integer(
        string="Sequence",
        required=True,
        readonly=True,
        copy=False,
        default=0,
    )
    code = fields.Char(
        string="Dossier Code",
        compute="_compute_code",
        store=True,
        readonly=True,
    )
    item_ids = fields.One2many(
        "document.profile.item",
        "dossier_id",
        string="Files by Code",
        copy=True,
        help="Each line: file code (matching codes inferred from reports) and attachments.",
    )

    _sql_constraints = [
        (
            "document_profile_dossier_set_seq_uniq",
            "unique(profile_set_id, sequence_number)",
            _("The dossier sequence must be unique within the profile set."),
        ),
    ]

    @api.depends("profile_set_id", "profile_set_id.dossier_code_format", "sequence_number")
    def _compute_code(self):
        for rec in self:
            rec.code = document_profile_format_dossier_code(
                rec.profile_set_id.dossier_code_format,
                rec.sequence_number or 0,
            )

    @api.model_create_multi
    def create(self, vals_list):
        by_set = {}
        for vals in vals_list:
            sid = vals.get("profile_set_id")
            if sid and not vals.get("sequence_number"):
                by_set.setdefault(sid, []).append(vals)
        for sid, valss in by_set.items():
            pset = self.env["document.profile.set"].browse(sid)
            start = pset._next_dossier_sequence()
            for i, vals in enumerate(valss):
                vals["sequence_number"] = start + i
        return super().create(vals_list)

    @api.constrains("code", "profile_set_id")
    def _check_code_unique_per_set(self):
        Dossier = self.with_context(active_test=False)
        for rec in self:
            c = (rec.code or "").strip()
            if not c:
                continue
            n = Dossier.search_count(
                [
                    ("profile_set_id", "=", rec.profile_set_id.id),
                    ("id", "!=", rec.id),
                    ("code", "=", c),
                ],
            )
            if n:
                raise ValidationError(_("Dossier code «%s» already exists in this profile set.", c))

    def action_archive(self):
        return self.write({"active": False})

    def action_unarchive(self):
        return self.write({"active": True})

    def expected_code_for_reference(self, ref_value):
        """Theoretical file code from reference and the profile set «File Code Format»."""
        self.ensure_one()
        key = document_profile_normalize_ref(ref_value)
        if not key:
            return ""
        fmt = (self.profile_set_id.file_code_format or "%s-%s").strip()
        dc = (self.code or "").strip()
        try:
            return fmt % (dc, key)
        except (TypeError, ValueError):
            return "%s-%s" % (dc, key)

    def _profile_attachment_for_reference(self, ref_value):
        """Hook: find ir.attachment by reference (default: document.profile.item).

        Other addons may ``_inherit = 'document.profile.dossier'`` and override
        this method to use another source, then call ``super()`` if fallback is needed.
        """
        self.ensure_one()
        expected = self.expected_code_for_reference(ref_value)
        if not (expected or "").strip():
            return False
        exp = expected.strip().lower()
        for line in self.item_ids:
            if (line.code or "").strip().lower() == exp and line.attachment_ids:
                return line.attachment_ids[0].id
        return False

    def profile_attachment_for_reference(self, ref_value):
        """Public API: ``ir.attachment`` id or False."""
        self.ensure_one()
        return self._profile_attachment_for_reference(ref_value)

    @api.model
    def profile_attachment_id_for_reference(self, dossier, ref_value):
        """Module-level API for reports / other addons (not tied to B03)."""
        if not dossier:
            return False
        return dossier.profile_attachment_for_reference(ref_value)

    @api.model
    def b03dn_attachment_id_for_explanation(self, dossier, explanation_ref):
        """B03-DN compatibility: Explanation column → reference key."""
        return self.profile_attachment_id_for_reference(dossier, explanation_ref)

    def action_open_item_window(self):
        """Popup: file code + upload for this dossier."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — Files by Code") % ((self.code or self.name) or ""),
            "res_model": "document.profile.item",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("document_profile.view_document_profile_item_tree").id, "list"),
                (self.env.ref("document_profile.view_document_profile_item_form").id, "form"),
            ],
            "search_view_id": self.env.ref(
                "document_profile.view_document_profile_item_search",
            ).id,
            "domain": [("dossier_id", "=", self.id)],
            "context": {
                "default_dossier_id": self.id,
                "default_profile_set_id": self.profile_set_id.id,
            },
            "target": "new",
        }
