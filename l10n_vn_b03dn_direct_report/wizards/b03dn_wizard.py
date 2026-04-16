# -*- coding: utf-8 -*-
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import date_utils


class L10nVnB03dnReportWizard(models.TransientModel):
    _name = "l10n.vn.b03dn.report.wizard"
    _description = "B03-DN — Statement of cash flows dialog (direct method)"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    circular_type = fields.Selection(
        related="company_id.circular_type",
        string="Circular type",
    )
    template_id = fields.Many2one(
        "l10n.vn.b03dn.template",
        string="Report template",
        domain=(
            "['&', '|', ('company_id', '=', False), "
            "('company_id', '=', company_id), "
            "('circular_type', '=', circular_type)]"
        ),
    )
    date_from = fields.Date(string="Date from", required=True)
    date_to = fields.Date(string="Date to", required=True)
    date_from_cmp = fields.Date(string="Date from (prior year)")
    date_to_cmp = fields.Date(string="Date to (prior year)")
    money_unit = fields.Selection(
        [
            ("1", "VND"),
            ("1000", "Thousands of VND"),
            ("1000000", "Millions of VND"),
        ],
        default="1",
        string="Amount display unit",
        help="Scale for print / Excel export — matches QWeb report.",
    )
    signature_date = fields.Date(string="Signature date", default=fields.Date.context_today)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        today = fields.Date.context_today(self)
        ds, de = date_utils.get_fiscal_year(
            today,
            day=company.fiscalyear_last_day,
            month=int(company.fiscalyear_last_month),
        )
        res.setdefault("date_from", ds)
        res.setdefault("date_to", de)
        py_end = ds - relativedelta(days=1)
        py_from, py_to = date_utils.get_fiscal_year(
            py_end,
            day=company.fiscalyear_last_day,
            month=int(company.fiscalyear_last_month),
        )
        res.setdefault("date_from_cmp", py_from)
        res.setdefault("date_to_cmp", py_to)
        if "template_id" in fields_list:
            ctype = company.circular_type or "tt200"
            tpl = self.env.ref(
                "l10n_vn_b03dn_direct_report.b03dn_template_tt200_direct",
                raise_if_not_found=False,
            )
            if (
                tpl
                and tpl.circular_type == ctype
                and (
                    not tpl.company_id or tpl.company_id.id == company.id
                )
            ):
                res.setdefault("template_id", tpl.id)
            else:
                first = self.env["l10n.vn.b03dn.template"].search(
                    [
                        ("circular_type", "=", ctype),
                        "|",
                        ("company_id", "=", False),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                if first:
                    res.setdefault("template_id", first.id)
        return res

    @api.onchange("company_id")
    def _onchange_company_id_b03dn_template(self):
        for wiz in self:
            if not wiz.company_id:
                continue
            ctype = wiz.company_id.circular_type or "tt200"
            tpl = wiz.template_id
            if tpl:
                ok_company = not tpl.company_id or tpl.company_id == wiz.company_id
                ok_type = tpl.circular_type == ctype
                if ok_company and ok_type:
                    continue
            match = self.env["l10n.vn.b03dn.template"].search(
                [
                    ("circular_type", "=", ctype),
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", wiz.company_id.id),
                ],
                limit=1,
            )
            wiz.template_id = match

    def _money_unit_int(self):
        self.ensure_one()
        try:
            return int(self.money_unit or 1)
        except (TypeError, ValueError):
            return 1

    @api.model
    def _parse_date_any(self, val):
        if not val:
            return False
        if isinstance(val, date):
            return val
        return fields.Date.from_string(str(val)[:10])

    @api.model
    def _build_report_payload_values(
        self,
        company_id,
        template_id,
        date_from,
        date_to,
        date_from_cmp,
        date_to_cmp,
        money_unit=1,
        doc_ids=None,
        signature_date=None,
    ):
        """Compute report data from wizard or QWeb filters (no transient required)."""
        company = self.env["res.company"].browse(company_id)
        template = self.env["l10n.vn.b03dn.template"].browse(template_id)
        if not company.exists() or not template.exists():
            return {
                "doc_ids": list(doc_ids or []),
                "doc_model": "l10n.vn.b03dn.report.wizard",
                "company": company.exists() and company or None,
                "currency": company.currency_id if company.exists() else None,
                "date_from": False,
                "date_to": False,
                "date_from_cmp": False,
                "date_to_cmp": False,
                "template": template.exists() and template or None,
                "rows": [],
                "aml_domain_common": [],
                "b03dn_ui_filters": {},
                "signature_date": False,
            }

        df = self._parse_date_any(date_from)
        dt = self._parse_date_any(date_to)
        dfc = self._parse_date_any(date_from_cmp)
        dtc = self._parse_date_any(date_to_cmp)

        try:
            mu = int(money_unit)
        except (TypeError, ValueError):
            mu = 1
        if mu not in (1, 1000, 1000000):
            mu = 1

        engine = self.env["l10n.vn.b03dn.engine"]
        cur = engine.compute_period(template, company, df, dt)
        prev = engine.compute_period(template, company, dfc, dtc)
        rows = []
        for line in template.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            c_code = (line.code or "").strip()
            if c_code:
                cur_vals = cur["lines_by_code"].get(
                    c_code, {"amount": 0.0, "aml_ids": []}
                )
                prev_vals = prev["lines_by_code"].get(
                    c_code, {"amount": 0.0, "aml_ids": []}
                )
            else:
                cur_vals = {"amount": 0.0, "aml_ids": []}
                prev_vals = {"amount": 0.0, "aml_ids": []}
            rows.append({
                "line": line,
                "amount_current": cur_vals["amount"],
                "amount_previous": prev_vals["amount"],
                "aml_domain_current": (
                    [("id", "in", cur_vals["aml_ids"])]
                    if cur_vals["aml_ids"]
                    else False
                ),
                "aml_domain_previous": (
                    [("id", "in", prev_vals["aml_ids"])]
                    if prev_vals["aml_ids"]
                    else False
                ),
            })

        sig_src = self._parse_date_any(signature_date) if signature_date else (
            self.signature_date if len(self) == 1 else False
        )
        ui_filters = {
            "company_id": company.id,
            "template_id": template.id,
            "date_from": fields.Date.to_string(df) if df else False,
            "date_to": fields.Date.to_string(dt) if dt else False,
            "date_from_cmp": fields.Date.to_string(dfc) if dfc else False,
            "date_to_cmp": fields.Date.to_string(dtc) if dtc else False,
            "money_unit": mu,
            "signature_date": fields.Date.to_string(sig_src) if sig_src else False,
        }

        sig_d = sig_src

        return {
            "doc_ids": list(doc_ids or []),
            "doc_model": "l10n.vn.b03dn.report.wizard",
            "company": company,
            "currency": company.currency_id,
            "date_from": df,
            "date_to": dt,
            "date_from_cmp": dfc,
            "date_to_cmp": dtc,
            "template": template,
            "rows": rows,
            "aml_domain_common": [
                ("company_id", "=", company.id),
                ("parent_state", "=", "posted"),
            ],
            "signature_date": sig_d,
            "b03dn_ui_filters": ui_filters,
        }

    def _report_payload(self):
        self.ensure_one()
        tid = self.template_id.id if self.template_id else False
        return self._build_report_payload_values(
            self.company_id.id,
            tid,
            self.date_from,
            self.date_to,
            self.date_from_cmp,
            self.date_to_cmp,
            money_unit=self._money_unit_int(),
            doc_ids=list(self.ids),
        )

    @api.model
    def build_payload_from_ui_filters(self, f, doc_ids=None):
        """Merge / rebuild payload from b03dn_ui_filters snapshot (QWeb / Excel)."""
        f = dict(f or {})
        try:
            cid = int(f.get("company_id") or 0)
            tid = int(f.get("template_id") or 0)
        except (TypeError, ValueError):
            return {}
        mu = f.get("money_unit", 1)
        try:
            mu = int(mu)
        except (TypeError, ValueError):
            mu = 1
        return self._build_report_payload_values(
            cid,
            tid,
            f.get("date_from"),
            f.get("date_to"),
            f.get("date_from_cmp"),
            f.get("date_to_cmp"),
            money_unit=mu,
            doc_ids=doc_ids,
            signature_date=f.get("signature_date") or False,
        )

    def action_open_html(self):
        self.ensure_one()
        data = self._report_payload()
        report = self.env.ref(
            "l10n_vn_b03dn_direct_report.b03dn_direct_html_action",
        )
        return report.report_action(self, data=data)

    def action_export_xlsx(self):
        self.ensure_one()
        data = self._report_payload()
        report = self.env.ref(
            "l10n_vn_b03dn_direct_report.b03dn_direct_xlsx_action",
        )
        return report.report_action(self, data=data)

    @api.model
    def action_open_html_menu(self):
        """Menu: open HTML report directly (edit layout in QWeb)."""
        vals = self.default_get(list(self._fields))
        wiz = self.create(vals)
        data = wiz._report_payload()
        report = self.env.ref(
            "l10n_vn_b03dn_direct_report.b03dn_direct_html_action",
        )
        return report.report_action(wiz, data=data)

    @api.model
    def action_open_from_menu(self):
        """Keep wizard (optional) — callable from other buttons."""
        Wizard = self.env["l10n.vn.b03dn.report.wizard"]
        vals = Wizard.default_get(list(Wizard._fields))
        wiz = Wizard.create(vals)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Statement of cash flows (B03-DN direct)"),
            "res_model": "l10n.vn.b03dn.report.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": wiz.id,
        }
