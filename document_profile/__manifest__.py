# -*- coding: utf-8 -*-
{
    "name": "Document Profile",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Reusable document profiles: dossiers and reference↔code↔file mapping (extensible).",
    "author": "devluoicode",
    "license": "AGPL-3",
    "depends": ["base", "account", "document_knowledge"],
    "data": [
        "security/document_profile_groups.xml",
        "security/document_profile_security.xml",
        "security/ir.model.access.csv",
        "views/document_profile_dossier_views.xml",
        "views/document_profile_item_views.xml",
        "views/document_profile_set_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
}
