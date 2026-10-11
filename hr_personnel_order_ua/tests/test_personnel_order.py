from datetime import timedelta

from lxml import etree

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

    def test_00_hire_selector_allows_archived_employee(self):
        view = self.env.ref(
            "hr_personnel_order_ua.view_hr_personnel_order_form"
        )

        root = etree.fromstring(
            view.arch_db.encode("utf-8")
        )

        employee_fields = root.xpath(
            ".//field[@name='employee_id']"
        )

        self.assertEqual(
            len(employee_fields),
            2,
        )

        for field in employee_fields:
            self.assertEqual(
                field.get("context"),
                "{'active_test': order_type != 'hire'}",
            )

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
        self.assertEqual(line.contract_id.l10n_ua_hire_order_line_id, line)
        self.assertEqual(
            line.contract_id.l10n_ua_personnel_number,
            "KAD-HIRE-002",
        )
        self.assertEqual(
            order.event_ids.employee_identification_id,
            "KAD-HIRE-002",
        )
        self.assertEqual(line.employee_id.contract_id, line.contract_id)
        self.assertEqual(
            line.employee_id.l10n_ua_first_employment_date,
            fields.Date.today(),
        )

    def test_04_rehire_preserves_previous_employment_period(self):
        today = fields.Date.today()
        first_hire_date = today - timedelta(days=30)
        termination_date = today - timedelta(days=10)
        rehire_date = today - timedelta(days=5)

        employee = self.env["hr.employee"].create({
            "name": "Повторно Прийнятий Працівник",
            "company_id": self.env.company.id,
            "identification_id": "TEMP-PERSON-001",
            "department_id": self.department.id,
            "job_id": self.job.id,
        })

        first_hire = self.env["hr.personnel.order"].create({
            "order_type": "hire",
            "subject": "Перше історичне прийняття",
            "line_ids": [(0, 0, {
                "employee_id": employee.id,
                "employee_identification_id": "OLD-TAB-001",
                "effective_date": first_hire_date,
                "department_id": self.department.id,
                "job_id": self.job.id,
                "wage": 10000.0,
                "work_type": "main",
                "weekly_hours": 40.0,
            })],
        })
        self._post(first_hire)

        first_contract = first_hire.line_ids.contract_id

        self.assertEqual(
            first_contract.l10n_ua_personnel_number,
            "OLD-TAB-001",
        )
        self.assertEqual(
            first_contract.l10n_ua_hire_order_id,
            first_hire,
        )
        self.assertEqual(
            first_hire.event_ids.employee_identification_id,
            "OLD-TAB-001",
        )

        termination = self.env["hr.personnel.order"].create({
            "order_type": "termination",
            "subject": "Історичне звільнення",
            "line_ids": [(0, 0, {
                "employee_id": employee.id,
                "effective_date": termination_date,
                "legal_reason": "Тестове історичне звільнення",
            })],
        })
        self._post(termination)

        employee.invalidate_recordset()
        first_contract.invalidate_recordset()

        self.assertFalse(employee.active)
        self.assertEqual(first_contract.state, "close")
        self.assertEqual(
            first_contract.date_end,
            termination_date,
        )
        self.assertEqual(
            first_contract.l10n_ua_personnel_number,
            "OLD-TAB-001",
        )
        self.assertEqual(
            first_contract.l10n_ua_hire_order_id,
            first_hire,
        )
        self.assertEqual(
            termination.event_ids.employee_identification_id,
            "OLD-TAB-001",
        )
        self.assertEqual(
            termination.line_ids.employee_identification_id,
            "OLD-TAB-001",
        )

        rehire = self.env["hr.personnel.order"].create({
            "order_type": "hire",
            "subject": "Повторне прийняття",
            "line_ids": [(0, 0, {
                "employee_id": employee.id,
                "employee_identification_id": "NEW-TAB-777",
                "effective_date": rehire_date,
                "department_id": self.department_b.id,
                "job_id": self.job_b.id,
                "wage": 30000.0,
                "work_type": "main",
                "weekly_hours": 40.0,
            })],
        })
        self._post(rehire)

        employee.invalidate_recordset()
        first_contract.invalidate_recordset()

        second_contract = rehire.line_ids.contract_id

        self.assertTrue(employee.active)
        self.assertNotEqual(first_contract, second_contract)

        self.assertEqual(
            employee.identification_id,
            "NEW-TAB-777",
        )
        self.assertEqual(
            employee.service_hire_date,
            rehire_date,
        )
        self.assertEqual(
            employee.contract_id,
            second_contract,
        )

        self.assertEqual(
            first_contract.l10n_ua_personnel_number,
            "OLD-TAB-001",
        )
        self.assertEqual(
            second_contract.l10n_ua_personnel_number,
            "NEW-TAB-777",
        )

        self.assertEqual(
            first_contract.l10n_ua_hire_order_id,
            first_hire,
        )
        self.assertEqual(
            second_contract.l10n_ua_hire_order_id,
            rehire,
        )

        self.assertEqual(
            employee.l10n_ua_first_employment_date,
            first_hire_date,
        )
        self.assertEqual(
            employee.l10n_ua_current_personnel_number,
            "NEW-TAB-777",
        )

        self.assertEqual(
            rehire.event_ids.employee_identification_id,
            "NEW-TAB-777",
        )
        self.assertEqual(
            rehire.line_ids.employee_identification_id,
            "NEW-TAB-777",
        )

        contracts = employee.contract_ids.sorted(
            key=lambda contract: (
                contract.date_start,
                contract.id,
            )
        )

        self.assertEqual(len(contracts), 2)
        self.assertEqual(contracts[0], first_contract)
        self.assertEqual(contracts[1], second_contract)

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
