# -*- coding: utf-8 -*-
from datetime import date
from types import SimpleNamespace

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestB03dnDirect(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_notrack=True,
                no_reset_password=True,
                tracking_disable=True,
            )
        )

    def test_b03dn_leaf_inflow_and_outflow_drilldown(self):
        company = self.env.company
        bank_journal = self.company_data["default_journal_bank"]
        liquidity = bank_journal.default_account_id
        self.assertTrue(liquidity)
        if liquidity.code != "1121":
            liquidity.code = "1121"

        inc = self.env["account.account"].create({
            "code": "5111",
            "name": "B03 test revenue",
            "account_type": "income",
            "company_ids": [(6, 0, [company.id])],
        })
        tpl = self.env.ref("l10n_vn_b03dn_direct_report.b03dn_template_tt200_direct")
        tpl.cash_account_ids = [(6, 0, [liquidity.id])]

        move_in = self.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-06-10",
            "journal_id": bank_journal.id,
            "line_ids": [
                (0, 0, {"account_id": liquidity.id, "name": "In", "debit": 200, "credit": 0}),
                (0, 0, {"account_id": inc.id, "name": "Rev", "debit": 0, "credit": 200}),
            ],
        })
        move_in.action_post()

        ap = self.env["account.account"].create({
            "code": "3311",
            "name": "B03 test payable",
            "account_type": "liability_payable",
            "company_ids": [(6, 0, [company.id])],
        })
        tag = self.env.ref("l10n_vn_b03dn_direct_report.tag_b03_cf_02_supplier")
        ap.tag_ids = [(6, 0, [tag.id])]

        move_out = self.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-06-12",
            "journal_id": bank_journal.id,
            "line_ids": [
                (0, 0, {"account_id": ap.id, "name": "Pay", "debit": 80, "credit": 0}),
                (0, 0, {"account_id": liquidity.id, "name": "Cash", "debit": 0, "credit": 80}),
            ],
        })
        move_out.action_post()

        engine = self.env["l10n.vn.b03dn.engine"]
        res = engine.compute_period(
            tpl,
            company,
            date(2025, 6, 1),
            date(2025, 6, 30),
        )
        by_code = res["lines_by_code"]
        self.assertAlmostEqual(by_code["01"]["amount"], 200.0, places=2)
        self.assertTrue(by_code["01"]["aml_ids"])
        inc_line = move_in.line_ids.filtered(lambda l: l.account_id == inc)
        self.assertEqual(len(inc_line), 1)
        self.assertIn(inc_line.id, by_code["01"]["aml_ids"])
        self.assertAlmostEqual(by_code["02"]["amount"], -80.0, places=2)
        self.assertTrue(by_code["02"]["aml_ids"])
        ap_line = move_out.line_ids.filtered(lambda l: l.account_id == ap)
        self.assertEqual(len(ap_line), 1)
        self.assertIn(ap_line.id, by_code["02"]["aml_ids"])

        agg20 = by_code["20"]["amount"]
        self.assertAlmostEqual(agg20, 200.0 - 80.0, places=2)

    def test_b03dn_leaf_exclude_account_patterns_skips_rule(self):
        """Mẫu loại trừ TK đối ứng: khớp Nợ/Có nhưng bị skip → không ghi vào chỉ tiêu đó."""
        company = self.env.company
        bank_journal = self.company_data["default_journal_bank"]
        liquidity = bank_journal.default_account_id
        if liquidity.code != "1121":
            liquidity.code = "1121"

        ap = self.env["account.account"].create({
            "code": "3319",
            "name": "B03 exclude-test payable",
            "account_type": "liability_payable",
            "company_ids": [(6, 0, [company.id])],
        })
        tag = self.env.ref("l10n_vn_b03dn_direct_report.tag_b03_cf_02_supplier")

        tpl = self.env.ref("l10n_vn_b03dn_direct_report.b03dn_template_tt200_direct")
        tpl.cash_account_ids = [(6, 0, [liquidity.id])]

        line02 = tpl.line_ids.filtered(lambda l: (l.code or "").strip() == "02")
        self.assertTrue(line02)
        saved_excl = line02.exclude_account_patterns
        line02.write({"exclude_account_patterns": "331%,3319"})

        try:
            ap.tag_ids = [(6, 0, [tag.id])]
            self.env["account.move"].create({
                "move_type": "entry",
                "date": "2025-08-01",
                "journal_id": bank_journal.id,
                "line_ids": [
                    (0, 0, {"account_id": ap.id, "name": "Pay", "debit": 50, "credit": 0}),
                    (0, 0, {"account_id": liquidity.id, "name": "Cash", "debit": 0, "credit": 50}),
                ],
            }).action_post()

            engine = self.env["l10n.vn.b03dn.engine"]
            by_code = engine.compute_period(
                tpl, company, date(2025, 8, 1), date(2025, 8, 31),
            )["lines_by_code"]
            self.assertAlmostEqual(by_code["02"]["amount"], 0.0, places=2)
            self.assertFalse(by_code["02"]["aml_ids"])
        finally:
            line02.write({"exclude_account_patterns": saved_excl or False})

    def test_b03dn_multi_counterpart_split_inflow(self):
        """Một dòng Nợ tiền, nhiều dòng Có đối ứng → phân bổ đúng từng phần."""
        company = self.env.company
        bank_journal = self.company_data["default_journal_bank"]
        liquidity = bank_journal.default_account_id
        if liquidity.code != "1121":
            liquidity.code = "1121"

        inc_a = self.env["account.account"].create({
            "code": "5118",
            "name": "B03 multi rev A",
            "account_type": "income",
            "company_ids": [(6, 0, [company.id])],
        })
        inc_b = self.env["account.account"].create({
            "code": "1312",
            "name": "B03 multi rev B",
            "account_type": "income",
            "company_ids": [(6, 0, [company.id])],
        })
        tpl = self.env.ref("l10n_vn_b03dn_direct_report.b03dn_template_tt200_direct")
        tpl.cash_account_ids = [(6, 0, [liquidity.id])]

        move = self.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-07-01",
            "journal_id": bank_journal.id,
            "line_ids": [
                (0, 0, {"account_id": liquidity.id, "debit": 1000, "credit": 0}),
                (0, 0, {"account_id": inc_a.id, "debit": 0, "credit": 600}),
                (0, 0, {"account_id": inc_b.id, "debit": 0, "credit": 400}),
            ],
        })
        move.action_post()

        engine = self.env["l10n.vn.b03dn.engine"]
        by_code = engine.compute_period(
            tpl, company, date(2025, 7, 1), date(2025, 7, 31),
        )["lines_by_code"]
        self.assertAlmostEqual(by_code["01"]["amount"], 1000.0, places=2)
        la = move.line_ids.filtered(lambda l: l.account_id == inc_a)
        lb = move.line_ids.filtered(lambda l: l.account_id == inc_b)
        self.assertEqual(len(la), 1)
        self.assertEqual(len(lb), 1)
        self.assertIn(la.id, by_code["01"]["aml_ids"])
        self.assertIn(lb.id, by_code["01"]["aml_ids"])

    def test_b03dn_two_cash_lines_shared_revenue_credit(self):
        """Hai dòng Nợ tiền, một dòng Có doanh thu — mỗi dòng tiền nhận đúng phần."""
        company = self.env.company
        bank_journal = self.company_data["default_journal_bank"]
        liq_a = bank_journal.default_account_id
        if liq_a.code != "1121":
            liq_a.code = "1121"
        liq_b = self.env["account.account"].create({
            "code": "1122",
            "name": "B03 second bank",
            "account_type": liq_a.account_type,
            "company_ids": [(6, 0, [company.id])],
        })
        rev = self.env["account.account"].create({
            "code": "5119",
            "name": "B03 shared rev",
            "account_type": "income",
            "company_ids": [(6, 0, [company.id])],
        })
        tpl = self.env.ref("l10n_vn_b03dn_direct_report.b03dn_template_tt200_direct")
        tpl.cash_account_ids = [(6, 0, [liq_a.id, liq_b.id])]

        self.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-07-05",
            "journal_id": bank_journal.id,
            "line_ids": [
                (0, 0, {"account_id": liq_a.id, "debit": 600, "credit": 0}),
                (0, 0, {"account_id": liq_b.id, "debit": 400, "credit": 0}),
                (0, 0, {"account_id": rev.id, "debit": 0, "credit": 1000}),
            ],
        }).action_post()

        engine = self.env["l10n.vn.b03dn.engine"]
        by_code = engine.compute_period(
            tpl, company, date(2025, 7, 1), date(2025, 7, 31),
        )["lines_by_code"]
        self.assertAlmostEqual(by_code["01"]["amount"], 1000.0, places=2)

    def test_b03dn_pure_interbank_no_leaf(self):
        """Chuyển tiền nội bộ giữa các TK tiền → không ghi nhận trên chỉ tiêu leaf."""
        company = self.env.company
        bank_journal = self.company_data["default_journal_bank"]
        liq_a = bank_journal.default_account_id
        if liq_a.code != "1121":
            liq_a.code = "1121"
        liq_b = self.env["account.account"].create({
            "code": "1123",
            "name": "B03 bank B",
            "account_type": liq_a.account_type,
            "company_ids": [(6, 0, [company.id])],
        })
        tpl = self.env.ref("l10n_vn_b03dn_direct_report.b03dn_template_tt200_direct")
        tpl.cash_account_ids = [(6, 0, [liq_a.id, liq_b.id])]

        self.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-07-06",
            "journal_id": bank_journal.id,
            "line_ids": [
                (0, 0, {"account_id": liq_a.id, "debit": 300, "credit": 0}),
                (0, 0, {"account_id": liq_b.id, "debit": 0, "credit": 300}),
            ],
        }).action_post()

        engine = self.env["l10n.vn.b03dn.engine"]
        by_code = engine.compute_period(
            tpl, company, date(2025, 7, 1), date(2025, 7, 31),
        )["lines_by_code"]
        self.assertAlmostEqual(by_code["01"]["amount"], 0.0, places=2)

    def test_b03dn_xlsx_html_strong_preserves_text(self):
        """Một đoạn HTML chỉ bọc <strong> phải ra đủ nội dung (tránh write_rich_string 2-token)."""
        xlsx = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]
        html = "<p><strong>I. Lưu chuyển tiền</strong></p>"
        runs = xlsx._b03dn_html_name_to_runs(html)
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0][0].startswith("I. Lưu"))
        self.assertTrue(runs[0][1])
        self.assertFalse(runs[0][2])

    def test_b03dn_line_name_visible_text(self):
        xlsx = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]
        self.assertFalse(xlsx._b03dn_line_name_has_visible_text(False))
        self.assertFalse(xlsx._b03dn_line_name_has_visible_text(""))
        self.assertFalse(xlsx._b03dn_line_name_has_visible_text("   "))
        self.assertFalse(xlsx._b03dn_line_name_has_visible_text("<p><br/></p>"))
        self.assertTrue(
            xlsx._b03dn_line_name_has_visible_text("<p><strong>X</strong></p>"),
        )

    def test_b03dn_line_shows_money_columns_skips_section_display_type(self):
        xlsx = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]
        spacer = SimpleNamespace(
            display_type="line_section",
            name="<p><strong>Tiêu đề</strong></p>",
        )
        self.assertFalse(xlsx._b03dn_line_shows_money_columns(spacer))
        leaf = SimpleNamespace(
            display_type=False,
            name="<p><strong>Tiêu đề</strong></p>",
        )
        self.assertTrue(xlsx._b03dn_line_shows_money_columns(leaf))

    def test_b03dn_row_name_style_flags_whole_line_strong_em(self):
        """Toàn dòng bọc strong+em → cột khác cùng hàng dùng đậm+nghiêng."""
        xlsx = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]
        html = "<p><strong><em>Lưu chuyển tiền thuần từ HĐKD</em></strong></p>"
        self.assertEqual(xlsx._b03dn_row_name_style_flags(html), (True, True))

    def test_b03dn_row_name_style_flags_mixed_runs_no_row_emphasis(self):
        """Chữ thường + đậm lẫn nhau → không ép đậm cả hàng (chỉ cột tên giữ rich text)."""
        xlsx = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]
        html = "<p>Phần <strong>đậm</strong> cuối</p>"
        self.assertEqual(xlsx._b03dn_row_name_style_flags(html), (False, False))

    def test_b03dn_effective_row_style_flags_or_bold_amounts(self):
        xlsx = self.env["report.l10n_vn_b03dn_direct_report.b03dn_direct_xlsx"]
        plain = SimpleNamespace(
            name="<p>Chỉ tiêu</p>",
            b03dn_report_bold_amounts=True,
        )
        self.assertEqual(xlsx._b03dn_effective_row_style_flags(plain), (True, False))
        strong = SimpleNamespace(
            name="<p><strong>Tổng</strong></p>",
            b03dn_report_bold_amounts=False,
        )
        self.assertEqual(xlsx._b03dn_effective_row_style_flags(strong), (True, False))
