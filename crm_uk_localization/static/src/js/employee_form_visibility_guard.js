/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Record } from "@web/model/relational_model/record";
import { EmployeeFormController } from "@hr/views/form_view";

function isUnloadedX2Many(record, fieldName) {
    const field = record.fields[fieldName];
    return Boolean(
        field &&
            ["one2many", "many2many"].includes(field.type) &&
            !field.relatedPropertyField &&
            !record.data[fieldName]
    );
}

/**
 * Odoo 18 FormController.beforeVisibilityChange() assumes every active x2many
 * field already has a relational value in root.data. On the Employee form that
 * invariant can temporarily be false while lazy form data is being loaded.
 */
patch(EmployeeFormController.prototype, {
    beforeVisibilityChange() {
        const root = this.model.root;

        const isEditingX2Many = Object.keys(root.activeFields).some((fieldName) => {
            const field = root.fields[fieldName];
            const value = root.data[fieldName];

            return Boolean(
                field &&
                    ["one2many", "many2many"].includes(field.type) &&
                    !field.relatedPropertyField &&
                    value &&
                    value.editedRecord
            );
        });

        if (
            document.visibilityState === "hidden" &&
            this.formInDialog === 0 &&
            !isEditingX2Many
        ) {
            return root.save();
        }
    },
});

/**
 * The same Odoo 18 assumption exists inside Record._save():
 *
 *     this.data[fieldName]._abandonRecords()
 *
 * If an Employee x2many is active but has not been materialized in `data`,
 * autosave/manual save crashes before any RPC is made. Temporarily exclude only
 * those unloaded x2many fields from the save specification. They contain no
 * client-side value and therefore no changes to persist.
 */
patch(Record.prototype, {
    async _save(...args) {
        if (this.resModel !== "hr.employee") {
            return super._save(...args);
        }

        const unloaded = new Set(
            Object.keys(this.activeFields).filter((fieldName) =>
                isUnloadedX2Many(this, fieldName)
            )
        );

        if (!unloaded.size) {
            return super._save(...args);
        }

        const originalActiveFields = this.activeFields;
        this.activeFields = Object.fromEntries(
            Object.entries(originalActiveFields).filter(
                ([fieldName]) => !unloaded.has(fieldName)
            )
        );

        try {
            return await super._save(...args);
        } finally {
            this.activeFields = originalActiveFields;
        }
    },
});
