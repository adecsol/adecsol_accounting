{
    "name": "Vietnam Chart of Accounts - TT200 (Odoo 18)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Vietnam COA according to Circular 200/2014 (TT200) & TT99/2025",
    "author": "Custom",
    "license": "AGPL-3",
    "depends": [
        "account",
        "account_financial_report",  # Required for OCA JS/XML inheritance
        "report_xlsx",
        "account_fiscal_year_closing",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/closing_template_tt200.xml",
        "wizard/trial_balance_wizard_view.xml",
        # "wizard/balance_sheet_tt200_view.xml",
        "wizard/balance_sheet_wizard_view.xml",
        "wizard/profit_loss_wizard_view.xml",
        "report/report.xml",
        "views/account_fiscalyear_closing_view.xml",
        "views/account_report_actions.xml",
        "views/account_report_menu.xml",
    ],
    # "assets": {
    #     "web.assets_backend": [
    #         # Nạp JS trước để xử lý logic, sau đó nạp XML để hiển thị nút
    #         "accounting_adecsol/static/src/js/financial_report_action.js",
    #         "accounting_adecsol/static/src/xml/financial_report_buttons.xml",
    #     ],
    # },
    "installable": True,
    "application": True,
}
