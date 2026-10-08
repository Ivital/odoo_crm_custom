def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        ALTER TABLE l10n_ua_kved
        DROP CONSTRAINT IF EXISTS l10n_ua_kved_code_unique
        """
    )

    # Preserve values from the old stored hr.employee columns before they are
    # converted into writable related fields backed by work_contact_id.
    cr.execute(
        """
        DROP TABLE IF EXISTS crm_uk_localization_employee_1804_snapshot
        """
    )
    cr.execute(
        """
        CREATE TABLE crm_uk_localization_employee_1804_snapshot AS
        SELECT
            id AS employee_id,
            private_street,
            private_street2,
            private_city,
            private_state_id,
            private_zip,
            private_country_id,
            private_phone,
            private_email,
            country_id,
            gender,
            birthday,
            place_of_birth,
            country_of_birth,
            identification_id,
            passport_id
        FROM hr_employee
        """
    )
