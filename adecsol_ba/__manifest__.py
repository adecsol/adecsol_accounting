# -*- coding: utf-8 -*-
{
    "name": "ADEC Solutions — Business Analysis Process (P5)",
    "version": "18.0.1.14.0",
    "category": "Project",
    "summary": "Digitize the P5 Business Analysis workflow: Survey → FSD → Sign-off → Handover → WBS",
    "description": """
Digitize full P5 Business Analysis process:
=========================================================
* A.1  Interview — Meeting Minutes (MoM)
* A.2  AS-IS Analysis — Customer Survey
* B.1  TO-BE Design — Approve Document Page
* B.2  Gap-Fit Analysis — FIT/GAP on Project Task
* C.1  Write Document FSD — Functional Specification Document
* C.2  Setup Master Data — Validate MST, HS Code
* D.1  Customer Approve — Portal Signature
* D.2  Technical Handover — Mapping FSD → Handover
* E.1  Update plan — WBS Roll-up Progress
    """,
    "author": "ADEC Solutions",
    "website": "https://adecsolutions.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "portal",
        "project",
        "calendar",
        "hr_timesheet",
        "document_page",
        "document_page_project",
        "document_page_approval",
        "document_url",
        "document_profile",
    ],
    "data": [
        # security
        "security/ba_security.xml",
        "security/ir.model.access.csv",
        # data
        "data/document_page_data.xml",
        "data/mail_templates.xml",
        "data/ba_knowledge_template_data.xml",
        # wizards
        "wizard/handover_mapping_views.xml",
        "wizard/ba_template_preview_views.xml",
        # views
        "views/ba_mom_views.xml",
        "views/ba_customer_survey_views.xml",
        "views/document_page_views.xml",
        "views/ba_fitgap_views.xml",
        "views/ba_fsd_views.xml",
        "views/ba_master_data_views.xml",
        "views/project_task_views.xml",
        "views/calendar_event_views.xml",
        "views/project_project_views.xml",
        "views/portal_templates.xml",
        "views/res_partner_industry_views.xml",
        "views/ba_handover_views.xml",
        "views/ba_dashboard_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "adecsol_ba/static/src/js/goto_wbs_page.js",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
