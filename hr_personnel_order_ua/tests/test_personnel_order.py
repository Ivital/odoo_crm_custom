from datetime import timedelta

from lxml import etree
from psycopg2 import IntegrityError

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

    def test_04_historical_hire_creates_factual_period_only(self):
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

        before = {
            "active": employee.active,
            "tab": employee.identification_id,
            "hire": employee.service_hire_date,
            "department": employee.department_id,
            "job": employee.job_id,
            "contract": employee.contract_id,
        }

        contract_count = self.env[
            "hr.contract"
        ].search_count([])

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "05-к",
            "order_date": historical_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Історичне прийняття",
            "line_ids": [(0, 0, {
                "employee_id":
                    employee.id,
                "historical_action_type":
                    "hire",
                "effective_date":
                    historical_date,
                "job_id":
                    self.job.id,
                "work_type":
                    "main",
            })],
        })

        order.action_register_historical()
        self.env.flush_all()

        line = order.line_ids
        period = line.employment_period_id
        event = order.event_ids

        self.assertTrue(period)

        self.assertEqual(
            period.employee_id,
            employee,
        )

        self.assertEqual(
            period.date_start,
            historical_date,
        )

        self.assertFalse(
            period.date_end,
        )

        self.assertEqual(
            period.start_order_line_id,
            line,
        )

        self.assertFalse(
            period.end_order_line_id,
        )

        self.assertFalse(
            line.contract_id,
        )

        self.assertFalse(
            line.leave_id,
        )

        self.assertEqual(
            event.employment_period_id,
            period,
        )

        self.assertFalse(
            event.contract_id,
        )

        self.assertFalse(
            event.leave_id,
        )

        self.assertEqual(
            self.env["hr.contract"]
            .search_count([]),
            contract_count,
        )

        employee.invalidate_recordset()

        self.assertEqual(
            employee.active,
            before["active"],
        )

        self.assertEqual(
            employee.identification_id,
            before["tab"],
        )

        self.assertEqual(
            employee.service_hire_date,
            before["hire"],
        )

        self.assertEqual(
            employee.department_id,
            before["department"],
        )

        self.assertEqual(
            employee.job_id,
            before["job"],
        )

        self.assertEqual(
            employee.contract_id,
            before["contract"],
        )

        self.assertEqual(
            employee.l10n_ua_first_employment_date,
            historical_date,
        )

    def test_04_historical_new_employee_is_archived(self):
        historical_date = fields.Date.from_string(
            "2004-08-06"
        )

        contract_count = self.env[
            "hr.contract"
        ].search_count([])

        calendar_count = (
            self.env["resource.calendar"]
            .with_context(active_test=False)
            .search_count([])
        )

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "01-к",
            "order_date": historical_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Нова історична особа",
            "line_ids": [(0, 0, {
                "employee_name":
                    "Архівний Працівник",
                "identity_resolution":
                    "new",
                "historical_action_type":
                    "hire",
                "effective_date":
                    historical_date,
            })],
        })

        order.action_register_historical()
        self.env.flush_all()

        employee = order.line_ids.employee_id
        period = (
            order.line_ids.employment_period_id
        )

        self.assertTrue(employee)

        self.assertFalse(
            employee.active,
        )

        # Historical-only discovery must not inherit or invent
        # current operational employment attributes.
        self.assertFalse(
            employee.identification_id,
        )

        self.assertFalse(
            employee.resource_calendar_id,
        )

        if "calendar_ids" in employee._fields:
            self.assertFalse(
                employee.calendar_ids,
            )

        self.assertFalse(
            employee.department_id,
        )

        self.assertFalse(
            employee.job_id,
        )

        self.assertFalse(
            employee.contract_id,
        )

        self.assertFalse(
            employee.service_hire_date,
        )

        self.assertEqual(
            self.env["resource.calendar"]
            .with_context(active_test=False)
            .search_count([]),
            calendar_count,
        )

        self.assertEqual(
            period.date_start,
            historical_date,
        )

        self.assertFalse(
            period.date_end,
        )

        self.assertEqual(
            self.env["hr.contract"]
            .search_count([]),
            contract_count,
        )

    def test_04_historical_part_time_to_main_same_period(self):
        part_time_date = fields.Date.from_string(
            "2004-10-01"
        )

        main_date = fields.Date.from_string(
            "2004-10-28"
        )

        contract_count = self.env[
            "hr.contract"
        ].search_count([])

        first = self.env[
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
                "identity_resolution":
                    "new",
                "historical_action_type":
                    "hire",
                "effective_date":
                    part_time_date,
                "job_id":
                    self.job.id,
                "work_type":
                    "part_time",
            })],
        })

        first.action_register_historical()
        self.env.flush_all()

        employee = first.line_ids.employee_id
        period = (
            first.line_ids.employment_period_id
        )

        second = self.env[
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

        second.action_register_historical()
        self.env.flush_all()

        self.assertEqual(
            second.line_ids.employment_period_id,
            period,
        )

        self.assertFalse(
            period.date_end,
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
                    "employment_period_id",
                    "=",
                    period.id,
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

        self.assertEqual(
            self.env["hr.contract"]
            .search_count([]),
            contract_count,
        )

    def test_04_historical_termination_closes_factual_period_only(self):
        hire_date = fields.Date.from_string(
            "2004-08-06"
        )

        termination_date = fields.Date.from_string(
            "2004-11-30"
        )

        employee = self.employee

        active_before = employee.active

        hire = self.env[
            "hr.personnel.order"
        ].create({
            "number": "01-к",
            "order_date": hire_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Історичне прийняття",
            "line_ids": [(0, 0, {
                "employee_id":
                    employee.id,
                "historical_action_type":
                    "hire",
                "effective_date":
                    hire_date,
            })],
        })

        hire.action_register_historical()

        period = (
            hire.line_ids.employment_period_id
        )

        termination = self.env[
            "hr.personnel.order"
        ].create({
            "number": "33-к",
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

        termination.action_register_historical()
        self.env.flush_all()

        period.invalidate_recordset()
        employee.invalidate_recordset()

        self.assertEqual(
            period.date_end,
            termination_date,
        )

        self.assertEqual(
            period.end_order_line_id,
            termination.line_ids,
        )

        self.assertEqual(
            termination.line_ids.employment_period_id,
            period,
        )

        self.assertEqual(
            employee.active,
            active_before,
        )

        self.assertFalse(
            termination.line_ids.contract_id,
        )

    def test_04_historical_leave_is_event_only_and_end_may_be_unknown(self):
        start = fields.Date.from_string(
            "2004-12-17"
        )

        hire_date = fields.Date.from_string(
            "2004-08-06"
        )

        leave_type = self.env[
            "hr.leave.type"
        ].create({
            "name":
                "КШЗ TEST Historical Unpaid",
            "requires_allocation":
                "no",
            "leave_validation_type":
                "no_validation",
        })

        hire = self.env[
            "hr.personnel.order"
        ].create({
            "number": "01-к",
            "order_date": hire_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject":
                "Історичне прийняття",
            "line_ids": [(0, 0, {
                "employee_id":
                    self.employee.id,
                "historical_action_type":
                    "hire",
                "effective_date":
                    hire_date,
            })],
        })

        hire.action_register_historical()

        period = (
            hire.line_ids.employment_period_id
        )

        leave_count = self.env[
            "hr.leave"
        ].search_count([])

        leave_order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "36-к",
            "order_date": start,
            "entry_mode": "historical",
            "order_type": "leave",
            "subject":
                "Без збереження зарплати",
            "line_ids": [(0, 0, {
                "employee_id":
                    self.employee.id,
                "historical_action_type":
                    "leave",
                "effective_date":
                    start,
                "leave_type_id":
                    leave_type.id,
                "leave_date_from":
                    start,
                # Unknown end remains NULL.
                "leave_date_to":
                    False,
            })],
        })

        leave_order.action_register_historical()
        self.env.flush_all()

        event = leave_order.event_ids

        self.assertEqual(
            leave_order.line_ids.employment_period_id,
            period,
        )

        self.assertFalse(
            leave_order.line_ids.leave_id,
        )

        self.assertFalse(
            event.leave_id,
        )

        self.assertEqual(
            event.leave_date_from,
            start,
        )

        self.assertFalse(
            event.leave_date_to,
        )

        self.assertEqual(
            self.env["hr.leave"]
            .search_count([]),
            leave_count,
        )

    def test_04_historical_first_seen_termination_creates_unknown_start_period(self):
        termination_date = fields.Date.from_string(
            "2004-10-21"
        )

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "23-к",
            "order_date":
                termination_date,
            "entry_mode":
                "historical",
            "order_type":
                "termination",
            "subject":
                "Перша відома подія — звільнення",
            "line_ids": [(0, 0, {
                "employee_name":
                    "Архівний Звільнений Працівник",
                "identity_resolution":
                    "new",
                "historical_action_type":
                    "termination",
                "effective_date":
                    termination_date,
            })],
        })

        order.action_register_historical()
        self.env.flush_all()

        employee = order.line_ids.employee_id
        period = (
            order.line_ids.employment_period_id
        )

        self.assertFalse(
            employee.active,
        )

        self.assertFalse(
            period.date_start,
        )

        self.assertEqual(
            period.date_end,
            termination_date,
        )

        self.assertEqual(
            period.boundary_state,
            "start_unknown",
        )

    def test_04_historical_annulled_source_is_noop(self):
        before_periods = self.env[
            "hr.personnel.employment.period"
        ].search_count([])

        before_events = self.env[
            "hr.personnel.event"
        ].search_count([])

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "34-к",
            "order_date":
                fields.Date.from_string(
                    "2004-12-14"
                ),
            "entry_mode":
                "historical",
            "order_type":
                "other",
            "subject":
                "Анульований історичний наказ",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал реєстрації "
                "тривалих наказів 2004",
            "source_year": 2004,
            "source_row":
                34,
            "source_key":
                "personnel-long-orders:"
                "2004:row:034",
            "source_status":
                "annulled",
            "source_text":
                "Про призначення Гуца В.І. "
                "відповідальним за "
                "мобілізаційну роботу",
            "source_note":
                "Анульований",
        })

        order.action_register_historical()

        self.assertEqual(
            order.state,
            "cancelled",
        )

        self.assertFalse(
            order.event_ids,
        )

        self.assertEqual(
            self.env[
                "hr.personnel.employment.period"
            ].search_count([]),
            before_periods,
        )

        self.assertEqual(
            self.env[
                "hr.personnel.event"
            ].search_count([]),
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
            "order_date":
                historical_date,
            "entry_mode":
                "historical",
            "order_type":
                "hire",
            "subject":
                "Неоднозначна особа",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал реєстрації "
                "тривалих наказів 2004",
            "source_year": 2004,
            "source_row":
                19,
            "source_key":
                "personnel-long-orders:"
                "2004:row:019",
            "source_status":
                "normal",
            "source_text":
                "Про прийняття Іващенка В.П.",
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

    def test_04_historical_hire_reconciles_unknown_start_period(self):
        hire_date = fields.Date.from_string(
            "2004-08-06"
        )

        termination_date = fields.Date.from_string(
            "2004-10-21"
        )

        termination = self.env[
            "hr.personnel.order"
        ].create({
            "number": "23-к",
            "order_date":
                termination_date,
            "entry_mode":
                "historical",
            "order_type":
                "termination",
            "subject":
                "Спочатку відоме лише звільнення",
            "line_ids": [(0, 0, {
                "employee_name":
                    "Архівний Backfill Працівник",
                "identity_resolution":
                    "new",
                "historical_action_type":
                    "termination",
                "effective_date":
                    termination_date,
            })],
        })

        termination.action_register_historical()
        self.env.flush_all()

        employee = (
            termination.line_ids.employee_id
        )

        original_period = (
            termination.line_ids.employment_period_id
        )

        self.assertFalse(
            original_period.date_start,
        )

        self.assertEqual(
            original_period.date_end,
            termination_date,
        )

        period_count = self.env[
            "hr.personnel.employment.period"
        ].search_count(
            [
                (
                    "employee_id",
                    "=",
                    employee.id,
                ),
            ]
        )

        hire = self.env[
            "hr.personnel.order"
        ].create({
            "number": "01-к",
            "order_date":
                hire_date,
            "entry_mode":
                "historical",
            "order_type":
                "hire",
            "subject":
                "Пізніше знайдене прийняття",
            "line_ids": [(0, 0, {
                "employee_id":
                    employee.id,
                "historical_action_type":
                    "hire",
                "effective_date":
                    hire_date,
            })],
        })

        hire.action_register_historical()
        self.env.flush_all()

        original_period.invalidate_recordset()

        self.assertEqual(
            hire.line_ids.employment_period_id,
            original_period,
        )

        self.assertEqual(
            original_period.date_start,
            hire_date,
        )

        self.assertEqual(
            original_period.date_end,
            termination_date,
        )

        self.assertEqual(
            original_period.start_order_line_id,
            hire.line_ids,
        )

        self.assertEqual(
            original_period.end_order_line_id,
            termination.line_ids,
        )

        self.assertEqual(
            self.env[
                "hr.personnel.employment.period"
            ].search_count(
                [
                    (
                        "employee_id",
                        "=",
                        employee.id,
                    ),
                ]
            ),
            period_count,
        )

    def test_04_source_register_year_row_is_idempotent(self):
        source_date = fields.Date.from_string(
            "2004-12-14"
        )

        base = {
            "number":
                "34-к",
            "order_date":
                source_date,
            "entry_mode":
                "historical",
            "order_type":
                "other",
            "subject":
                "Source location identity",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал 2004",
            "source_year":
                2004,
            "source_row":
                3401,
            "source_status":
                "annulled",
            "source_text":
                "Source row",
            "source_note":
                "Анульований",
        }

        self.env[
            "hr.personnel.order"
        ].create({
            **base,
            "source_key":
                "source-location:first",
        })

        self.env.flush_all()

        with self.assertRaises(
            IntegrityError
        ):
            with self.env.cr.savepoint():
                self.env[
                    "hr.personnel.order"
                ].create({
                    **base,
                    # A different source_key must not permit
                    # the same physical journal row twice.
                    "source_key":
                        "source-location:second",
                    "number":
                        "34-к-duplicate",
                })

                self.env.flush_all()

    def test_04_historical_state_is_as_of_effective_date(self):
        hire_date = fields.Date.from_string(
            "2004-01-01"
        )

        february = fields.Date.from_string(
            "2004-02-01"
        )

        march = fields.Date.from_string(
            "2004-03-01"
        )

        hire = self.env[
            "hr.personnel.order"
        ].create({
            "number": "01-к",
            "order_date": hire_date,
            "entry_mode": "historical",
            "order_type": "hire",
            "subject": "Initial historical state",
            "line_ids": [(0, 0, {
                "employee_id":
                    self.employee.id,
                "historical_action_type":
                    "hire",
                "effective_date":
                    hire_date,
                "department_id":
                    self.department.id,
                "job_id":
                    self.job.id,
            })],
        })

        hire.action_register_historical()

        period = (
            hire.line_ids.employment_period_id
        )

        # Apply a future event first.
        march_order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "03-к",
            "order_date": march,
            "entry_mode": "historical",
            "order_type": "position_change",
            "subject": "March job change",
            "line_ids": [(0, 0, {
                "employee_id":
                    self.employee.id,
                "historical_action_type":
                    "position_change",
                "effective_date":
                    march,
                "job_id":
                    self.job_b.id,
            })],
        })

        march_order.action_register_historical()

        # Now backfill February. Its previous/new job must
        # come from the January state, not the future March
        # event.
        february_order = self.env[
            "hr.personnel.order"
        ].create({
            "number": "02-к",
            "order_date": february,
            "entry_mode": "historical",
            "order_type": "department_change",
            "subject": "February department change",
            "line_ids": [(0, 0, {
                "employee_id":
                    self.employee.id,
                "historical_action_type":
                    "department_change",
                "effective_date":
                    february,
                "department_id":
                    self.department_b.id,
            })],
        })

        february_order.action_register_historical()
        self.env.flush_all()

        feb_event = february_order.event_ids

        self.assertEqual(
            february_order.line_ids.employment_period_id,
            period,
        )

        self.assertEqual(
            feb_event.previous_job_id,
            self.job,
        )

        self.assertEqual(
            feb_event.new_job_id,
            self.job,
        )

        self.assertEqual(
            feb_event.previous_department_id,
            self.department,
        )

        self.assertEqual(
            feb_event.new_department_id,
            self.department_b,
        )

        # March fact itself remains intact, while its derived
        # previous/new department snapshots are reconciled to
        # include the February fact imported afterwards.
        march_event = march_order.event_ids

        self.assertEqual(
            march_event.previous_department_id,
            self.department_b,
        )

        self.assertEqual(
            march_event.new_department_id,
            self.department_b,
        )

        self.assertEqual(
            march_event.previous_job_id,
            self.job,
        )

        self.assertEqual(
            march_event.new_job_id,
            self.job_b,
        )

    def test_04_current_order_number_remains_unique_per_year(self):
        order_date = fields.Date.from_string(
            "2026-05-10"
        )

        self.env[
            "hr.personnel.order"
        ].create({
            "number": "CURRENT-001",
            "order_date": order_date,
            "entry_mode": "current",
            "order_type": "other",
            "subject": "Current order one",
        })

        with self.assertRaises(
            ValidationError
        ):
            self.env[
                "hr.personnel.order"
            ].create({
                "number": "CURRENT-001",
                "order_date": order_date,
                "entry_mode": "current",
                "order_type": "other",
                "subject": "Current duplicate",
            })

    def test_04_source_key_is_idempotent(self):
        order_date = fields.Date.from_string(
            "2004-12-14"
        )

        vals = {
            "number": "34-к",
            "order_date": order_date,
            "entry_mode": "historical",
            "order_type": "other",
            "subject": "Source-key idempotency",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал 2004",
            "source_year": 2004,
            "source_row": 3401,
            "source_key":
                "personnel-long-orders:"
                "2004:test:idempotency",
            "source_status": "annulled",
            "source_text": "Source row",
            "source_note": "Анульований",
        }

        self.env[
            "hr.personnel.order"
        ].create(vals)

        self.env.flush_all()

        with self.assertRaises(
            IntegrityError
        ):
            with self.env.cr.savepoint():
                self.env[
                    "hr.personnel.order"
                ].create({
                    **vals,
                    "number": "34-к-copy",
                    "source_year": 2004,
                    "source_row": 3402,
                })

                self.env.flush_all()

    def test_04_same_legal_number_can_have_distinct_source_rows(self):
        date_2004 = fields.Date.from_string(
            "2004-12-14"
        )

        common = {
            "number":
                "34-к",
            "order_date":
                date_2004,
            "entry_mode":
                "historical",
            "order_type":
                "other",
            "subject":
                "Duplicate legal number test",
            "source_register_key":
                "personnel-long-orders",
            "source_register_name":
                "Журнал 2004",
            "source_status":
                "annulled",
            "source_text":
                "Source row",
            "source_note":
                "Анульований",
        }

        first = self.env[
            "hr.personnel.order"
        ].create({
            **common,
            "source_year": 2004,
            "source_row":
                3401,
            "source_key":
                "personnel-long-orders:"
                "2004:row:3401",
        })

        second = self.env[
            "hr.personnel.order"
        ].create({
            **common,
            "source_year": 2004,
            "source_row":
                3402,
            "source_key":
                "personnel-long-orders:"
                "2004:row:3402",
        })

        self.env.flush_all()

        self.assertNotEqual(
            first.id,
            second.id,
        )

        self.assertEqual(
            first.number,
            second.number,
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

    def test_04_job_name_matching_uses_unicode_nfkc(self):
        Job = self.env["hr.job"]

        self.assertEqual(
            Job.l10n_ua_job_name_key(
                "ABC"
            ),
            Job.l10n_ua_job_name_key(
                "ＡＢＣ"
            ),
        )

        found = (
            Job.l10n_ua_find_canonical_job(
                "КШЗ ＴＥＳＴ Посада A",
                company=self.env.company,
            )
        )

        self.assertEqual(
            found,
            self.job,
        )

    def test_04_factual_period_is_immutable_outside_engine(self):
        historical_date = fields.Date.from_string(
            "2004-08-06"
        )

        order = self.env[
            "hr.personnel.order"
        ].create({
            "number":
                "01-к",
            "order_date":
                historical_date,
            "entry_mode":
                "historical",
            "order_type":
                "hire",
            "subject":
                "Immutable factual period",
            "line_ids": [(0, 0, {
                "employee_id":
                    self.employee.id,
                "historical_action_type":
                    "hire",
                "effective_date":
                    historical_date,
            })],
        })

        order.action_register_historical()

        period = (
            order.line_ids.employment_period_id
        )

        with self.assertRaises(
            UserError
        ):
            period.write({
                "date_end":
                    historical_date,
            })

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
