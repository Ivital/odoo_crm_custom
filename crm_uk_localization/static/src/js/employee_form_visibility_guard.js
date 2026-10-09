/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Record } from "@web/model/relational_model/record";
import { EmployeeFormController } from "@hr/views/form_view";

function getUnloadedX2ManyFields(record) {
    return Object.keys(record.activeFields).filter((fieldName) => {
        const field = record.fields[fieldName];
        return Boolean(
            field &&
                ["one2many", "many2many"].includes(field.type) &&
                !field.relatedPropertyField &&
                !record.data[fieldName]
        );
    });
}

function withoutFields(source, excluded) {
    const excludedSet = new Set(excluded);
    return Object.fromEntries(
        Object.entries(source).filter(([fieldName]) => !excludedSet.has(fieldName))
    );
}

/**
 * Odoo 18 FormController.beforeVisibilityChange() assumes every active x2many
 * field is already materialized in root.data. The Employee form can temporarily
 * violate that assumption while relational fields are lazy-loaded.
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
 * Guard Employee Record internals against transient active x2many fields that
 * have not yet been materialized in record.data.
 *
 * IMPORTANT: DataPoint.activeFields is a getter-only property in Odoo 18.
 * Therefore we must update record.config.activeFields temporarily rather than
 * assigning record.activeFields directly.
 */
patch(Record.prototype, {
    _checkValidity(...args) {
        if (this.resModel !== "hr.employee") {
            return super._checkValidity(...args);
        }

        const unloaded = getUnloadedX2ManyFields(this);
        if (!unloaded.length) {
            return super._checkValidity(...args);
        }

        const originalActiveFields = this.config.activeFields;
        this.config.activeFields = withoutFields(originalActiveFields, unloaded);

        try {
            return super._checkValidity(...args);
        } finally {
            this.config.activeFields = originalActiveFields;
        }
    },

    async _save(...args) {
        if (this.resModel !== "hr.employee") {
            return super._save(...args);
        }

        const unloaded = getUnloadedX2ManyFields(this);
        if (!unloaded.length) {
            return super._save(...args);
        }

        const originalActiveFields = this.config.activeFields;
        this.config.activeFields = withoutFields(originalActiveFields, unloaded);

        try {
            return await super._save(...args);
        } finally {
            this.config.activeFields = originalActiveFields;
        }
    },
});
