/** @odoo-module **/
import { FinancialReportAction } from "@account_financial_report/js/financial_report_action";
import { patch } from "@web/core/utils/patch";

patch(FinancialReportAction.prototype, {
    async onExecuteB01DN() {
        const wizardId = this.action.context.active_id;
        return this.actionService.doAction({
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: "accounting_adecsol.balance_sheet_xlsx",
            report_file: "Bang_Can_Doi_Ke_Toan_B01_DN",
            context: { active_id: wizardId },
        });
    }
});