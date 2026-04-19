#!/usr/bin/env python3

model_project_links = {
    "ba.mom": "project_id",
    "ba.customer.survey": "project_id",
    "ba.fitgap": "project_id",
    "ba.fsd": "project_id",
    "ba.master.data": "project_id",
    "ba.handover": "project_id",
    "ba.project.team": "project_id",
    
    "ba.fsd.feature": "fsd_id.project_id",
    "ba.master.data.line": "master_data_id.project_id",
    "ba.handover.line": "handover_id.project_id",
    "ba.wbs.checklist": "task_id.project_id",
}

xml = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="module_category_ba_process" model="ir.module.category">
        <field name="name">BA Process</field>
        <field name="description">Business Analysis Process Management</field>
        <field name="sequence">50</field>
    </record>

    <!-- Base internal group -->
    <record id="group_ba_user" model="res.groups">
        <field name="name">BA Internal User</field>
        <field name="category_id" ref="module_category_ba_process"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <!-- Portal group -->
    <record id="group_ba_customer" model="res.groups">
        <field name="name">BA Customer (Portal)</field>
        <field name="category_id" ref="module_category_ba_process"/>
        <field name="implied_ids" eval="[(4, ref('base.group_portal'))]"/>
    </record>

    <data noupdate="0">
"""

for m, pref in model_project_links.items():
    safe_name = m.replace(".", "_")
    
    xml += f"""
        <!-- {m} -->
        <record id="rule_{safe_name}_read" model="ir.rule">
            <field name="name">{m}: Read for project members</field>
            <field name="model_id" ref="model_{safe_name}"/>
            <field name="domain_force">['|', '|', '|', ('{pref}.ba_manager_id', '=', user.id), ('{pref}.user_id', '=', user.id), ('{pref}.ba_user_ids', 'in', [user.id]), ('{pref}.ba_developer_ids', 'in', [user.id])]</field>
            <field name="groups" eval="[(4, ref('group_ba_user'))]"/>
            <field name="perm_read" eval="True"/>
            <field name="perm_write" eval="False"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_unlink" eval="False"/>
        </record>

        <record id="rule_{safe_name}_write" model="ir.rule">
            <field name="name">{m}: Write/Create for BA or PM</field>
            <field name="model_id" ref="model_{safe_name}"/>
            <field name="domain_force">['|', '|', ('{pref}.ba_manager_id', '=', user.id), ('{pref}.user_id', '=', user.id), ('{pref}.ba_user_ids', 'in', [user.id])]</field>
            <field name="groups" eval="[(4, ref('group_ba_user'))]"/>
            <field name="perm_read" eval="False"/>
            <field name="perm_write" eval="True"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_unlink" eval="False"/>
        </record>

        <record id="rule_{safe_name}_unlink" model="ir.rule">
            <field name="name">{m}: Unlink for Manager</field>
            <field name="model_id" ref="model_{safe_name}"/>
            <field name="domain_force">[('{pref}.ba_manager_id', '=', user.id)]</field>
            <field name="groups" eval="[(4, ref('group_ba_user'))]"/>
            <field name="perm_read" eval="False"/>
            <field name="perm_write" eval="False"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_unlink" eval="True"/>
        </record>
"""

xml += """
        <!-- Portal FSD Rule -->
        <record id="rule_ba_fsd_portal" model="ir.rule">
            <field name="name">BA FSD: Portal Customer</field>
            <field name="model_id" ref="model_ba_fsd"/>
            <field name="domain_force">[('state', 'in', ['pending_signoff', 'approved']), ('project_id.message_partner_ids', 'in', [user.partner_id.id])]</field>
            <field name="groups" eval="[(4, ref('group_ba_customer'))]"/>
            <field name="perm_read" eval="True"/>
            <field name="perm_write" eval="True"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_unlink" eval="False"/>
        </record>
    </data>
</odoo>
"""

with open("/home/ngocphat/github/adecsol/adecsol_ba/security/ba_security.xml", "w") as f:
    f.write(xml)
