/** @odoo-module **/
import { ReportAction } from "@web/webclient/actions/reports/report_action";
import { patch } from "@web/core/utils/patch";

patch(ReportAction.prototype, {
    async onExecuteB01DN() {
        const wizardId = this.props.context.active_id || this.props.data?.context?.active_id;

        if (!wizardId) {
            console.error("No wizard id in context; cannot export report.");
            return;
        }

        return this.env.services.action.doAction({
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: "accounting_adecsol.balance_sheet_xlsx",
            report_file: "Balance_sheet_B01_DN",
            data: this.props.data || {},
            context: { ...this.props.context, active_id: wizardId },
        });
    }
});