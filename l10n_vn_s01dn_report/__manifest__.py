{
    "name": "Nhật ký - Sổ Cái S01-DN (TT200)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Nhật ký - Sổ Cái theo mẫu S01-DN, Thông tư 200/2014/TT-BTC",
    "author": "Custom",
    "license": "AGPL-3",
    "depends": [
        "account_financial_report",
        "report_xlsx",
        "accounting_adecsol",
    ],
    "data": [
        "wizard/general_ledger_s01dn_inherit_view.xml",
        "views/account_report_menu.xml",
        "report/report.xml",
        "report/templates/general_ledger_s01dn.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_vn_s01dn_report/static/src/js/s01dn_gl_wizard_button.esm.js",
            "l10n_vn_s01dn_report/static/src/js/report_action.esm.js",
            "l10n_vn_s01dn_report/static/src/xml/report_action.xml",
        ],
    },
    "installable": True,
}
