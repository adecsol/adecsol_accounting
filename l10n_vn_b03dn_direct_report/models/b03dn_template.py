# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape


def _b03dn_html_has_visible_text(html_value):
    if not html_value or not str(html_value).strip():
        return False
    plain = re.sub(r"<[^>]+>", "", str(html_value))
    return bool(plain.strip())


class L10nVnB03dnTemplate(models.Model):
    _name = "l10n.vn.b03dn.template"
    _description = "B03-DN (direct) — Report template"

    name = fields.Char(required=True, translate=True)
    circular_type = fields.Selection(
        [
            ("tt133", "TT133"),
            ("tt99", "TT99"),
            ("tt200", "TT200"),
        ],
        string="Circular type",
        default="tt200",
        required=True,
        help="Must match «Circular type» on the company for the template to appear on the report.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        help="Leave empty: available for every company.",
    )
    document_dossier_id = fields.Many2one(
        "document.profile.dossier",
        string="Notes dossier",
        ondelete="set null",
        help="When set: on the HTML report, the «Notes» column opens files whose code matches "
        "(reference TM aligned with the line, e.g. 05 → …-05).",
    )
    cash_account_ids = fields.Many2many(
        "account.account",
        "b03dn_template_cash_account_rel",
        "template_id",
        "account_id",
        string="Cash & cash-equivalent accounts (override)",
        help="If set, only these accounts are scanned. If empty: 111/112/113 per company + "
        "cash-equivalent accounts on res.company.",
        check_company=True,
    )
    line_ids = fields.One2many(
        "l10n.vn.b03dn.line",
        "template_id",
        string="Line items",
        copy=True,
    )
    b03dn_tag_config_alert = fields.Html(
        string="Tag configuration warning",
        compute="_compute_b03dn_tag_config_alert",
        sanitize=False,
    )

    @api.depends(
        "line_ids",
        "line_ids.display_type",
        "line_ids.tag_ids",
        "line_ids.exclude_tag_ids",
    )
    def _compute_b03dn_tag_config_alert(self):
        for tmpl in self:
            comp_lines = tmpl.line_ids.filtered(lambda l: not l.display_type)
            required_union = comp_lines.mapped("tag_ids")
            exclude_union = comp_lines.mapped("exclude_tag_ids")
            only_in_required = required_union - exclude_union
            if not only_in_required:
                tmpl.b03dn_tag_config_alert = False
                continue
            badges = Markup(", ").join(
                Markup('<span class="badge text-bg-secondary me-1">%s</span>')
                % html_escape((t.display_name or t.name or "").strip() or str(t.id))
                for t in only_in_required.sorted(key=lambda t: (t.name or "").lower())
            )
            title = html_escape(
                _(
                    "Tags that appear only in «Required tags» and not in «Excluded tags» "
                    "for any line on this template:"
                )
            )
            tmpl.b03dn_tag_config_alert = Markup(
                '<div class="alert alert-warning mb-3" role="alert">'
                "<p class=\"mb-2\"><strong>%s</strong></p>"
                "<p class=\"mb-0\">%s</p>"
                "</div>"
            ) % (Markup(title), badges)


class L10nVnB03dnLine(models.Model):
    _name = "l10n.vn.b03dn.line"
    _description = "B03-DN (direct) — Line item / rule"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "l10n.vn.b03dn.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    display_type = fields.Selection(
        [
            ("line_section", "Section"),
            ("line_note", "Note"),
        ],
        default=False,
        help="For list UI only (widget): section title / note; "
        "empty = computed line item (account patterns / sum / opening / FX).",
    )

    code = fields.Char(
        size=8,
        help="Line code (e.g. 01, 20, 70). Optional on Section / Note lines.",
    )
    name = fields.Html(
        translate=True,
        help="Section / Note lines may be empty. Computed lines must have content.",
    )
    explanation_ref = fields.Char(
        string="Notes reference",
        translate=True,
        help="Notes symbol on B03 (if any).",
    )
    debit_account_patterns = fields.Char(
        string="Debit account patterns",
        help="Comma-separated account code patterns (e.g. 331%, 152%). "
        "Cash outflow (credit side of cash): match counterpart debit lines (TT200 debit column; excluding cash).",
    )
    credit_account_patterns = fields.Char(
        string="Credit account patterns",
        help="Comma-separated account code patterns. "
        "Cash inflow (debit side of cash): match counterpart credit lines (TT200 credit column).",
    )
    exclude_account_patterns = fields.Char(
        string="Exclude counterpart patterns",
        help="Comma-separated account codes, %% suffix supported like Debit/Credit patterns. "
        "If any counterpart code (or split string) matches an exclusion pattern, "
        "this leaf rule does not apply to that fragment (it may fall through to another line).",
    )
    amount_multiplier = fields.Float(
        default=1.0,
        help="Multiplier after allocation (usually -1 for outflows).",
    )
    tag_ids = fields.Many2many(
        "account.account.tag",
        "l10n_vn_b03dn_line_tag_rel",
        "line_id",
        "tag_id",
        string="Required tags",
    )
    exclude_tag_ids = fields.Many2many(
        "account.account.tag",
        "l10n_vn_b03dn_line_exclude_tag_rel",
        "line_id",
        "tag_id",
        string="Excluded tags",
        help="Tag accounts (or B03-DN cash-flow tags on move lines, depending on «Tag source») to "
        "exclude transactions that match account patterns but do not belong on this line. "
        "Use together with «Required tags» for evaluation.",
    )
    tag_match_mode = fields.Selection(
        [
            ("all", "Must have all tags"),
            ("any", "At least one tag"),
        ],
        default="any",
        required=True,
    )
    tag_source = fields.Selection(
        [
            ("counterpart_account", "Tags on counterpart account"),
            ("cash_line", "Tags on cash line (B03-DN)"),
            ("either", "Prefer cash line, then counterpart account"),
        ],
        default="either",
    )

    sum_expression = fields.Char(
        string="Sum expression",
        help="Example: 01+02 or 20+30+40. When set: line = sum of codes (aggregate). "
        "Do not combine with opening / FX / cash filtering patterns.",
    )

    use_opening_cash_balance = fields.Boolean(
        string="Opening cash & equivalents",
        help="When enabled: take cash account balances (per template config) on the day before the report period. "
        "Do not use together with sum expression, FX patterns or cash filtering.",
    )

    fx_account_patterns = fields.Char(
        string="FX journal account patterns",
        help="When set: line takes total movement of matching accounts in the period (e.g. 413%%). "
        "Do not use together with sum expression, opening or cash filtering.",
    )

    extra_domain = fields.Char(
        string="Extra filter (move line)",
        help="JSON domain string on account.move.line, applied after detailed rules match.",
    )

    b03dn_report_bold_amounts = fields.Boolean(
        string="Report: bold amounts",
        compute="_compute_b03dn_report_bold_amounts",
    )

    @api.depends("display_type", "sum_expression", "use_opening_cash_balance")
    def _compute_b03dn_report_bold_amounts(self):
        for line in self:
            if line.display_type == "line_section":
                line.b03dn_report_bold_amounts = True
            elif line.display_type:
                line.b03dn_report_bold_amounts = False
            else:
                line.b03dn_report_bold_amounts = bool(
                    (line.sum_expression or "").strip()
                ) or line.use_opening_cash_balance

    def _b03dn_sum_stripped(self):
        return (self.sum_expression or "").replace(" ", "").strip()

    def _b03dn_is_aggregate_line(self):
        return bool(self._b03dn_sum_stripped()) and not self.display_type

    def _b03dn_is_opening_line(self):
        return bool(self.use_opening_cash_balance) and not self.display_type

    def _b03dn_is_fx_line(self):
        fx = (self.fx_account_patterns or "").strip()
        if not fx or self.display_type:
            return False
        return (
            not self._b03dn_is_aggregate_line()
            and not self._b03dn_is_opening_line()
        )

    def _b03dn_is_leaf_line(self):
        if (
            self.display_type
            or self._b03dn_is_aggregate_line()
            or self._b03dn_is_opening_line()
            or self._b03dn_is_fx_line()
        ):
            return False
        d_pat = (self.debit_account_patterns or "").strip()
        c_pat = (self.credit_account_patterns or "").strip()
        return bool(d_pat or c_pat or self.tag_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        dt = ctx.get("default_display_type")
        if dt in ("line_section", "line_note"):
            res["display_type"] = dt
        elif "default_display_type" in ctx and not dt:
            res["display_type"] = False
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code") is not None:
                c = (vals.get("code") or "").strip()
                vals["code"] = c or False
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals:
            v = vals["code"]
            if isinstance(v, str):
                c = v.strip()
                vals["code"] = c or False
            elif not v:
                vals["code"] = False
        return super().write(vals)

    @api.constrains(
        "display_type",
        "sum_expression",
        "use_opening_cash_balance",
        "fx_account_patterns",
        "debit_account_patterns",
        "credit_account_patterns",
        "tag_ids",
    )
    def _b03dn_line_exclusive_computation(self):
        for line in self:
            if line.display_type:
                continue
            sum_e = line._b03dn_sum_stripped()
            d_pat = (line.debit_account_patterns or "").strip()
            c_pat = (line.credit_account_patterns or "").strip()
            fx = (line.fx_account_patterns or "").strip()
            leaf = bool(d_pat or c_pat or line.tag_ids)
            modes = (
                bool(sum_e)
                + bool(line.use_opening_cash_balance)
                + bool(fx)
                + bool(leaf)
            )
            if modes == 0:
                raise ValidationError(
                    self.env._(
                        "A computed line must have exactly one mode: sum expression, opening cash, "
                        "FX account pattern, or cash filter (debit/credit patterns and/or tags). "
                        "(line id: %s)",
                        line.id,
                    )
                )
            if modes > 1:
                raise ValidationError(
                    self.env._(
                        "Only one computation mode is allowed: aggregate (sum), opening, FX, "
                        "or leaf filter — do not mix. (line id: %s)",
                        line.id,
                    )
                )

    @api.constrains("code", "display_type")
    def _b03dn_line_code_required_computing(self):
        for line in self:
            if line.display_type:
                continue
            c = (line.code or "").strip()
            if not c:
                raise ValidationError(
                    self.env._(
                        "Line code is required for computed lines (line id: %s).",
                        line.id,
                    )
                )

    @api.constrains("name", "display_type")
    def _b03dn_name_required_for_computing_lines(self):
        for line in self:
            if line.display_type:
                continue
            if not _b03dn_html_has_visible_text(line.name):
                raise ValidationError(
                    self.env._(
                        "Line name is required for computed lines (line id: %s).",
                        line.id,
                    )
                )

    @api.constrains("code", "template_id")
    def _b03dn_line_code_unique_per_template(self):
        for line in self:
            c = (line.code or "").strip()
            if not c:
                continue
            n = self.search_count(
                [
                    ("template_id", "=", line.template_id.id),
                    ("id", "!=", line.id),
                    ("code", "=", c),
                ]
            )
            if n:
                raise ValidationError(
                    self.env._(
                        "Line code «%s» already exists on this template.",
                        c,
                    )
                )
