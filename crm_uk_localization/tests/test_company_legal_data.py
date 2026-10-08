from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCompanyLegalData(TransactionCase):
    def test_vat_number_required_for_active_vat_payer(self):
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                {
                    "name": "UA VAT Test Company",
                    "l10n_ua_vat_registered": True,
                }
            )

    def test_vat_number_must_have_twelve_digits_for_ua_organization(self):
        ua = self.env.ref("base.ua")
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "UA VAT Invalid Number",
                    "is_company": True,
                    "country_id": ua.id,
                    "l10n_ua_vat_registered": True,
                    "l10n_ua_vat_number": "12345678",
                }
            )

    def test_cancelled_vat_registration_keeps_historical_number(self):
        company = self.env["res.company"].create(
            {
                "name": "UA Former VAT Payer",
                "l10n_ua_vat_registered": False,
                "l10n_ua_vat_number": "123456789012",
                "l10n_ua_vat_registration_date": "2020-01-01",
                "l10n_ua_vat_cancellation_date": "2025-01-01",
            }
        )
        self.assertEqual(company.l10n_ua_vat_number, "123456789012")
        self.assertEqual(
            company.partner_id.l10n_ua_vat_number,
            "123456789012",
        )

    def test_partner_kveds_are_persisted(self):
        main_kved = self.env["l10n_ua.kved"].create(
            {"code": "62.01", "name": "Комп'ютерне програмування"}
        )
        extra_kved = self.env["l10n_ua.kved"].create(
            {"code": "62.02", "name": "Консультування з питань інформатизації"}
        )
        partner = self.env["res.partner"].create(
            {
                "name": "UA KVED Partner",
                "is_company": True,
                "l10n_ua_main_kved_id": main_kved.id,
                "l10n_ua_kved_ids": [Command.set(extra_kved.ids)],
            }
        )

        partner.invalidate_recordset()
        reloaded = self.env["res.partner"].browse(partner.id)

        self.assertEqual(reloaded.l10n_ua_main_kved_id, main_kved)
        self.assertEqual(reloaded.l10n_ua_kved_ids, extra_kved)

    def test_company_kveds_are_stored_on_partner(self):
        main_kved = self.env["l10n_ua.kved"].create(
            {"code": "63.11", "name": "Оброблення даних"}
        )
        extra_kved = self.env["l10n_ua.kved"].create(
            {"code": "63.12", "name": "Веб-портали"}
        )
        company = self.env["res.company"].create(
            {
                "name": "UA Shared KVED Company",
                "l10n_ua_main_kved_id": main_kved.id,
                "l10n_ua_kved_ids": [Command.set(extra_kved.ids)],
            }
        )

        company.invalidate_recordset()
        company.partner_id.invalidate_recordset()

        self.assertEqual(company.l10n_ua_main_kved_id, main_kved)
        self.assertEqual(company.l10n_ua_kved_ids, extra_kved)
        self.assertEqual(
            company.partner_id.l10n_ua_main_kved_id,
            main_kved,
        )
        self.assertEqual(
            company.partner_id.l10n_ua_kved_ids,
            extra_kved,
        )

    def test_company_and_partner_share_legal_fields(self):
        company = self.env["res.company"].create(
            {
                "name": "UA Shared Legal Data",
                "l10n_ua_short_name": "UA Shared",
                "l10n_ua_tax_system": "general",
            }
        )

        self.assertEqual(
            company.partner_id.l10n_ua_short_name,
            "UA Shared",
        )

        company.partner_id.l10n_ua_short_name = "Changed on Contact"

        self.assertEqual(
            company.l10n_ua_short_name,
            "Changed on Contact",
        )

    def test_main_kved_must_not_be_duplicated(self):
        kved = self.env["l10n_ua.kved"].create(
            {"code": "64.19", "name": "Тестовий КВЕД"}
        )
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "UA KVED Test Company",
                    "is_company": True,
                    "l10n_ua_main_kved_id": kved.id,
                    "l10n_ua_kved_ids": [Command.set(kved.ids)],
                }
            )
