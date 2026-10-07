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

    def test_vat_number_must_have_twelve_digits(self):
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                {
                    "name": "UA VAT Invalid Number",
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

    def test_main_kved_must_not_be_duplicated(self):
        kved = self.env["l10n_ua.kved"].create(
            {"code": "62.01", "name": "Тестовий КВЕД"}
        )
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                {
                    "name": "UA KVED Test Company",
                    "l10n_ua_main_kved_id": kved.id,
                    "l10n_ua_kved_ids": [(6, 0, [kved.id])],
                }
            )
