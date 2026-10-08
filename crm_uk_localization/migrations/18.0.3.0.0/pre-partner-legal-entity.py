def migrate(cr, version):
    tables = [
        "l10n_ua_company_authorized_person",
        "l10n_ua_company_participant",
        "l10n_ua_company_beneficial_owner",
    ]

    for table in tables:
        cr.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS legal_entity_id integer"
        )
        cr.execute(
            f"""
            UPDATE {table} line
               SET legal_entity_id = company.partner_id
              FROM res_company company
             WHERE line.company_id = company.id
               AND line.legal_entity_id IS NULL
            """
        )

        cr.execute(
            f"SELECT count(*) FROM {table} "
            "WHERE legal_entity_id IS NULL"
        )
        missing = cr.fetchone()[0]

        if missing:
            raise RuntimeError(
                f"{table}: {missing} rows cannot be linked "
                "to a legal entity partner"
            )
