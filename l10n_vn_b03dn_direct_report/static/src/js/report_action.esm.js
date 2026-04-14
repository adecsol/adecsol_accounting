/** @odoo-module **/

import { ReportAction } from "@web/webclient/actions/reports/report_action";
import { patch } from "@web/core/utils/patch";
import { onWillUnmount } from "@odoo/owl";

const B03DN_HTML_REPORT = "l10n_vn_b03dn_direct_report.b03dn_direct";
const B03DN_XLSX_REPORT = "l10n_vn_b03dn_direct_report.b03dn_direct_xlsx";
/** Cùng lề @page với QWeb — lề dưới lớn hơn một chút để margin box “Trang xx/yy”. */
const B03DN_PRINT_PAGE_MARGIN = "20mm 20mm 24mm 30mm";
const B03DN_PRINT_MARGIN_STYLE_ID = "b03dn_print_margin_override";

const __reportActionPrintOriginal = ReportAction.prototype.print;
const __reportActionSetupOriginal = ReportAction.prototype.setup;

patch(ReportAction.prototype, {
    setup() {
        __reportActionSetupOriginal.call(this, ...arguments);
        if (this.props.report_name !== B03DN_HTML_REPORT) {
            return;
        }
        /** Drill-down sau khi AJAX thay DOM trong iframe — domain gửi như chuỗi (cùng kiểu report.esm enrich). */
        this._b03dnDrillMessageHandler = (ev) => {
            const data = ev?.data;
            if (!data) {
                return;
            }
            if (data.type === "b03dn_tm_document") {
                const attachmentId = data.attachmentId;
                if (!attachmentId) {
                    return;
                }
                this.env.services.action.doAction({
                    type: "ir.actions.act_url",
                    url: `/web/content/${attachmentId}?download=true`,
                    target: "new",
                });
                return;
            }
            if (data.type === "b03dn_tm_find_item") {
                const dossierId = data.dossierId;
                const fileCode = (data.fileCode || "").trim();
                if (!dossierId || !fileCode) {
                    return;
                }
                this.env.services.action.doAction({
                    type: "ir.actions.act_window",
                    name: fileCode,
                    res_model: "document.profile.item",
                    domain: [
                        ["dossier_id", "=", dossierId],
                        ["code", "=", fileCode],
                    ],
                    views: [
                        [false, "list"],
                        [false, "form"],
                    ],
                    target: "current",
                });
                return;
            }
            if (data.type !== "b03dn_drilldown") {
                return;
            }
            const resModel = data.resModel;
            const domain = data.domain;
            if (!resModel) {
                return;
            }
            this.env.services.action.doAction({
                type: "ir.actions.act_window",
                res_model: resModel,
                domain,
                name: resModel,
                views: [
                    [false, "list"],
                    [false, "form"],
                ],
            });
        };
        window.addEventListener("message", this._b03dnDrillMessageHandler);
        onWillUnmount(() => {
            window.removeEventListener("message", this._b03dnDrillMessageHandler);
        });
    },

    get isB03dnHtmlReport() {
        return this.props.report_name === B03DN_HTML_REPORT;
    },

    /**
     * B03-DN HTML: không gọi in PDF mặc định — chỉ in trình duyệt (A4 dọc, CSS QWeb).
     */
    print() {
        if (this.props.report_name === B03DN_HTML_REPORT) {
            this.printB03dnBrowser();
            return;
        }
        return __reportActionPrintOriginal.call(this);
    },

    /**
     * Xuất Excel — gộp snapshot từ iframe (__b03dnGetFilterSnapshot) để khớp màn hình / in.
     */
    exportB03dnXlsx() {
        let uiFilters = null;
        try {
            const iframeEl = this.iframe?.el;
            const win = iframeEl?.contentWindow;
            if (win && typeof win.__b03dnGetFilterSnapshot === "function") {
                uiFilters = win.__b03dnGetFilterSnapshot();
            }
        } catch {
            uiFilters = null;
        }
        const baseData = { ...(this.props.data || {}) };
        if (uiFilters !== null && typeof uiFilters === "object") {
            baseData.b03dn_ui_filters = uiFilters;
        }
        this.action.doAction({
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: B03DN_XLSX_REPORT,
            report_file: "B03_DN_LCTT",
            data: baseData,
            context: this.props.context || {},
            display_name: this.title,
        });
    },

    printB03dnBrowser() {
        const win = this.iframe?.el?.contentWindow;
        if (!win) {
            return;
        }
        const doc = win.document;
        /**
         * Reset margin/padding thân trang + giữ @page trùng QWeb (mọi trang in đều có lề).
         */
        const injectPrintMarginKill = () => {
            let st = doc.getElementById(B03DN_PRINT_MARGIN_STYLE_ID);
            if (!st) {
                st = doc.createElement("style");
                st.id = B03DN_PRINT_MARGIN_STYLE_ID;
                doc.head.appendChild(st);
            }
            st.textContent = `
@page {
  margin: ${B03DN_PRINT_PAGE_MARGIN} !important;
  size: A4 portrait !important;
  @bottom-right {
    content: "Trang " counter(page, decimal-leading-zero) " / " counter(pages, decimal-leading-zero);
    font-size: 9pt;
    font-family: Arial, Helvetica, sans-serif;
    color: #000;
    vertical-align: top;
    text-align: right;
    white-space: nowrap;
    padding: 0 0 2mm 0;
  }
}
#b03dnToolbar, #b03dnToolbar.b03dn-toolbar-screen-only {
  display: none !important;
  visibility: hidden !important;
}
html { margin: 0 !important; padding: 0 !important; }
body { margin: 0 !important; padding: 0 !important; }
#wrapwrap, #wrapwrap > main,
.o_action_manager, .o_action .o_content, .o_web_client .o_content,
body > .container, body > .container-fluid, .container, .container-fluid,
.page, .o_report_layout, .o_report_iframe {
  margin: 0 !important;
  padding: 0 !important;
  max-width: none !important;
  width: 100% !important;
  box-sizing: border-box !important;
}
`;
        };
        const removePrintMarginKill = () => {
            doc.getElementById(B03DN_PRINT_MARGIN_STYLE_ID)?.remove();
        };
        injectPrintMarginKill();
        win.addEventListener("afterprint", removePrintMarginKill, { once: true });
        const raf = win.requestAnimationFrame.bind(win);
        raf(() => {
            raf(() => {
                win.focus();
                win.print();
            });
        });
    },
});
