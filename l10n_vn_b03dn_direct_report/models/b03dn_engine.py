# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, models
from odoo.osv.expression import AND
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class L10nVnB03dnEngine(models.AbstractModel):
    """Tính toán luồng tiền B03-DN (trực tiếp) từ các dòng mẫu."""

    _name = "l10n.vn.b03dn.engine"
    _description = "B03-DN — Bộ máy tính toán"

    @api.model
    def _cash_account_ids(self, company, template):
        if template.cash_account_ids:
            return template.cash_account_ids.filtered(
                lambda a: company.id in a.company_ids.ids
            ).ids
        Account = self.env["account.account"]
        codes_domain = [
            "|",
            "|",
            ("code", "=ilike", "111%"),
            ("code", "=ilike", "112%"),
            ("code", "=ilike", "113%"),
        ]
        base_ids = Account.search(AND([[("company_ids", "in", company.ids)], codes_domain])).ids
        equiv_ids = company.b03dn_cash_equiv_account_ids.filtered(
            lambda a: company.id in a.company_ids.ids
        ).ids
        return list(set(base_ids + equiv_ids))

    @api.model
    def _allocate_split_amounts(self, total, weights, currency):
        prec = currency.decimal_places
        if not weights:
            return [currency.round(total)]
        w = [max(0.0, float(x)) for x in weights]
        sum_w = sum(w)
        if float_is_zero(sum_w, precision_digits=prec):
            n = len(w)
            if not n:
                return [currency.round(total)]
            base = currency.round(total / n)
            alloc = [base] * n
            diff = currency.round(total - sum(alloc))
            if alloc:
                alloc[-1] = currency.round(alloc[-1] + diff)
            return [max(0.0, x) for x in alloc]
        if float_compare(total, sum_w, precision_digits=prec) == 0:
            return [currency.round(x) for x in w]
        out = []
        allocated = 0.0
        for i, wi in enumerate(w):
            if i == len(w) - 1:
                alloc = currency.round(total - allocated)
            else:
                alloc = currency.round(total * (wi / sum_w))
                allocated += alloc
            out.append(max(0.0, alloc))
        return out

    @api.model
    def _cp_side_codes(self, others, use_debit):
        out = []
        key = "debit" if use_debit else "credit"
        for o in others:
            if (o.get(key) or 0) and o.get("code") and o["code"] not in out:
                out.append(o["code"])
        return ", ".join(out)

    @api.model
    def _counterparts_for_moves(self, entry_ids):
        if not entry_ids:
            return {}
        Line = self.env["account.move.line"]
        lines_data = Line.search_read(
            [("move_id", "in", entry_ids)],
            ["id", "move_id", "account_id", "debit", "credit"],
            order="move_id, id",
        )
        acc_ids = {l["account_id"][0] for l in lines_data if l.get("account_id")}
        code_map = {}
        if acc_ids:
            accounts = self.env["account.account"].browse(list(acc_ids))
            code_map = {a.id: a.code or "" for a in accounts}
        counterparts = defaultdict(list)
        for l in lines_data:
            mid = l["move_id"][0] if l.get("move_id") else False
            aid = l["account_id"][0] if l.get("account_id") else False
            counterparts[mid].append({
                "id": l["id"],
                "account_id": aid,
                "code": code_map.get(aid, ""),
                "debit": l["debit"],
                "credit": l["credit"],
            })
        return counterparts

    @api.model
    def _fragment_from_cash_line(self, ml, by_move, currency, cash_account_ids=None):
        """Một dòng tiền → 1 hoặc nhiều mảnh theo từng TK đối ứng có Nợ/Có cùng phía.

        Luôn phân bổ *amount* dòng tiền theo trọng số các đối ứng (kể cả chỉ 1 đối ứng) để
        trường hợp nhiều TK tiền trên cùng chứng từ + nhiều TK đối ứng không gán nhầm
        nguyên số tiền vào một đối ứng.

        Bút toán chỉ chuyển qua lại giữa các TK tiền (đối ứng toàn là tiền) → không tạo mảnh.
        """
        prec = currency.decimal_places
        cash_ids = frozenset(cash_account_ids or [])
        my_debit = float(ml.get("debit") or 0)
        my_credit = float(ml.get("credit") or 0)
        entry_id = ml["move_id"][0] if ml.get("move_id") else False
        if not entry_id or entry_id not in by_move:
            return []

        others = [o for o in by_move[entry_id] if o["id"] != ml["id"]]
        if (
            others
            and cash_ids
            and all(o.get("account_id") in cash_ids for o in others)
        ):
            return []

        def credit_pairs():
            return [
                (o["code"], o["account_id"], float(o["credit"] or 0), o["id"])
                for o in others
                if o.get("code")
                and float_compare(o.get("credit") or 0, 0, precision_digits=prec) > 0
            ]

        def debit_pairs():
            return [
                (o["code"], o["account_id"], float(o["debit"] or 0), o["id"])
                for o in others
                if o.get("code")
                and float_compare(o.get("debit") or 0, 0, precision_digits=prec) > 0
            ]

        def build_frags(amount, opp, is_inflow, use_debit_fallback):
            if float_is_zero(amount, precision_digits=prec):
                return []
            if not opp:
                code = self._cp_side_codes(others, use_debit_fallback)
                if not (code or "").strip():
                    return []
                cp_ids = [
                    o["id"]
                    for o in others
                    if not cash_ids or o.get("account_id") not in cash_ids
                ]
                return [{
                    "cash_aml_id": ml["id"],
                    "counterpart_code": code,
                    "counterpart_account_id": False,
                    "counterpart_aml_ids": cp_ids,
                    "amount": amount,
                    "is_inflow": is_inflow,
                }]
            weights = [w for _c, _aid, w, _lid in opp]
            splits = self._allocate_split_amounts(amount, weights, currency)
            frags = []
            for (code, acc_id, _w, cp_aml_id), amt in zip(opp, splits):
                if float_is_zero(amt, precision_digits=prec):
                    continue
                frags.append({
                    "cash_aml_id": ml["id"],
                    "counterpart_code": code,
                    "counterpart_account_id": acc_id,
                    "counterpart_aml_ids": [cp_aml_id],
                    "amount": amt,
                    "is_inflow": is_inflow,
                })
            return frags

        if my_debit > 0 and float_is_zero(my_credit, precision_digits=prec):
            return build_frags(my_debit, credit_pairs(), True, False)

        if my_credit > 0 and float_is_zero(my_debit, precision_digits=prec):
            return build_frags(my_credit, debit_pairs(), False, True)

        return []

    @api.model
    def _patterns_list(self, char_patterns):
        if not char_patterns or not str(char_patterns).strip():
            return []
        return [p.strip() for p in str(char_patterns).split(",") if p.strip()]

    @api.model
    def _leaf_rule_counterpart_pattern_source(self, rule, is_inflow):
        """Inflow → match credit_account_patterns; outflow → debit_account_patterns."""
        if is_inflow:
            return (rule.credit_account_patterns or "").strip()
        return (rule.debit_account_patterns or "").strip()

    @api.model
    def _code_matches_patterns(self, account_code, patterns):
        code = (account_code or "").strip()
        if not patterns:
            return True
        for p in patterns:
            if not p:
                continue
            pat = p.strip()
            if pat.endswith("%"):
                if code.startswith(pat[:-1]):
                    return True
            elif code == pat:
                return True
        return False

    @api.model
    def _tag_pool(self, rule, line_tags, acc_tags):
        if rule.tag_source == "cash_line":
            return line_tags
        if rule.tag_source == "counterpart_account":
            return acc_tags
        return line_tags | acc_tags

    @api.model
    def _exclude_tags_hit(self, rule, line_tags, acc_tags):
        excluded = rule.exclude_tag_ids
        if not excluded:
            return False
        pool = self._tag_pool(rule, line_tags, acc_tags)
        return any(t in pool for t in excluded)

    @api.model
    def _tags_match(self, rule, line_tags, acc_tags):
        required = rule.tag_ids
        if not required:
            return True
        pool = self._tag_pool(rule, line_tags, acc_tags)
        if rule.tag_match_mode == "any":
            return any(t in pool for t in required)
        return all(t in pool for t in required)

    @api.model
    def _parse_extra_domain(self, line):
        if not line.extra_domain:
            return []
        try:
            dom = safe_eval(line.extra_domain.strip(), {})
        except Exception as e:  # noqa: BLE001
            _logger.warning("B03DN extra_domain eval failed: %s", e)
            return []
        if not isinstance(dom, list):
            return []
        return dom

    @api.model
    def _opening_cash_balance(self, company, account_ids, date_from):
        if not account_ids:
            return 0.0
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(aml.debit - aml.credit), 0.0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.company_id = %s
              AND aml.account_id = ANY(%s)
              AND aml.date < %s
              AND am.state = 'posted'
            """,
            (company.id, list(account_ids), date_from),
        )
        row = self.env.cr.fetchone()
        return float(row[0] or 0.0)

    @api.model
    def _fx_balance_change(self, company, date_from, date_to, patterns):
        pats = self._patterns_list(patterns) or ["413%"]
        dom = [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("parent_state", "=", "posted"),
        ]
        or_part = []
        for p in pats:
            or_part.append(("account_id.code", "=ilike", p))
        if len(or_part) == 1:
            dom = AND([dom, or_part])
        else:
            dom = AND([dom, ["|"] * (len(or_part) - 1) + or_part])
        lines = self.env["account.move.line"].search(dom)
        return sum(lines.mapped("balance")), lines.ids

    @api.model
    def compute_period(self, template, company, date_from, date_to):
        """Return dict code -> {amount, aml_ids} for one period.

        ``aml_ids`` (chỉ tiêu leaf / aggregate): id các dòng sổ **đối ứng** khớp fragment,
        dùng drill-down QWeb / Excel — không còn là id dòng tiền.
        """
        currency = company.currency_id
        account_ids = self._cash_account_ids(company, template)
        cash_id_set = frozenset(account_ids)
        lines = template.line_ids.sorted(key=lambda l: (l.sequence, l.id))
        leaf_lines = lines.filtered(lambda l: l._b03dn_is_leaf_line())

        aml_domain = [
            ("company_id", "=", company.id),
            ("account_id", "in", account_ids),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("parent_state", "=", "posted"),
        ]
        cash_amls = self.env["account.move.line"].search_read(
            aml_domain,
            ["id", "move_id", "debit", "credit", "account_id"],
        )
        move_ids = list({m["move_id"][0] for m in cash_amls if m.get("move_id")})
        by_move = self._counterparts_for_moves(move_ids)

        fragments = []
        for ml in cash_amls:
            fragments.extend(
                self._fragment_from_cash_line(
                    ml, by_move, currency, cash_account_ids=cash_id_set,
                )
            )

        buckets = defaultdict(lambda: {"amount": 0.0, "aml_ids": set()})
        Account = self.env["account.account"]

        leaf_lines_ord = leaf_lines.sorted(key=lambda l: (l.sequence, l.id))
        for frag in fragments:
            for rule in leaf_lines_ord:
                pats = self._patterns_list(
                    self._leaf_rule_counterpart_pattern_source(
                        rule, frag["is_inflow"]
                    )
                )
                if not pats and not rule.tag_ids:
                    continue
                extra = self._parse_extra_domain(rule)
                cp_code_single = frag["counterpart_code"] or ""
                if "," in cp_code_single:
                    codes_to_check = [
                        c.strip() for c in cp_code_single.split(",") if c.strip()
                    ]
                elif cp_code_single:
                    codes_to_check = [cp_code_single]
                else:
                    codes_to_check = [""]
                match_cp = any(
                    self._code_matches_patterns(cc, pats)
                    for cc in codes_to_check
                )
                if not match_cp:
                    continue

                excl_pats = self._patterns_list(rule.exclude_account_patterns or "")
                if excl_pats and any(
                    self._code_matches_patterns(cc, excl_pats)
                    for cc in codes_to_check
                ):
                    continue

                cash_line = self.env["account.move.line"].browse(frag["cash_aml_id"])
                cp_acc = (
                    Account.browse(frag["counterpart_account_id"])
                    if frag.get("counterpart_account_id")
                    else self.env["account.account"]
                )
                line_tags = cash_line.b03dn_cash_flow_tag_ids
                acc_tags = cp_acc.tag_ids if cp_acc else self.env["account.account.tag"]
                if self._exclude_tags_hit(rule, line_tags, acc_tags):
                    continue
                if not self._tags_match(rule, line_tags, acc_tags):
                    continue
                if extra and not cash_line.filtered_domain(extra):
                    continue

                raw = frag["amount"]
                signed = raw if frag["is_inflow"] else -raw
                signed *= rule.amount_multiplier
                rcode = (rule.code or "").strip()
                buckets[rcode]["amount"] += signed
                for cp_id in frag.get("counterpart_aml_ids") or []:
                    buckets[rcode]["aml_ids"].add(cp_id)
                break

        result = {}
        for li in lines:
            c = (li.code or "").strip()
            if c:
                result[c] = {"amount": 0.0, "aml_ids": []}
        for code, v in buckets.items():
            result[code] = {"amount": v["amount"], "aml_ids": sorted(v["aml_ids"])}

        for line in lines:
            c = (line.code or "").strip()
            if line._b03dn_is_opening_line():
                amt = self._opening_cash_balance(company, account_ids, date_from)
                result[c] = {"amount": amt, "aml_ids": []}
            elif line._b03dn_is_fx_line():
                p = line.fx_account_patterns or "413%"
                amt, aml_ids = self._fx_balance_change(
                    company, date_from, date_to, p
                )
                result[c] = {"amount": amt, "aml_ids": aml_ids}

        seq_lines = list(lines.sorted(key=lambda l: (l.sequence, l.id)))
        for _rep in range(len(seq_lines) + 5):
            stable = True
            for line in seq_lines:
                if not line._b03dn_is_aggregate_line():
                    continue
                parts = [
                    p.strip()
                    for p in line._b03dn_sum_stripped().split("+")
                    if p.strip()
                ]
                amt = 0.0
                aml_set = set()
                missing = False
                for c in parts:
                    if c not in result:
                        missing = True
                        break
                    amt += result[c]["amount"]
                    aml_set.update(result[c]["aml_ids"])
                if missing:
                    continue
                lc = (line.code or "").strip()
                prev_amt = result.get(lc, {}).get("amount")
                prev_ids = set(result.get(lc, {}).get("aml_ids", []))
                if prev_amt != amt or prev_ids != aml_set:
                    stable = False
                result[lc] = {
                    "amount": amt,
                    "aml_ids": sorted(aml_set),
                }
            if stable:
                break

        return {
            "lines_by_code": result,
            "account_ids": account_ids,
        }
