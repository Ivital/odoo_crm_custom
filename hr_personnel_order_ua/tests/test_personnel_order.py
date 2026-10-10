from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPersonnelOrderFoundation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hr.department"].create(
            {
                "name": "КШЗ TEST Підрозділ",
                "company_id": cls.env.company.id,
            }
        )
        cls.job = cls.env["hr.job"].create(
            {
                "name": "КШЗ TEST Посада",
                "company_id": cls.env.company.id,
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Тестовий Працівник Кадровий",
                "company_id": cls.env.company.id,
                "identification_id": "KAD-FOUNDATION-001",
                "department_id": cls.department.id,
                "job_id": cls.job.id,
            }
        )

    def _make_transfer_order(self):
        return self.env["hr.personnel.order"].create(
            {
                "order_type": "transfer",
                "subject": "Тестове переведення",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "employee_id": self.employee.id,
                            "effective_date": "2030-01-15",
                            "department_id": self.department.id,
                            "job_id": self.job.id,
                        },
                    )
                ],
            }
        )

    def test_01_sequence_and_snapshot(self):
        order = self._make_transfer_order()
        self.assertTrue(order.number)
        self.assertNotEqual(order.number, "Новий")
        self.assertEqual(order.state, "draft")

        line = order.line_ids
        self.assertEqual(line.employee_name, self.employee.name)
        self.assertEqual(
            line.employee_identification_id,
            self.employee.identification_id,
        )
        self.assertEqual(
            line.previous_department_id,
            self.employee.department_id,
        )
        self.assertEqual(line.previous_job_id, self.employee.job_id)
        self.assertEqual(line.application_state, "pending")

    def test_02_state_machine_does_not_mutate_employee(self):
        order = self._make_transfer_order()
        before = (
            self.employee.department_id,
            self.employee.job_id,
            self.employee.resource_calendar_id,
        )

        order.action_submit()
        self.assertEqual(order.state, "submitted")
        order.action_approve()
        self.assertEqual(order.state, "approved")
        order.action_sign()
        self.assertEqual(order.state, "signed")
        order.action_post()
        self.assertEqual(order.state, "posted")

        self.employee.invalidate_recordset()
        after = (
            self.employee.department_id,
            self.employee.job_id,
            self.employee.resource_calendar_id,
        )
        self.assertEqual(before, after)
        self.assertFalse(order.event_ids)
        self.assertEqual(order.line_ids.application_state, "pending")

    def test_03_invalid_transition_is_blocked(self):
        order = self._make_transfer_order()
        with self.assertRaises(UserError):
            order.action_approve()

    def test_04_posted_order_is_locked(self):
        order = self._make_transfer_order()
        order.action_submit()
        order.action_approve()
        order.action_sign()
        order.action_post()

        with self.assertRaises(UserError):
            order.write({"subject": "Спроба переписати наказ"})

        with self.assertRaises(UserError):
            order.line_ids.write({"note": "Спроба переписати рядок"})

    def test_05_non_hire_requires_employee(self):
        with self.assertRaises(ValidationError):
            self.env["hr.personnel.order"].create(
                {
                    "order_type": "transfer",
                    "subject": "Некоректне переведення",
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "employee_name": "Лише текст без працівника",
                                "effective_date": "2030-01-15",
                            },
                        )
                    ],
                }
            )

    def test_06_hire_allows_future_employee_name(self):
        order = self.env["hr.personnel.order"].create(
            {
                "order_type": "hire",
                "subject": "Майбутнє прийняття",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "employee_name": "Майбутній Працівник Тестовий",
                            "employee_identification_id": "KAD-FUTURE-001",
                            "effective_date": "2030-02-01",
                            "department_id": self.department.id,
                            "job_id": self.job.id,
                        },
                    )
                ],
            }
        )
        self.assertFalse(order.line_ids.employee_id)
        self.assertEqual(
            order.line_ids.employee_name,
            "Майбутній Працівник Тестовий",
        )
