def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_partner partner
           SET l10n_ua_short_name = company.l10n_ua_short_name,
               l10n_ua_kopfg_id = company.l10n_ua_kopfg_id,
               l10n_ua_legal_status = company.l10n_ua_legal_status,
               l10n_ua_registration_date = company.l10n_ua_registration_date,
               l10n_ua_edr_record_number = company.l10n_ua_edr_record_number,
               l10n_ua_last_registration_action_date =
                   company.l10n_ua_last_registration_action_date,
               l10n_ua_tax_system = company.l10n_ua_tax_system,
               l10n_ua_single_tax_group =
                   company.l10n_ua_single_tax_group,
               l10n_ua_single_tax_rate =
                   company.l10n_ua_single_tax_rate,
               l10n_ua_tax_authority = company.l10n_ua_tax_authority,
               l10n_ua_vat_registered =
                   company.l10n_ua_vat_registered,
               l10n_ua_vat_number = company.l10n_ua_vat_number,
               l10n_ua_vat_registration_date =
                   company.l10n_ua_vat_registration_date,
               l10n_ua_vat_cancellation_date =
                   company.l10n_ua_vat_cancellation_date,
               l10n_ua_main_kved_id =
                   company.l10n_ua_main_kved_id,
               l10n_ua_currency_id = company.currency_id,
               l10n_ua_statutory_capital =
                   company.l10n_ua_statutory_capital,
               l10n_ua_manager_partner_id =
                   company.l10n_ua_manager_partner_id,
               l10n_ua_manager_position =
                   company.l10n_ua_manager_position,
               l10n_ua_manager_appointment_date =
                   company.l10n_ua_manager_appointment_date,
               l10n_ua_manager_authority_basis =
                   company.l10n_ua_manager_authority_basis,
               l10n_ua_manager_authority_basis_note =
                   company.l10n_ua_manager_authority_basis_note,
               l10n_ua_representation_restrictions =
                   company.l10n_ua_representation_restrictions
          FROM res_company company
         WHERE partner.id = company.partner_id
        """
    )

    cr.execute(
        """
        INSERT INTO res_partner_l10n_ua_kved_rel (
            partner_id,
            kved_id
        )
        SELECT company.partner_id,
               legacy.kved_id
          FROM res_company_l10n_ua_kved_rel legacy
          JOIN res_company company
            ON company.id = legacy.company_id
         WHERE NOT EXISTS (
               SELECT 1
                 FROM res_partner_l10n_ua_kved_rel current_rel
                WHERE current_rel.partner_id = company.partner_id
                  AND current_rel.kved_id = legacy.kved_id
         )
        """
    )

    cr.execute(
        """
        SELECT count(*)
          FROM res_company_l10n_ua_kved_rel legacy
          JOIN res_company company
            ON company.id = legacy.company_id
          LEFT JOIN res_partner_l10n_ua_kved_rel current_rel
            ON current_rel.partner_id = company.partner_id
           AND current_rel.kved_id = legacy.kved_id
         WHERE current_rel.partner_id IS NULL
        """
    )
    missing_kveds = cr.fetchone()[0]

    if missing_kveds:
        raise RuntimeError(
            f"KVED migration incomplete: {missing_kveds} "
            "relations were not migrated"
        )
