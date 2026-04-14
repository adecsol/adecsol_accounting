/** @odoo-module **/

import { ReportAction } from "@web/webclient/actions/reports/report_action";
import { patch } from "@web/core/utils/patch";

const S01DN_HTML_REPORT = "l10n_vn_s01dn_report.general_ledger_s01dn";
const S01DN_XLSX_REPORT = "l10n_vn_s01dn_report.general_ledger_s01dn_xlsx";

patch(ReportAction.prototype, {
    get isS01dnHtmlReport() {
        return this.props.report_name === S01DN_HTML_REPORT;
    },

    /**
     * Xuất Excel TT200 thay cho in PDF khi xem báo cáo HTML S01-DN (tổng hợp).
     * Gộp snapshot bộ lọc từ iframe (__s01dnGetFilterSnapshot) để file Excel khớp màn hình.
     */
    exportS01dnTT200() {
        let uiFilters = null;
        try {
            const iframeEl = this.iframe?.el;
            const win = iframeEl?.contentWindow;
            if (win && typeof win.__s01dnGetFilterSnapshot === "function") {
                uiFilters = win.__s01dnGetFilterSnapshot();
            }
        } catch {
            uiFilters = null;
        }
        const baseData = { ...(this.props.data || {}) };
        if (uiFilters !== null && typeof uiFilters === "object") {
            baseData.s01dn_ui_filters = uiFilters;
        }
        this.action.doAction({
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: S01DN_XLSX_REPORT,
            report_file: "Nhat_ky_So_Cai_S01_DN",
            data: baseData,
            // report_xlsx action handler JSON.stringify(context) for the URL; pass an object.
            context: this.props.context || {},
            display_name: this.title,
        });
    },

    /** In HTML trong iframe (beforeprint trong báo cáo tách trang theo TK). */
    printS01dnBrowser() {
        const win = this.iframe?.el?.contentWindow;
        if (!win) {
            return;
        }
        if (typeof win.__s01dnConfirmPrintBeforeDialog === "function") {
            if (!win.__s01dnConfirmPrintBeforeDialog()) {
                return;
            }
        }
        // Cho iframe kịp dựng header/footer in (beforeprint + layout) trước hộp thoại in
        const raf = win.requestAnimationFrame.bind(win);
        raf(() => {
            raf(() => {
                win.print();
            });
        });
    },
});
