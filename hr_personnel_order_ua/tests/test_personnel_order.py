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
                "{'active_test': action_type != 'hire'}",
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

    def test_04_historical_backfill_preserves_newer_current_period(self):
        today = fields.Date.today()

        current_start = today - timedelta(days=5)

        historical_hire_date = (
            fields.Date.from_string(
                "2004-09-03"
            )
        )

        historical_transfer_date = (
            fields.Date.from_string(
                "2005-01-10"
            )
        )

        historical_termination_date = (
            current_start
            - timedelta(days=10)
        )

        employee = self.env["hr.employee"].create({
            "name": "Історичний Працівник Тест",
            "company_id": self.env.company.id,
            "identification_id": "NEW-TAB-2026",
            "service_hire_date": current_start,
            "department_id": self.department_b.id,
            "job_id": self.job_b.id,
        })

        current_contract = (
            self.env["hr.contract"].create({
                "name": "Поточний контракт 2026",
                "employee_id": employee.id,
                "company_id": self.env.company.id,
                "date_start": current_start,
                "wage": 30000.0,
                "state": "open",
                "l10n_ua_personnel_number":
                    "NEW-TAB-2026",
            })
        )

        employee.write({
            "contract_id": current_contract.id,
        })

        historical_hire = (
            self.env["hr.personnel.order"].create({
                "number": "01-к",
                "order_date":
                    historical_hire_date,
                "entry_mode": "historical",
                "order_type": "other",
                "subject":
                    "Історичне прийняття",
                "line_ids": [(0, 0, {
                    "employee_id":
                        employee.id,
                    "historical_action_type":
                        "hire",
                    "employee_identification_id":
                        "OLD-TAB-2004",
                    "effective_date":
                        historical_hire_date,
                    "department_id":
                        self.department.id,
                    "job_id":
                        self.job.id,
                    "wage": 0.0,
                })],
            })
        )

        self.assertEqual(
            historical_hire.number,
            "01-к",
        )
        self.assertEqual(
            historical_hire.order_year,
            2004,
        )

        historical_hire.action_register_historical()

        employee.invalidate_recordset()
        current_contract.invalidate_recordset()

        historical_line = (
            historical_hire.line_ids
        )

        historical_contract = (
            historical_line.contract_id
        )

        self.assertEqual(
            historical_line.action_type,
            "hire",
        )

        self.assertEqual(
            historical_hire.event_ids.event_type,
            "hire",
        )

        self.assertNotEqual(
            historical_contract,
            current_contract,
        )

        self.assertEqual(
            historical_contract.date_start,
            historical_hire_date,
        )

        self.assertFalse(
            historical_contract.date_end,
        )

        self.assertEqual(
            historical_contract.state,
            "draft",
        )

        self.assertFalse(
            historical_contract.l10n_ua_end_date_inferred,
        )

        self.assertTrue(
            historical_contract.l10n_ua_end_date_unresolved,
        )

        self.assertEqual(
            historical_contract.l10n_ua_personnel_number,
            "OLD-TAB-2004",
        )

        self.assertEqual(
            historical_contract.job_id,
            self.job,
        )

        self.assertEqual(
            historical_contract.department_id,
            self.department,
        )

        # Current 2026 employment must stay live.
        self.assertTrue(
            employee.active
        )

        self.assertEqual(
            employee.identification_id,
            "NEW-TAB-2026",
        )

        self.assertEqual(
            employee.service_hire_date,
            current_start,
        )

        self.assertEqual(
            employee.contract_id,
            current_contract,
        )

        self.assertEqual(
            employee.job_id,
            self.job_b,
        )

        self.assertEqual(
            employee.department_id,
            self.department_b,
        )

        # First-ever employment is reconstructed.
        self.assertEqual(
            employee.l10n_ua_first_employment_date,
            historical_hire_date,
        )

        historical_transfer = (
            self.env["hr.personnel.order"].create({
                "number":
                    "01-к",
                "order_date":
                    historical_transfer_date,
                "entry_mode": "historical",
                "order_type": "other",
                "subject":
                    "Історичне переведення",
                "line_ids": [(0, 0, {
                    "employee_id":
                        employee.id,
                    "historical_action_type":
                        "transfer",
                    "effective_date":
                        historical_transfer_date,
                    "job_id":
                        self.job_b.id,
                })],
            })
        )

        self.assertEqual(
            historical_transfer.number,
            "01-к",
        )
        self.assertEqual(
            historical_transfer.order_year,
            2005,
        )

        historical_transfer.action_register_historical()

        employee.invalidate_recordset()
        historical_contract.invalidate_recordset()

        self.assertEqual(
            historical_transfer.line_ids.action_type,
            "transfer",
        )

        self.assertEqual(
            historical_transfer.event_ids.event_type,
            "transfer",
        )

        self.assertEqual(
            historical_contract.job_id,
            self.job_b,
        )

        self.assertEqual(
            employee.contract_id,
            current_contract,
        )

        self.assertEqual(
            employee.identification_id,
            "NEW-TAB-2026",
        )

        self.assertEqual(
            employee.service_hire_date,
            current_start,
        )

        historical_termination = (
            self.env["hr.personnel.order"].create({
                "number":
                    "01-к",
                "order_date":
                    historical_termination_date,
                "entry_mode": "historical",
                "order_type": "other",
                "subject":
                    "Історичне звільнення",
                "line_ids": [(0, 0, {
                    "employee_id":
                        employee.id,
                    "historical_action_type":
                        "termination",
                    "effective_date":
                        historical_termination_date,
                })],
            })
        )

        historical_termination.action_register_historical()

        employee.invalidate_recordset()
        historical_contract.invalidate_recordset()
        current_contract.invalidate_recordset()

        self.assertEqual(
            historical_termination.line_ids.action_type,
            "termination",
        )

        self.assertEqual(
            historical_termination.event_ids.event_type,
            "termination",
        )

        self.assertEqual(
            historical_contract.date_end,
            historical_termination_date,
        )

        self.assertEqual(
            historical_contract.state,
            "close",
        )

        # Current 2026 employment still untouched.
        self.assertTrue(
            employee.active
        )

        self.assertEqual(
            employee.contract_id,
            current_contract,
        )

        self.assertEqual(
            current_contract.state,
            "open",
        )

        self.assertEqual(
            current_contract.date_start,
            current_start,
        )

        self.assertEqual(
            current_contract.l10n_ua_personnel_number,
            "NEW-TAB-2026",
        )

        self.assertEqual(
            employee.identification_id,
            "NEW-TAB-2026",
        )

        events = (
            self.env["hr.personnel.event"]
            .search(
                [
                    (
                        "employee_id",
                        "=",
                        employee.id,
                    ),
                    (
                        "order_id",
                        "in",
                        [
                            historical_hire.id,
                            historical_transfer.id,
                            historical_termination.id,
                        ],
                    ),
                ],
                order=(
                    "effective_date asc, "
                    "id asc"
                ),
            )
        )

        self.assertEqual(
            events.mapped("event_type"),
            [
                "hire",
                "transfer",
                "termination",
            ],
        )

        self.assertEqual(
            events[0].employee_identification_id,
            "OLD-TAB-2004",
        )

        self.assertEqual(
            events[1].employee_identification_id,
            "OLD-TAB-2004",
        )

        self.assertEqual(
            events[2].employee_identification_id,
            "OLD-TAB-2004",
        )

    def test_04_historical_backfill_preserves_active_card_without_contract(self):
        historical_date = fields.Date.from_string(
            "2004-09-03"
        )
        current_start = fields.Date.from_string(
            "2026-04-09"
        )

        employee = self.env["hr.employee"].create({
            "name": "Іващенко Віталій Тестовий",
            "company_id": self.env.company.id,
            "identification_id": "1261",
            "service_hire_date": current_start,
            "department_id": self.department_b.id,
            "job_id": self.job_b.id,
            "active": True,
        })

        self.assertFalse(
            employee.contract_id
        )

        order = self.env["hr.personnel.order"].create({
            "number": "03-к",
            "order_date": historical_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject": "Історичне прийняття",
            "line_ids": [(0, 0, {
                "employee_id": employee.id,
                "historical_action_type": "hire",
                "employee_identification_id":
                    "OLD-2004",
                "effective_date":
                    historical_date,
                "department_id":
                    self.department.id,
                "job_id":
                    self.job.id,
                "wage": 0.0,
            })],
        })

        order.action_register_historical()

        employee.invalidate_recordset()

        contract = order.line_ids.contract_id

        self.assertTrue(contract)
        self.assertTrue(
            contract.l10n_ua_historical_reconstruction
        )
        self.assertFalse(
            contract.l10n_ua_end_date_inferred
        )
        self.assertTrue(
            contract.l10n_ua_end_date_unresolved
        )
        self.assertEqual(
            contract.date_start,
            historical_date,
        )
        self.assertFalse(
            contract.date_end,
        )
        self.assertEqual(
            contract.state,
            "draft",
        )
        self.assertEqual(
            contract.l10n_ua_personnel_number,
            "OLD-2004",
        )

        # Modern imported employee card is protected.
        self.assertTrue(employee.active)
        self.assertFalse(employee.contract_id)
        self.assertEqual(
            employee.identification_id,
            "1261",
        )
        self.assertEqual(
            employee.service_hire_date,
            current_start,
        )
        self.assertEqual(
            employee.department_id,
            self.department_b,
        )
        self.assertEqual(
            employee.job_id,
            self.job_b,
        )

        termination_date = (
            current_start - timedelta(days=4)
        )

        termination = (
            self.env["hr.personnel.order"].create({
                "number": "04-к",
                "order_date": termination_date,
                "entry_mode": "historical",
                "order_type": "termination",
                "subject":
                    "Історичне звільнення",
                "line_ids": [(0, 0, {
                    "employee_id":
                        employee.id,
                    "historical_action_type":
                        "termination",
                    "effective_date":
                        termination_date,
                })],
            })
        )

        termination.action_register_historical()

        employee.invalidate_recordset()
        contract.invalidate_recordset()

        # Real dismissal supplies the first factual end date.
        self.assertEqual(
            contract.date_end,
            termination_date,
        )
        self.assertFalse(
            contract.l10n_ua_end_date_inferred
        )
        self.assertFalse(
            contract.l10n_ua_end_date_unresolved
        )

        # Current card still remains the 2026 state.
        self.assertTrue(employee.active)
        self.assertFalse(employee.contract_id)
        self.assertEqual(
            employee.identification_id,
            "1261",
        )
        self.assertEqual(
            employee.service_hire_date,
            current_start,
        )

        # When reconstruction reaches the documented
        # current rehire, the current contract is materialized.
        rehire = self.env["hr.personnel.order"].create({
            "number": "05-к",
            "order_date": current_start,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject": "Повторне прийняття",
            "line_ids": [(0, 0, {
                "employee_id": employee.id,
                "historical_action_type": "hire",
                "employee_identification_id":
                    "1261",
                "effective_date":
                    current_start,
                "department_id":
                    self.department_b.id,
                "job_id":
                    self.job_b.id,
                "wage": 0.0,
            })],
        })

        rehire.action_register_historical()

        employee.invalidate_recordset()

        current_contract = (
            rehire.line_ids.contract_id
        )

        self.assertEqual(
            employee.contract_id,
            current_contract,
        )
        self.assertEqual(
            current_contract.state,
            "open",
        )
        self.assertEqual(
            current_contract.date_start,
            current_start,
        )
        self.assertEqual(
            current_contract.l10n_ua_personnel_number,
            "1261",
        )

        self.assertEqual(
            employee.identification_id,
            "1261",
        )
        self.assertEqual(
            employee.service_hire_date,
            current_start,
        )
        self.assertEqual(
            employee.department_id,
            self.department_b,
        )
        self.assertEqual(
            employee.job_id,
            self.job_b,
        )

    def test_04_historical_unknown_current_start_stays_provisional(self):
        historical_date = fields.Date.from_string(
            "2004-08-06"
        )

        employee = self.env["hr.employee"].create({
            "name": "Поточний Працівник Без Дати",
            "company_id": self.env.company.id,
            "identification_id": "CURRENT-500",
            "department_id": self.department_b.id,
            "job_id": self.job_b.id,
            "active": True,
        })

        order = self.env["hr.personnel.order"].create({
            "number": "06-к",
            "order_date": historical_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Історичне прийняття "
                "при невідомій сучасній даті",
            "line_ids": [(0, 0, {
                "employee_id": employee.id,
                "historical_action_type": "hire",
                "employee_identification_id":
                    "OLD-500",
                "effective_date":
                    historical_date,
                "job_id": self.job.id,
                "department_id":
                    self.department.id,
                "wage": 0.0,
            })],
        })

        order.action_register_historical()

        employee.invalidate_recordset()

        contract = order.line_ids.contract_id

        self.assertEqual(
            contract.state,
            "draft",
        )
        self.assertFalse(
            contract.date_end,
        )
        self.assertTrue(
            contract.l10n_ua_historical_reconstruction
        )
        self.assertFalse(
            contract.l10n_ua_end_date_inferred
        )
        self.assertTrue(
            contract.l10n_ua_end_date_unresolved
        )

        # The unresolved old period must not become today's
        # employee state or today's current contract.
        self.assertFalse(
            employee.contract_id
        )
        self.assertEqual(
            employee.identification_id,
            "CURRENT-500",
        )
        self.assertEqual(
            employee.department_id,
            self.department_b,
        )
        self.assertEqual(
            employee.job_id,
            self.job_b,
        )

    def test_04_historical_annulled_source_is_noop(self):
        before_contracts = (
            self.env["hr.contract"]
            .search_count([])
        )

        before_events = (
            self.env["hr.personnel.event"]
            .search_count([])
        )

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "34-к",
            "order_date":
                fields.Date.from_string(
                    "2004-12-14"
                ),
            "entry_mode": "historical",
            "order_type": "other",
            "subject":
                "Анульований історичний наказ",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал реєстрації "
                "тривалих наказів 2004",
            "source_row": 34,
            "source_key":
                "personnel-long-orders:"
                "2004:34-к",
            "source_status": "annulled",
            "source_text":
                "Про призначення "
                "Гуца В.І. відповідальним "
                "за мобілізаційну роботу",
            "source_note":
                "Анульований",
        })

        order.action_register_historical()

        self.assertEqual(
            order.state,
            "cancelled",
        )

        self.assertEqual(
            order.source_status,
            "annulled",
        )

        self.assertFalse(
            order.line_ids,
        )

        self.assertFalse(
            order.event_ids,
        )

        self.assertEqual(
            self.env["hr.contract"]
            .search_count([]),
            before_contracts,
        )

        self.assertEqual(
            self.env["hr.personnel.event"]
            .search_count([]),
            before_events,
        )

    def test_04_source_backfill_blocks_ambiguous_identity(self):
        historical_date = (
            fields.Date.from_string(
                "2004-10-08"
            )
        )

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "19-к",
            "order_date": historical_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Неоднозначна особа",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал реєстрації "
                "тривалих наказів 2004",
            "source_row": 19,
            "source_key":
                "personnel-long-orders:"
                "2004:19-к",
            "source_status": "normal",
            "source_text":
                "Про прийняття "
                "Іващенка В.П. охоронцем",
            "line_ids": [(0, 0, {
                "employee_name":
                    "Іващенко В.П.",
                "historical_action_type":
                    "hire",
                "effective_date":
                    historical_date,
                "source_line_key":
                    "19-к:01",
                "source_person_name":
                    "Іващенко В.П.",
                "source_text":
                    "Про прийняття на роботу "
                    "Іващенка В.П. охоронцем "
                    "з 08.10.2004",
                "identity_resolution":
                    "ambiguous",
            })],
        })

        with self.assertRaises(
            ValidationError
        ):
            order.action_register_historical()

        self.assertEqual(
            order.state,
            "draft",
        )

        self.assertFalse(
            order.event_ids,
        )

    def test_04_job_name_matching_is_case_and_space_insensitive(self):
        Job = self.env["hr.job"]

        found = (
            Job.l10n_ua_find_canonical_job(
                "   кшз   test   посада a ",
                company=self.env.company,
            )
        )

        self.assertEqual(
            found,
            self.job,
        )

        created = (
            Job.l10n_ua_get_or_create_canonical_job(
                "   історична   тестова посада ",
                company=self.env.company,
            )
        )

        self.assertEqual(
            created.name,
            "Історична тестова посада",
        )

        again = (
            Job.l10n_ua_get_or_create_canonical_job(
                "історична тестова ПОСАДА",
                company=self.env.company,
            )
        )

        self.assertEqual(
            again,
            created,
        )

    def test_04_historical_part_time_to_main_without_fake_end_date(self):
        part_time_date = fields.Date.from_string(
            "2004-10-01"
        )

        main_date = fields.Date.from_string(
            "2004-10-28"
        )

        first_order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "16-к",
            "order_date": part_time_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Прийняття за сумісництвом",
            "line_ids": [(0, 0, {
                "employee_name":
                    "Заславська Тестова Григорівна",
                "historical_action_type":
                    "hire",
                "effective_date":
                    part_time_date,
                "job_id":
                    self.job.id,
                "work_type":
                    "part_time",
                "wage": 0.0,
            })],
        })

        first_order.action_register_historical()

        self.env.flush_all()

        employee = first_order.line_ids.employee_id
        contract = first_order.line_ids.contract_id

        self.assertFalse(employee.active)
        self.assertFalse(employee.contract_id)

        self.assertEqual(
            contract.l10n_ua_work_type,
            "part_time",
        )

        self.assertFalse(
            contract.date_end,
        )

        self.assertEqual(
            contract.state,
            "draft",
        )

        self.assertTrue(
            contract.resource_calendar_id,
        )

        self.assertTrue(
            contract.l10n_ua_historical_calendar_unknown,
        )

        self.assertTrue(
            contract.l10n_ua_historical_wage_unknown,
        )

        second_order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "25-к",
            "order_date":
                fields.Date.from_string(
                    "2004-10-25"
                ),
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Перехід на основне місце роботи",
            "line_ids": [(0, 0, {
                "employee_id":
                    employee.id,
                "historical_action_type":
                    "employment_condition_change",
                "effective_date":
                    main_date,
                "work_type":
                    "main",
            })],
        })

        second_order.action_register_historical()

        employee.invalidate_recordset()
        contract.invalidate_recordset()

        self.assertEqual(
            contract.l10n_ua_work_type,
            "main",
        )

        # Transition does not invent dismissal / end date.
        self.assertFalse(
            contract.date_end,
        )

        self.assertEqual(
            contract.state,
            "draft",
        )

        self.assertFalse(
            employee.active,
        )

        self.assertFalse(
            employee.contract_id,
        )

        events = self.env[
            "hr.personnel.event"
        ].search(
            [
                (
                    "employee_id",
                    "=",
                    employee.id,
                ),
                (
                    "order_id",
                    "in",
                    [
                        first_order.id,
                        second_order.id,
                    ],
                ),
            ],
            order="effective_date asc, id asc",
        )

        self.assertEqual(
            events.mapped("event_type"),
            [
                "hire",
                "employment_condition_change",
            ],
        )

        self.assertEqual(
            events.mapped("work_type"),
            [
                "part_time",
                "main",
            ],
        )

    def test_04_historical_hire_allows_incomplete_old_requisites(self):
        historical_date = (
            fields.Date.from_string(
                "2004-08-06"
            )
        )

        order = self.env["hr.personnel.order"].create({
            "number": "02-к",
            "order_date": historical_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Історичне прийняття "
                "з неповними реквізитами",
            "line_ids": [(0, 0, {
                "employee_name":
                    "Архівний Працівник",
                "effective_date":
                    historical_date,
                "wage": 0.0,
            })],
        })

        order.action_register_historical()

        # Production hr_contract.resource_calendar_id and
        # wage are NOT NULL. Force an actual SQL flush here so
        # this regression cannot hide in the ORM cache.
        self.env.flush_all()

        line = order.line_ids
        employee = line.employee_id
        contract = line.contract_id

        self.assertTrue(employee)
        self.assertTrue(contract)

        self.assertEqual(
            line.action_type,
            "hire",
        )

        self.assertEqual(
            contract.date_start,
            historical_date,
        )

        self.assertEqual(
            contract.wage,
            0.0,
        )

        # 0.0 is only the native Odoo NOT NULL placeholder;
        # it is explicitly NOT a historical wage fact.
        self.assertTrue(
            contract.l10n_ua_historical_wage_unknown,
        )

        self.assertTrue(
            contract.resource_calendar_id,
        )

        self.assertEqual(
            contract.resource_calendar_id,
            self.env.company.resource_calendar_id,
        )

        # The company calendar is likewise only a technical
        # placeholder because the source did not state the
        # historical work schedule.
        self.assertTrue(
            contract.l10n_ua_historical_calendar_unknown,
        )

        self.assertFalse(
            contract.l10n_ua_personnel_number,
        )

        self.assertFalse(
            contract.date_end,
        )

        self.assertEqual(
            contract.state,
            "draft",
        )

        self.assertTrue(
            contract.l10n_ua_end_date_unresolved,
        )

        self.assertFalse(
            employee.active,
        )

        self.assertFalse(
            employee.contract_id,
        )

        self.assertFalse(
            employee.service_hire_date,
        )

        event = order.event_ids

        self.assertTrue(event)

        self.assertTrue(
            event.l10n_ua_historical_calendar_unknown,
        )

        self.assertTrue(
            event.l10n_ua_historical_wage_unknown,
        )

        # Technical placeholders must not leak into the
        # immutable event ledger as factual history.
        self.assertFalse(
            event.new_resource_calendar_id,
        )

        self.assertEqual(
            event.new_wage,
            0.0,
        )

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
