/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { pick } from "@web/core/utils/objects";
import { ViewButton } from "@web/views/view_button/view_button";
import { onWillUnmount } from "@odoo/owl";

const GL_WIZARD_MODEL = "general.ledger.report.wizard";
/** Một lần: QWeb; hai lần nhanh: Excel — cùng tên nút với server để debounce. */
const S01DN_QWEB_BTN = "button_view_s01dn_html";
const S01DN_XLSX = "button_export_s01dn_xlsx";
/** Hai lần nhấp liên tiếp trong khoảng này → xuất Excel (tương đương double-click). */
const DOUBLE_CLICK_MS = 320;

patch(ViewButton.prototype, {
    setup() {
        super.setup(...arguments);
        this._s01dnPendingTimer = null;
        onWillUnmount(() => {
            if (this._s01dnPendingTimer) {
                clearTimeout(this._s01dnPendingTimer);
                this._s01dnPendingTimer = null;
            }
        });
    },

    onClick(ev) {
        const rec = this.props.record;
        if (
            this.clickParams?.name === S01DN_QWEB_BTN &&
            rec?.resModel === GL_WIZARD_MODEL
        ) {
            if (this.props.tag === "a") {
                ev.preventDefault();
            }
            if (this._s01dnPendingTimer) {
                clearTimeout(this._s01dnPendingTimer);
                this._s01dnPendingTimer = null;
                return this._s01dnRunViewButton(S01DN_XLSX);
            }
            this._s01dnPendingTimer = setTimeout(() => {
                this._s01dnPendingTimer = null;
                this._s01dnRunViewButton(S01DN_QWEB_BTN);
            }, DOUBLE_CLICK_MS);
            return;
        }
        return super.onClick(...arguments);
    },

    _s01dnRunViewButton(methodName) {
        return this.env.onClickViewButton({
            clickParams: { ...this.clickParams, name: methodName },
            getResParams: () =>
                pick(
                    this.props.record || {},
                    "context",
                    "evalContext",
                    "resModel",
                    "resId",
                    "resIds",
                ),
            beforeExecute: () => this.dropdownControl.close(),
        });
    },
});
