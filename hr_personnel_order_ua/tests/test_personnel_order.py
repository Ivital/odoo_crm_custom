from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPersonnelOrderApplication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hr.department"].create({
            "name": "КШЗ TEST Підрозділ A",
            "company_id": cls.env.company.id,
        })
        cls.department_b = cls.env["hr.department"].create({
            "name": "КШЗ TEST Підрозділ B",
            "company_id": cls.env.company.id,
        })
        cls.job = cls.env["hr.job"].create({
            "name": "КШЗ TEST Посада A",
            "company_id": cls.env.company.id,
        })
        cls.job_b = cls.env["hr.job"].create({
            "name": "КШЗ TEST Посада B",
            "company_id": cls.env.company.id,
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "Тестовий Працівник Кадровий",
            "company_id": cls.env.company.id,
            "identification_id": "KAD-FOUNDATION-001",
            "department_id": cls.department.id,
            "job_id": cls.job.id,
        })

    def _post(self, order):
        order.action_submit()
        order.action_approve()
        order.action_sign()
        order.action_post()
        return order

    def test_01_future_transfer_is_planned_only(self):
        future = fields.Date.today() + timedelta(days=30)
        order = self.env["hr.personnel.order"].create({
            "order_type": "transfer",
            "subject": "Майбутнє переведення",
            "line_ids": [(0, 0, {
                "employee_id": self.employee.id,
                "effective_date": future,
                "department_id": self.department_b.id,
                "job_id": self.job_b.id,
            })],
        })
        self._post(order)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.department_id, self.department)
        self.assertEqual(self.employee.job_id, self.job)
        self.assertEqual(order.line_ids.application_state, "pending")
        self.assertEqual(order.event_ids.status, "planned")

    def test_02_due_transfer_updates_employee_and_event(self):
        order = self.env["hr.personnel.order"].create({
            "order_type": "transfer",
            "subject": "Негайне переведення",
            "line_ids": [(0, 0, {
                "employee_id": self.employee.id,
                "effective_date": fields.Date.today(),
                "department_id": self.department_b.id,
                "job_id": self.job_b.id,
            })],
        })
        self._post(order)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.department_id, self.department_b)
        self.assertEqual(self.employee.job_id, self.job_b)
        self.assertEqual(order.line_ids.application_state, "applied")
        self.assertEqual(order.event_ids.status, "applied")
        self.assertEqual(order.event_ids.previous_department_id, self.department)
        self.assertEqual(order.event_ids.new_department_id, self.department_b)

    def test_03_hire_creates_employee_contract_and_links_source(self):
        order = self.env["hr.personnel.order"].create({
            "order_type": "hire",
            "subject": "Прийняття тестового працівника",
            "line_ids": [(0, 0, {
                "employee_name": "Новий Працівник Кадровий",
                "employee_identification_id": "KAD-HIRE-002",
                "effective_date": fields.Date.today(),
                "department_id": self.department.id,
                "job_id": self.job.id,
                "wage": 25000.0,
                "work_type": "main",
                "weekly_hours": 40.0,
            })],
        })
        self._post(order)
        line = order.line_ids
        self.assertTrue(line.employee_id)
        self.assertTrue(line.contract_id)
        self.assertEqual(line.application_state, "applied")
        self.assertEqual(line.contract_id.wage, 25000.0)
        self.assertEqual(line.contract_id.l10n_ua_personnel_order_line_id, line)
        self.assertEqual(line.employee_id.contract_id, line.contract_id)

    def test_04_leave_creates_approved_leave_with_p3_data(self):
        leave_type = self.env["hr.leave.type"].create({
            "name": "КШЗ TEST Відпустка",
            "requires_allocation": "no",
            "leave_validation_type": "no_validation",
        })
        start = fields.Date.today() + timedelta(days=10)
        end = start + timedelta(days=4)
        order = self.env["hr.personnel.order"].create({
            "order_type": "leave",
            "subject": "Тестова відпустка",
            "line_ids": [(0, 0, {
                "employee_id": self.employee.id,
                "effective_date": fields.Date.today(),
                "leave_type_id": leave_type.id,
                "work_period_from": fields.Date.today() - timedelta(days=365),
                "work_period_to": fields.Date.today() - timedelta(days=1),
                "leave_date_from": start,
                "leave_date_to": end,
                "health_assistance": True,
            })],
        })
        self._post(order)
        leave = order.line_ids.leave_id
        self.assertTrue(leave)
        self.assertEqual(leave.state, "validate")
        self.assertEqual(leave.l10n_ua_personnel_order_line_id, order.line_ids)
        self.assertEqual(order.line_ids.leave_calendar_days, 5)
        self.assertEqual(leave.l10n_ua_calendar_days, 5)
        self.assertTrue(leave.l10n_ua_health_assistance)

    def test_05_posted_order_is_locked(self):
        future = fields.Date.today() + timedelta(days=30)
        order = self.env["hr.personnel.order"].create({
            "order_type": "transfer",
            "subject": "Заблокований наказ",
            "line_ids": [(0, 0, {
                "employee_id": self.employee.id,
                "effective_date": future,
                "department_id": self.department_b.id,
                "job_id": self.job_b.id,
            })],
        })
        self._post(order)
        with self.assertRaises(UserError):
            order.write({"subject": "Спроба переписати наказ"})
        with self.assertRaises(UserError):
            order.line_ids.write({"note": "Спроба переписати рядок"})

    def test_06_non_hire_requires_employee(self):
        with self.assertRaises(ValidationError):
            self.env["hr.personnel.order"].create({
                "order_type": "transfer",
                "subject": "Некоректне переведення",
                "line_ids": [(0, 0, {
                    "employee_name": "Лише текст без працівника",
                    "effective_date": fields.Date.today(),
                })],
            })
