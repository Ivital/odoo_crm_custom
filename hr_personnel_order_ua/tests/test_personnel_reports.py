from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPersonnelReports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.department = cls.env["hr.department"].create(
            {
                "name": "REPORT TEST Підрозділ",
                "company_id": cls.env.company.id,
            }
        )
        cls.job = cls.env["hr.job"].create(
            {
                "name": "REPORT TEST Посада",
                "company_id": cls.env.company.id,
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Працівник Для Друку Тестовий",
                "company_id": cls.env.company.id,
                "identification_id": "REPORT-001",
                "department_id": cls.department.id,
                "job_id": cls.job.id,
                "birthday": "1980-05-10",
                "gender": "male",
                "private_city": "Кривий Ріг",
                "private_street": "вул. Тестова, 1",
                "l10n_ua_p2_card_number": "P2-TEST-001",
                "l10n_ua_p2_card_date": fields.Date.today(),
                "l10n_ua_p2_registered_address": "м. Кривий Ріг, тестова адреса",
            }
        )
        cls.leave_type = cls.env["hr.leave.type"].create(
            {
                "name": "REPORT TEST Відпустка",
                "requires_allocation": "no",
                "leave_validation_type": "no_validation",
            }
        )

    def _order(self, order_type, vals):
        line_vals = {
            "employee_id": self.employee.id,
            "effective_date": fields.Date.today(),
            **vals,
        }
        return self.env["hr.personnel.order"].create(
            {
                "number": f"REPORT-{order_type.upper()}",
                "order_type": order_type,
                "subject": f"REPORT TEST {order_type}",
                "company_id": self.env.company.id,
                "line_ids": [(0, 0, line_vals)],
            }
        )

    def _render(self, report_xmlid, records):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report_xmlid,
            records.ids,
        )
        self.assertTrue(html)
        return html.decode() if isinstance(html, bytes) else html

    def test_p1_report_action_and_html(self):
        order = self._order(
            "hire",
            {
                "department_id": self.department.id,
                "job_id": self.job.id,
                "wage": 25000.0,
                "work_type": "main",
                "weekly_hours": 40.0,
            },
        )

        action = order.action_print_p1()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_p1",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_p1",
            order,
        )
        self.assertIn("про прийняття на роботу", html)
        self.assertIn("Працівник Для Друку Тестовий", html)

    def test_p3_report_action_and_html(self):
        start = fields.Date.today() + timedelta(days=10)
        end = start + timedelta(days=4)

        order = self._order(
            "leave",
            {
                "leave_type_id": self.leave_type.id,
                "work_period_from": fields.Date.today() - timedelta(days=365),
                "work_period_to": fields.Date.today() - timedelta(days=1),
                "leave_date_from": start,
                "leave_date_to": end,
                "health_assistance": True,
            },
        )

        action = order.action_print_p3()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_p3",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_p3",
            order,
        )
        self.assertIn("про надання відпустки", html)
        self.assertIn("5", html)

    def test_p4_report_action_and_html(self):
        order = self._order(
            "termination",
            {
                "legal_reason": "За власним бажанням",
                "legal_article": "ст. 38 КЗпП України",
                "termination_basis": "Заява працівника",
                "unused_leave_days": 15.0,
                "severance_amount": 1000.0,
            },
        )

        action = order.action_print_p4()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_p4",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_p4",
            order,
        )
        self.assertIn("про припинення трудового договору", html)
        self.assertIn("ст. 38 КЗпП України", html)

    def test_p2_report_action_and_html(self):
        action = self.employee.action_print_personal_card_p2()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personal_card_p2",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personal_card_p2",
            self.employee,
        )
        self.assertIn("ОСОБОВА КАРТКА ПРАЦІВНИКА", html)
        self.assertIn("P2-TEST-001", html)
        self.assertIn("Кривий Ріг", html)

    def test_wrong_order_type_is_rejected(self):
        order = self._order(
            "termination",
            {
                "legal_reason": "Тест",
            },
        )

        with self.assertRaises(ValidationError):
            order.action_print_p1()

        with self.assertRaises(ValidationError):
            order.action_print_p3()

    def test_private_address_helper(self):
        address = self.employee._l10n_ua_report_private_address()
        self.assertIn("Кривий Ріг", address)
        self.assertIn("вул. Тестова, 1", address)
