SNAPSHOT_TABLE = "crm_uk_localization_employee_1805_snapshot"

SNAPSHOT_COLUMNS = (
    "id AS employee_id",
    "marital",
    "spouse_complete_name",
    "spouse_birthdate",
    "children",
    "ssnid",
    "sinid",
    "permit_no",
    "visa_no",
    "visa_expire",
    "work_permit_expiration_date",
    "additional_note",
    "certificate",
    "study_field",
    "study_school",
    "emergency_contact",
    "emergency_phone",
)


def migrate(cr, version):
    if not version:
        return

    cr.execute(f"DROP TABLE IF EXISTS {SNAPSHOT_TABLE}")
    cr.execute(
        f"""
        CREATE TABLE {SNAPSHOT_TABLE} AS
        SELECT {", ".join(SNAPSHOT_COLUMNS)}
        FROM hr_employee
        """
    )
