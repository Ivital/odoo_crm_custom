from lxml import html as lxml_html

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestEmployeeEducation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "EDUCATION TEST Працівник",
                "company_id": cls.env.company.id,
            }
        )

    def _render_p2(self):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "hr_personnel_order_ua.action_report_personal_card_p2",
            self.employee.ids,
        )
        return html.decode() if isinstance(html, bytes) else html

    def test_employee_has_unlimited_normalized_education_records(self):
        Education = self.env["hr.employee.education"]

        values = [
            {
                "institution_name": "Навчальний заклад 1",
                "education_level": "vocational",
                "specialty": "Професія 1",
                "qualification": "Кваліфікація 1",
                "document_type": "Свідоцтво",
                "document_series": "АА",
                "document_number": "000001",
                "graduation_year": 1998,
                "study_form": "full_time",
            },
            {
                "institution_name": "Навчальний заклад 2",
                "education_level": "incomplete_higher",
                "specialty": "Спеціальність 2",
                "qualification": "Кваліфікація 2",
                "document_type": "Диплом",
                "document_series": "ББ",
                "document_number": "000002",
                "graduation_year": 2001,
                "study_form": "part_time",
            },
            {
                "institution_name": "Навчальний заклад 3",
                "education_level": "complete_higher",
                "specialty": "Спеціальність 3",
                "qualification": "Кваліфікація 3",
                "document_type": "Диплом",
                "document_number": "000003",
                "graduation_year": 2004,
            },
            {
                "institution_name": "Навчальний заклад 4",
                "education_level": "complete_higher",
                "specialty": "Спеціальність 4",
                "qualification": "Кваліфікація 4",
                "document_type": "Диплом",
                "document_number": "000004",
                "graduation_year": 2008,
            },
        ]

        for sequence, vals in enumerate(values, start=1):
            Education.create(
                {
                    "employee_id": self.employee.id,
                    "sequence": sequence * 10,
                    **vals,
                }
            )

        self.assertEqual(len(self.employee.l10n_ua_education_ids), 4)
        self.assertFalse(self.employee.study_school)
        self.assertFalse(self.employee.study_field)

        html = self._render_p2()
        root = lxml_html.fromstring(html)
        text = " ".join(root.text_content().split())

        school_rows = root.xpath(
            "//*[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' p2-education-school-row '"
            ")]"
        )
        specialty_rows = root.xpath(
            "//*[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' p2-education-specialty-row '"
            ")]"
        )

        self.assertEqual(len(school_rows), 4)
        self.assertEqual(len(specialty_rows), 4)

        for index in range(1, 5):
            self.assertIn(f"Навчальний заклад {index}", text)
            self.assertIn(f"Спеціальність {index}", text)
            self.assertIn(f"Кваліфікація {index}", text)
            self.assertIn(f"00000{index}", text)

        self.assertIn("Професійно-технічна", text)
        self.assertIn("Неповна вища", text)
        self.assertIn("Повна вища", text)

    def test_education_is_deleted_with_employee(self):
        education = self.env["hr.employee.education"].create(
            {
                "employee_id": self.employee.id,
                "institution_name": "Тестовий заклад",
            }
        )
        education_id = education.id
        self.employee.unlink()
        self.assertFalse(
            self.env["hr.employee.education"].browse(education_id).exists()
        )
