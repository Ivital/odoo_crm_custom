from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCompanyLegalData(TransactionCase):
    def _test_kved(self, code, name="Тестовий вид діяльності"):
        return self.env["l10n_ua.kved"].create(
            {
                "classifier": "nace_2_1_ua",
                "code": code,
                "name": name,
                "selectable": True,
            }
        )

    def test_reference_data_loaded(self):
        self.assertGreaterEqual(
            self.env["l10n_ua.kved"].search_count(
                [("classifier", "=", "kved_2010")]
            ),
            615,
        )
        fop = self.env["l10n_ua.kopfg"].search([("code", "=", "910")], limit=1)
        self.assertTrue(fop)
        self.assertTrue(fop.selectable)

    def test_vat_number_required_for_active_vat_payer(self):
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                {"name": "UA VAT Test Company", "l10n_ua_vat_registered": True}
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

    def test_partner_kveds_are_persisted(self):
        main_kved = self._test_kved("T.01")
        extra_kved = self._test_kved("T.02")
        partner = self.env["res.partner"].create(
            {
                "name": "UA KVED Partner",
                "is_company": True,
                "l10n_ua_activity_classifier": "nace_2_1_ua",
                "l10n_ua_main_kved_id": main_kved.id,
                "l10n_ua_kved_ids": [Command.set(extra_kved.ids)],
            }
        )
        partner.invalidate_recordset()
        reloaded = self.env["res.partner"].browse(partner.id)
        self.assertEqual(reloaded.l10n_ua_main_kved_id, main_kved)
        self.assertEqual(reloaded.l10n_ua_kved_ids, extra_kved)

    def test_company_kveds_are_stored_on_partner(self):
        main_kved = self._test_kved("T.11")
        extra_kved = self._test_kved("T.12")
        company = self.env["res.company"].create(
            {
                "name": "UA Shared KVED Company",
                "l10n_ua_activity_classifier": "nace_2_1_ua",
                "l10n_ua_main_kved_id": main_kved.id,
                "l10n_ua_kved_ids": [Command.set(extra_kved.ids)],
            }
        )
        company.invalidate_recordset()
        company.partner_id.invalidate_recordset()
        self.assertEqual(company.l10n_ua_main_kved_id, main_kved)
        self.assertEqual(company.partner_id.l10n_ua_main_kved_id, main_kved)
        self.assertEqual(company.partner_id.l10n_ua_kved_ids, extra_kved)

    def test_fop_is_physical_person_with_kopfg_910(self):
        partner = self.env["res.partner"].create(
            {"name": "Тестовий ФОП", "l10n_ua_is_fop": True}
        )
        self.assertFalse(partner.is_company)
        self.assertEqual(partner.company_type, "person")
        self.assertEqual(partner.l10n_ua_kopfg_id.code, "910")
        self.assertEqual(partner.l10n_ua_legal_status, "active")

    def test_plain_person_cannot_have_kved(self):
        kved = self._test_kved("T.21")
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Фізична особа без ФОП",
                    "l10n_ua_activity_classifier": "nace_2_1_ua",
                    "l10n_ua_main_kved_id": kved.id,
                }
            )

    def test_main_kved_must_not_be_duplicated(self):
        kved = self._test_kved("T.31")
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "UA KVED Test Company",
                    "is_company": True,
                    "l10n_ua_activity_classifier": "nace_2_1_ua",
                    "l10n_ua_main_kved_id": kved.id,
                    "l10n_ua_kved_ids": [Command.set(kved.ids)],
                }
            )

    def test_employee_personal_data_uses_work_contact(self):
        employee = self.env["hr.employee"].create(
            {"name": "Employee Contact Sync Test"}
        )
        employee.write(
            {
                "private_email": "private@example.test",
                "identification_id": "1234567890",
                "birthday": "1990-01-02",
            }
        )
        partner = employee.work_contact_id
        self.assertEqual(partner.l10n_ua_private_email, "private@example.test")
        self.assertEqual(partner.l10n_ua_rnokpp, "1234567890")
        self.assertEqual(str(partner.birthdate_date), "1990-01-02")

        partner.write(
            {
                "l10n_ua_private_email": "changed@example.test",
                "birthdate_date": "1991-03-04",
            }
        )
        self.assertEqual(employee.private_email, "changed@example.test")
        self.assertEqual(str(employee.birthday), "1991-03-04")

    def test_employee_and_contact_share_name(self):
        employee = self.env["hr.employee"].create({"name": "Original Name"})
        employee.name = "Changed Employee Name"
        self.assertEqual(employee.work_contact_id.name, "Changed Employee Name")
        employee.work_contact_id.name = "Changed Contact Name"
        self.assertEqual(employee.name, "Changed Contact Name")
