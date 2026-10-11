def migrate(cr, version):
    # Odoo installations can expose the legacy SQL constraint
    # either with the table prefix or with the logical name.
    # Drop both safely before the new year-scoped constraint
    # is installed by the ORM.
    cr.execute(
        """
        ALTER TABLE hr_personnel_order
        DROP CONSTRAINT IF EXISTS
        hr_personnel_order_number_company_unique
        """
    )
    cr.execute(
        """
        ALTER TABLE hr_personnel_order
        DROP CONSTRAINT IF EXISTS
        number_company_unique
        """
    )
