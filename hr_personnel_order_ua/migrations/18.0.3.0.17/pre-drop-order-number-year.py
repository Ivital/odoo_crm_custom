def migrate(cr, version):
    # Legal order number/year is a business attribute, not
    # the idempotency identity of an archival source row.
    # source_key + company remains the deterministic import
    # identity.
    cr.execute(
        """
        ALTER TABLE hr_personnel_order
        DROP CONSTRAINT IF EXISTS
            hr_personnel_order_number_company_year_unique
        """
    )

    cr.execute(
        """
        ALTER TABLE hr_personnel_order
        DROP CONSTRAINT IF EXISTS
            number_company_year_unique
        """
    )

    cr.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            hr_personnel_order_current_number_company_year_uidx
        ON hr_personnel_order (
            number,
            company_id,
            order_year
        )
        WHERE entry_mode = 'current'
        """
    )
