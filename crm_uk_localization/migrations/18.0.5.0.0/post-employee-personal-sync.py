import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)
SYNC_CONTEXT_KEY = "l10n_ua_skip_employee_partner_sync"
SNAPSHOT_TABLE = "crm_uk_localization_employee_1805_snapshot"

PARTNER_FIELDS = {
    "marital": "l10n_ua_marital",
    "spouse_complete_name": "l10n_ua_spouse_complete_name",
    "spouse_birthdate": "l10n_ua_spouse_birthdate",
    "children": "l10n_ua_children",
    "ssnid": "l10n_ua_ssnid",
    "sinid": "l10n_ua_sinid",
    "permit_no": "l10n_ua_permit_no",
    "visa_no": "l10n_ua_visa_no",
    "visa_expire": "l10n_ua_visa_expire",
    "work_permit_expiration_date": "l10n_ua_work_permit_expiration_date",
    "additional_note": "l10n_ua_additional_note",
    "certificate": "l10n_ua_certificate",
    "study_field": "l10n_ua_study_field",
    "study_school": "l10n_ua_study_school",
    "emergency_contact": "l10n_ua_emergency_contact",
    "emergency_phone": "l10n_ua_emergency_phone",
}


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    return bool(cr.fetchone()[0])


def _present(value):
    return value not in (None, False, "", 0)


def migrate(cr, version):
    if not version:
        return
    if not _table_exists(cr, SNAPSHOT_TABLE):
        raise RuntimeError(f"Missing migration snapshot table: {SNAPSHOT_TABLE}")

    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].with_context(active_test=False).sudo()

    cr.execute(f"SELECT * FROM {SNAPSHOT_TABLE} ORDER BY employee_id")
    columns = [description[0] for description in cr.description]
    rows = [dict(zip(columns, row)) for row in cr.fetchall()]

    migrated = 0
    values_written = 0

    for snapshot in rows:
        employee = Employee.browse(snapshot["employee_id"]).exists()
        if not employee:
            continue
        if not employee.work_contact_id:
            raise RuntimeError(
                "Employee has no work contact during 18.0.5 migration: "
                f"employee={employee.id}"
            )

        partner = employee.work_contact_id.sudo()
        values = {}

        for old_field, partner_field in PARTNER_FIELDS.items():
            old_value = snapshot.get(old_field)
            if _present(old_value):
                values[partner_field] = old_value

        if (
            not employee.user_id
            and employee.company_id.partner_id
            and not partner.parent_id
        ):
            values["parent_id"] = employee.company_id.partner_id.id
            values["type"] = "contact"

        if values:
            partner.with_context(**{SYNC_CONTEXT_KEY: True}).write(values)
            values_written += len(values)

        employee.with_context(
            **{SYNC_CONTEXT_KEY: True}
        )._l10n_ua_sync_identity_to_contact()

        migrated += 1

    cr.execute(f"DROP TABLE {SNAPSHOT_TABLE}")

    _logger.info(
        "crm_uk_localization 18.0.5 employee/contact full synchronization complete: "
        "%s employees migrated, %s personal values moved to contacts",
        migrated,
        values_written,
    )
