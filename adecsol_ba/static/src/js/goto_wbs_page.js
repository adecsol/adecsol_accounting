/** @odoo-module **/
import { registry } from "@web/core/registry";

/**
 * Client action: navigate to the project form and activate the WBS notebook page.
 */
async function gotoWbsPage(env, action) {
    const projectId = action.context && action.context.project_id;
    if (!projectId) return;

    await env.services.action.doAction({
        type: "ir.actions.act_window",
        res_model: "project.project",
        res_id: projectId,
        views: [[false, "form"]],
        target: "current",
    });

    // Wait for DOM render, then click the WBS tab
    const maxAttempts = 10;
    let attempt = 0;
    const tryClick = () => {
        attempt++;
        const tab = document.querySelector(
            '.o_notebook .nav-link[name="wbs_page"]'
        );
        if (tab) {
            tab.click();
        } else if (attempt < maxAttempts) {
            setTimeout(tryClick, 200);
        }
    };
    setTimeout(tryClick, 300);
}

registry.category("actions").add("goto_wbs_page", gotoWbsPage);
