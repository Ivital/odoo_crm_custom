/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { EmployeeFormController } from "@hr/views/form_view";

/**
 * Odoo 18 FormController.beforeVisibilityChange() assumes every active x2many
 * field already has a relational value in root.data. On the Employee form that
 * invariant can be temporarily false while tabs/fields are being loaded or the
 * browser visibility changes, which makes core code dereference
 * `undefined.editedRecord`.
 *
 * Keep Odoo's original autosave semantics, but treat an absent x2many value as
 * "not currently editing an x2many record".
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
