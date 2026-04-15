/** @odoo-module **/
import { ReportAction } from "@web/webclient/actions/reports/report_action";
import { patch } from "@web/core/utils/patch";

patch(ReportAction.prototype, {
    // Hàm xử lý khi bấm nút B01-DN
    async onExecuteB01DN() {
        // Lấy wizard_id từ context của action hiện tại
        const wizardId = this.props.context.active_id || this.props.data?.context?.active_id;
        
        if (!wizardId) {
            console.error("Không tìm thấy Wizard ID để xuất báo cáo!");
            return;
        }

        return this.env.services.action.doAction({
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: "accounting_adecsol.balance_sheet_xlsx",
            report_file: "Bang_Can_Doi_Ke_Toan_B01_DN",
            data: this.props.data || {},
            context: { ...this.props.context, active_id: wizardId },
        });
    }
});