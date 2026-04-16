/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    SectionAndNoteFieldOne2Many,
    SectionAndNoteListRenderer,
    sectionAndNoteFieldOne2Many,
} from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";

/**
 * B03-DN line one2many: same account section/note renderer (merged columns, hidden cells),
 * plus a row class hook for backend styling.
 */
export class B03dnTemplateLineListRenderer extends SectionAndNoteListRenderer {
    getRowClass(record) {
        return `${super.getRowClass(record)} o_b03dn_template_line_row`;
    }
}

export class B03dnTemplateLineOne2Many extends SectionAndNoteFieldOne2Many {
    static components = {
        ...SectionAndNoteFieldOne2Many.components,
        ListRenderer: B03dnTemplateLineListRenderer,
    };
}

const extraClasses = [
    ...(sectionAndNoteFieldOne2Many.additionalClasses || []),
    "o_field_b03dn_template_lines",
];

export const b03dnTemplateLineOne2Many = {
    ...sectionAndNoteFieldOne2Many,
    component: B03dnTemplateLineOne2Many,
    additionalClasses: extraClasses,
};

registry.category("fields").add("b03dn_template_line_one2many", b03dnTemplateLineOne2Many);
