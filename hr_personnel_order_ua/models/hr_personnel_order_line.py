import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .constants import (
    ENGINE_CONTEXT_KEY,
    HIRE_CONDITION_SELECTION,
    WORK_TYPE_SELECTION,
)

_logger = logging.getLogger(__name__)


class HrPersonnelOrderLine(models.Model):
    _name = "hr.personnel.order.line"
    _description = "Рядок кадрового наказу"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one(
        "hr.personnel.order",
        string="Кадровий наказ",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="order_id.company_id", store=True, index=True)
    order_type = fields.Selection(related="order_id.order_type", store=True, index=True)
    order_state = fields.Selection(related="order_id.state", store=True, index=True)

    employee_id = fields.Many2one(
        "hr.employee",
        string="Працівник",
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    employee_name = fields.Char(
        string="ПІБ працівника",
        help="Для наказу про прийняття, якщо картки працівника ще немає.",
    )
    employee_identification_id = fields.Char(string="Табельний номер")

    effective_date = fields.Date(
        string="Дата набрання чинності",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    application_state = fields.Selection(
        [
            ("pending", "Очікує застосування"),
            ("applied", "Застосовано"),
            ("reversed", "Скасовано компенсуючою подією"),
        ],
        string="Стан застосування",
        required=True,
        default="pending",
        readonly=True,
        copy=False,
        index=True,
    )
    application_error = fields.Text(string="Помилка застосування", readonly=True, copy=False)
    last_application_attempt_at = fields.Datetime(
        string="Остання спроба застосування",
        readonly=True,
        copy=False,
    )
    applied_at = fields.Datetime(string="Застосовано", readonly=True, copy=False)
    applied_by_id = fields.Many2one("res.users", string="Застосував", readonly=True, copy=False)

    previous_department_id = fields.Many2one(
        "hr.department", string="Попередній підрозділ", readonly=True
    )
    previous_job_id = fields.Many2one("hr.job", string="Попередня посада", readonly=True)
    previous_resource_calendar_id = fields.Many2one(
        "resource.calendar", string="Попередній графік", readonly=True
    )
    previous_wage = fields.Monetary(
        string="Попередній оклад", currency_field="currency_id", readonly=True
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Новий підрозділ",
        domain="[('company_id', 'in', [False, company_id])]",
    )
    job_id = fields.Many2one(
        "hr.job",
        string="Нова посада",
        domain="[('company_id', 'in', [False, company_id])]",
    )
    professional_category_id = fields.Many2one(
        "hr.professional.category",
        string="Професійна категорія / розряд",
        domain="[('company_id', 'in', [False, company_id])]",
    )
    resource_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Новий графік роботи",
        domain="[('company_id', 'in', [False, company_id])]",
    )

    employment_end_date = fields.Date(string="Дата закінчення строкового договору")
    probation_months = fields.Integer(string="Випробувальний строк, місяців")
    trial_date_end = fields.Date(string="Дата завершення випробування")
    work_type = fields.Selection(WORK_TYPE_SELECTION, string="Вид роботи")
    hire_condition = fields.Selection(HIRE_CONDITION_SELECTION, string="Умова прийняття")
    weekly_hours = fields.Float(string="Тривалість робочого тижня, год.")
    work_conditions = fields.Text(string="Умови праці")
    allowance_note = fields.Text(string="Надбавки / доплати")
    wage = fields.Monetary(string="Оклад / тарифна ставка", currency_field="currency_id")
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True
    )

    leave_type_id = fields.Many2one(
        "hr.leave.type",
        string="Вид відпустки",
        domain="[('company_id', 'in', [False, company_id])]",
    )
    work_period_from = fields.Date(string="Робочий період з")
    work_period_to = fields.Date(string="Робочий період по")
    leave_date_from = fields.Date(string="Відпустка з")
    leave_date_to = fields.Date(string="Відпустка по")
    leave_calendar_days = fields.Integer(
        string="Календарні дні за наказом",
        compute="_compute_leave_calendar_days",
        store=True,
    )
    health_assistance = fields.Boolean(string="Матеріальна допомога на оздоровлення")

    departure_reason_id = fields.Many2one("hr.departure.reason", string="Причина звільнення")
    legal_reason = fields.Char(string="Формулювання причини")
    legal_article = fields.Char(string="Стаття КЗпП / правова підстава")
    termination_basis = fields.Text(string="Документальна підстава звільнення")
    basis_document_number = fields.Char(string="Номер документа-підстави")
    basis_document_date = fields.Date(string="Дата документа-підстави")
    unused_leave_days = fields.Float(string="Компенсація невикористаної відпустки, днів")
    severance_amount = fields.Monetary(
        string="Вихідна допомога", currency_field="currency_id"
    )

    contract_id = fields.Many2one(
        "hr.contract",
        string="Створений / змінений контракт",
        readonly=True,
        copy=False,
    )
    leave_id = fields.Many2one(
        "hr.leave", string="Створена відпустка", readonly=True, copy=False
    )
    event_ids = fields.One2many(
        "hr.personnel.event", "order_line_id", string="Кадрові події", readonly=True
    )
    note = fields.Text(string="Примітка")

    @api.model
    def _employee_snapshot_values(self, employee):
        contract = employee.contract_id
        return {
            "employee_name": employee.name,
            "employee_identification_id": employee.identification_id,
            "previous_department_id": employee.department_id.id or False,
            "previous_job_id": employee.job_id.id or False,
            "previous_resource_calendar_id": employee.resource_calendar_id.id or False,
            "previous_wage": contract.wage if contract else 0.0,
        }

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            employee_id = vals.get("employee_id")
            if employee_id:
                employee = self.env["hr.employee"].browse(employee_id).exists()
                if employee:
                    snapshot = self._employee_snapshot_values(employee)
                    for key, value in snapshot.items():
                        vals.setdefault(key, value)
            prepared.append(vals)
        return super().create(prepared)

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for line in self:
            if not line.employee_id:
                continue
            snapshot = self._employee_snapshot_values(line.employee_id)
            for key, value in snapshot.items():
                setattr(line, key, value)

    @api.onchange("probation_months", "effective_date")
    def _onchange_probation_months(self):
        for line in self:
            if line.effective_date and line.probation_months and not line.trial_date_end:
                line.trial_date_end = line.effective_date + relativedelta(
                    months=line.probation_months
                )

    @api.constrains("order_type", "employee_id", "employee_name")
    def _check_employee_reference(self):
        for line in self:
            if line.order_type == "hire":
                if not line.employee_id and not (line.employee_name or "").strip():
                    raise ValidationError(
                        "Для наказу про прийняття вкажіть існуючого працівника "
                        "або ПІБ майбутнього працівника."
                    )
            elif not line.employee_id:
                raise ValidationError(
                    "Для цього типу кадрового наказу необхідно вибрати працівника."
                )

    @api.depends("leave_date_from", "leave_date_to")
    def _compute_leave_calendar_days(self):
        for line in self:
            if line.leave_date_from and line.leave_date_to and line.leave_date_to >= line.leave_date_from:
                line.leave_calendar_days = (line.leave_date_to - line.leave_date_from).days + 1
            else:
                line.leave_calendar_days = 0

    @api.constrains("work_period_from", "work_period_to")
    def _check_work_period(self):
        for line in self:
            if line.work_period_from and line.work_period_to and line.work_period_from > line.work_period_to:
                raise ValidationError(
                    "Початок робочого періоду не може бути пізніше завершення."
                )

    @api.constrains("leave_date_from", "leave_date_to")
    def _check_leave_period(self):
        for line in self:
            if line.leave_date_from and line.leave_date_to and line.leave_date_from > line.leave_date_to:
                raise ValidationError("Початок відпустки не може бути пізніше завершення.")

    @api.constrains("probation_months")
    def _check_probation_months(self):
        for line in self:
            if line.probation_months < 0:
                raise ValidationError("Випробувальний строк не може бути від'ємним.")

    def _validate_for_post(self):
        for line in self:
            if not line.effective_date:
                raise ValidationError(_("Вкажіть дату набрання чинності."))

            if line.order_type == "hire":
                if not line.employee_id and not (line.employee_name or "").strip():
                    raise ValidationError(_("Для прийняття вкажіть ПІБ працівника."))
                if not line.department_id:
                    raise ValidationError(_("Для прийняття вкажіть структурний підрозділ."))
                if not line.job_id:
                    raise ValidationError(_("Для прийняття вкажіть посаду."))
                if line.wage <= 0:
                    raise ValidationError(_("Для прийняття вкажіть додатний оклад / тарифну ставку."))

            elif line.order_type == "leave":
                if not line.employee_id:
                    raise ValidationError(_("Для відпустки виберіть працівника."))
                if not line.leave_type_id or not line.leave_date_from or not line.leave_date_to:
                    raise ValidationError(_("Для відпустки вкажіть вид і період відпустки."))

            elif line.order_type == "termination":
                if not line.employee_id:
                    raise ValidationError(_("Для звільнення виберіть працівника."))
                if not line.departure_reason_id and not (line.legal_reason or "").strip():
                    raise ValidationError(
                        _("Для звільнення вкажіть причину або формулювання причини.")
                    )

            elif line.order_type == "position_change" and not line.job_id:
                raise ValidationError(_("Для зміни посади вкажіть нову посаду."))
            elif line.order_type == "department_change" and not line.department_id:
                raise ValidationError(_("Для зміни підрозділу вкажіть новий підрозділ."))
            elif line.order_type == "schedule_change" and not line.resource_calendar_id:
                raise ValidationError(_("Для зміни графіка вкажіть новий робочий графік."))
            elif line.order_type == "salary_change" and line.wage <= 0:
                raise ValidationError(_("Для зміни оплати праці вкажіть додатний новий оклад."))
            elif line.order_type == "transfer" and not any([
                line.department_id,
                line.job_id,
                line.resource_calendar_id,
                line.professional_category_id,
                line.wage > 0,
                line.work_type,
                line.hire_condition,
                line.weekly_hours > 0,
                line.work_conditions,
                line.allowance_note,
            ]):
                raise ValidationError(_("Для переведення вкажіть хоча б одну нову кадрову умову."))

        return True

    def _current_contract(self, employee):
        self.ensure_one()
        if employee.contract_id and employee.contract_id.state == "open":
            return employee.contract_id
        return self.env["hr.contract"].sudo().search(
            [
                ("employee_id", "=", employee.id),
                ("company_id", "=", self.company_id.id),
                ("state", "=", "open"),
                ("date_start", "<=", self.effective_date),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", self.effective_date),
            ],
            order="date_start desc, id desc",
            limit=1,
        )

    def _event_effective_date(self):
        self.ensure_one()
        if self.order_type == "leave" and self.leave_date_from:
            return self.leave_date_from
        return self.effective_date

    def _event_base_values(self, employee=False, status="planned"):
        self.ensure_one()
        return {
            "name": f"{self.order_id.number}: {self.order_id.subject}",
            "order_id": self.order_id.id,
            "order_line_id": self.id,
            "employee_id": employee.id if employee else self.employee_id.id or False,
            "effective_date": self._event_effective_date(),
            "status": status,
            "new_department_id": self.department_id.id or False,
            "new_job_id": self.job_id.id or False,
            "new_resource_calendar_id": self.resource_calendar_id.id or False,
            "new_wage": self.wage,
            "professional_category_id": self.professional_category_id.id or False,
            "work_type": self.work_type or False,
            "hire_condition": self.hire_condition or False,
            "weekly_hours": self.weekly_hours,
            "work_conditions": self.work_conditions or False,
            "allowance_note": self.allowance_note or False,
            "leave_type_id": self.leave_type_id.id or False,
            "work_period_from": self.work_period_from,
            "work_period_to": self.work_period_to,
            "leave_date_from": self.leave_date_from,
            "leave_date_to": self.leave_date_to,
            "leave_calendar_days": self.leave_calendar_days,
            "health_assistance": self.health_assistance,
            "departure_reason_id": self.departure_reason_id.id or False,
            "legal_reason": self.legal_reason or False,
            "legal_article": self.legal_article or False,
            "termination_basis": self.termination_basis or False,
            "basis_document_number": self.basis_document_number or False,
            "basis_document_date": self.basis_document_date,
            "unused_leave_days": self.unused_leave_days,
            "severance_amount": self.severance_amount,
            "description": self._event_description(),
        }

    def _event_description(self):
        self.ensure_one()
        parts = [self.order_id.subject]
        if self.order_id.basis:
            parts.append(f"Підстава: {self.order_id.basis}")
        if self.note:
            parts.append(f"Примітка: {self.note}")
        if self.legal_reason:
            parts.append(f"Причина: {self.legal_reason}")
        if self.legal_article:
            parts.append(f"Правова підстава: {self.legal_article}")
        if self.termination_basis:
            parts.append(f"Документальна підстава: {self.termination_basis}")
        if self.unused_leave_days:
            parts.append(
                f"Компенсація невикористаної відпустки: {self.unused_leave_days:g} дн."
            )
        if self.severance_amount:
            parts.append(f"Вихідна допомога: {self.severance_amount:g}")
        return "\n".join(parts)

    def _ensure_planned_event(self):
        self.ensure_one()
        event = self.event_ids.filtered(lambda item: item.status != "reversed")[:1]
        if event:
            return event
        return self.env["hr.personnel.event"].sudo().create(
            self._event_base_values(status="planned")
        )

    def _actual_state(self, employee, contract=False):
        return {
            "previous_department_id": employee.department_id.id or False,
            "previous_job_id": employee.job_id.id or False,
            "previous_resource_calendar_id": employee.resource_calendar_id.id or False,
            "previous_wage": contract.wage if contract else 0.0,
        }

    def _finalize_event(self, event, employee, contract=False, leave=False, previous=None):
        previous = previous or self._actual_state(employee, contract)
        vals = dict(previous)
        vals.update({
            "employee_id": employee.id,
            "status": "applied",
            "new_department_id": employee.department_id.id or False,
            "new_job_id": employee.job_id.id or False,
            "new_resource_calendar_id": employee.resource_calendar_id.id or False,
            "new_wage": contract.wage if contract else self.wage,
            "contract_id": contract.id if contract else False,
            "leave_id": leave.id if leave else False,
            "applied_at": fields.Datetime.now(),
            "applied_by_id": self.env.user.id,
        })
        event.sudo().with_context(personnel_event_maintenance=True).write(vals)

    def _mark_applied(self, employee, contract=False, leave=False):
        self.ensure_one()
        self.with_context(**{ENGINE_CONTEXT_KEY: True}).sudo().write({
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_identification_id": employee.identification_id,
            "contract_id": contract.id if contract else False,
            "leave_id": leave.id if leave else False,
            "application_state": "applied",
            "application_error": False,
            "last_application_attempt_at": fields.Datetime.now(),
            "applied_at": fields.Datetime.now(),
            "applied_by_id": self.env.user.id,
        })

    def _apply_hire(self, event):
        self.ensure_one()
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        employee = self.employee_id.sudo() if self.employee_id else False

        if self.employee_identification_id:
            duplicate = Employee.search(
                [
                    ("identification_id", "=", self.employee_identification_id),
                    ("id", "!=", employee.id if employee else 0),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("Табельний номер %s уже належить працівнику %s.")
                    % (self.employee_identification_id, duplicate.name)
                )

        previous = self._actual_state(employee, self._current_contract(employee)) if employee else {
            "previous_department_id": False,
            "previous_job_id": False,
            "previous_resource_calendar_id": False,
            "previous_wage": 0.0,
        }

        employee_vals = {
            "company_id": self.company_id.id,
            "department_id": self.department_id.id,
            "job_id": self.job_id.id,
            "active": True,
            "service_hire_date": self.effective_date,
        }
        if self.employee_identification_id:
            employee_vals["identification_id"] = self.employee_identification_id
        if self.resource_calendar_id:
            employee_vals["resource_calendar_id"] = self.resource_calendar_id.id

        if employee:
            employee.write(employee_vals)
        else:
            employee_vals["name"] = self.employee_name.strip()
            employee = Employee.create(employee_vals)

        existing_contract = self._current_contract(employee)
        if existing_contract:
            raise ValidationError(
                _("Працівник %s уже має діючий контракт %s.")
                % (employee.name, existing_contract.display_name)
            )

        calendar = (
            self.resource_calendar_id
            or employee.resource_calendar_id
            or self.company_id.resource_calendar_id
        )
        if not calendar:
            raise ValidationError(_("Для прийняття необхідний робочий графік."))

        trial_date_end = self.trial_date_end
        if not trial_date_end and self.probation_months:
            trial_date_end = self.effective_date + relativedelta(months=self.probation_months)

        contract_vals = {
            "name": f"{self.order_id.number} — {employee.name}",
            "employee_id": employee.id,
            "company_id": self.company_id.id,
            "department_id": self.department_id.id,
            "job_id": self.job_id.id,
            "date_start": self.effective_date,
            "date_end": self.employment_end_date,
            "trial_date_end": trial_date_end,
            "resource_calendar_id": calendar.id,
            "wage": self.wage,
            "state": "open",
            "l10n_ua_personnel_order_line_id": self.id,
            "l10n_ua_work_type": self.work_type or "main",
            "l10n_ua_hire_condition": self.hire_condition or False,
            "l10n_ua_weekly_hours": self.weekly_hours,
            "l10n_ua_work_conditions": self.work_conditions or False,
            "l10n_ua_allowance_note": self.allowance_note or False,
        }
        if self.professional_category_id:
            contract_vals["professional_category_id"] = self.professional_category_id.id

        contract = self.env["hr.contract"].sudo().create(contract_vals)
        employee.write({"contract_id": contract.id})
        self._finalize_event(event, employee, contract=contract, previous=previous)
        self._mark_applied(employee, contract=contract)

    def _apply_employment_change(self, event):
        self.ensure_one()
        employee = self.employee_id.sudo()
        contract = self._current_contract(employee)
        previous = self._actual_state(employee, contract)

        employee_vals = {}
        contract_vals = {"l10n_ua_personnel_order_line_id": self.id}

        if self.order_type in {
            "transfer", "department_change", "employment_condition_change"
        } and self.department_id:
            employee_vals["department_id"] = self.department_id.id
            if contract:
                contract_vals["department_id"] = self.department_id.id

        if self.order_type in {
            "transfer", "position_change", "employment_condition_change"
        } and self.job_id:
            employee_vals["job_id"] = self.job_id.id
            if contract:
                contract_vals["job_id"] = self.job_id.id

        if self.order_type in {
            "transfer", "schedule_change", "employment_condition_change"
        } and self.resource_calendar_id:
            employee_vals["resource_calendar_id"] = self.resource_calendar_id.id
            if contract:
                contract_vals["resource_calendar_id"] = self.resource_calendar_id.id

        contract_required = self.order_type in {
            "salary_change", "schedule_change", "employment_condition_change"
        }
        if contract_required and not contract:
            raise ValidationError(
                _("Для кадрової зміни працівник %s повинен мати діючий контракт.")
                % employee.name
            )

        if contract:
            if self.professional_category_id:
                contract_vals["professional_category_id"] = self.professional_category_id.id
            if self.order_type == "salary_change" or (
                self.order_type in {"transfer", "employment_condition_change"}
                and self.wage > 0
            ):
                contract_vals["wage"] = self.wage
            if self.work_type:
                contract_vals["l10n_ua_work_type"] = self.work_type
            if self.hire_condition:
                contract_vals["l10n_ua_hire_condition"] = self.hire_condition
            if self.weekly_hours > 0:
                contract_vals["l10n_ua_weekly_hours"] = self.weekly_hours
            if self.work_conditions:
                contract_vals["l10n_ua_work_conditions"] = self.work_conditions
            if self.allowance_note:
                contract_vals["l10n_ua_allowance_note"] = self.allowance_note

            contract.write(contract_vals)

        if employee_vals:
            employee.write(employee_vals)

        self._finalize_event(event, employee, contract=contract, previous=previous)
        self._mark_applied(employee, contract=contract)

    def _apply_leave(self, event):
        self.ensure_one()
        employee = self.employee_id.sudo()
        contract = self._current_contract(employee)
        previous = self._actual_state(employee, contract)

        leave = self.leave_id.sudo() if self.leave_id else False
        if not leave:
            leave = self.env["hr.leave"].sudo().create({
                "employee_id": employee.id,
                "holiday_status_id": self.leave_type_id.id,
                "request_date_from": self.leave_date_from,
                "request_date_to": self.leave_date_to,
                "private_name": f"{self.order_id.number}: {self.order_id.subject}",
                "l10n_ua_personnel_order_line_id": self.id,
                "l10n_ua_work_period_from": self.work_period_from,
                "l10n_ua_work_period_to": self.work_period_to,
                "l10n_ua_calendar_days": self.leave_calendar_days,
                "l10n_ua_health_assistance": self.health_assistance,
            })

        if leave.state != "validate":
            leave.sudo().action_validate(check_state=False)

        self._finalize_event(
            event,
            employee,
            contract=contract,
            leave=leave,
            previous=previous,
        )
        self._mark_applied(employee, contract=contract, leave=leave)

    def _apply_termination(self, event):
        self.ensure_one()
        employee = self.employee_id.sudo()
        contract = self._current_contract(employee)
        previous = self._actual_state(employee, contract)

        if contract:
            contract.write({
                "date_end": self.effective_date,
                "state": "close",
                "l10n_ua_personnel_order_line_id": self.id,
            })

        description_parts = [part for part in [self.legal_reason, self.legal_article] if part]
        if self.termination_basis:
            description_parts.append(self.termination_basis)

        employee_vals = {
            "departure_date": self.effective_date,
            "active": False,
        }
        if self.departure_reason_id:
            employee_vals["departure_reason_id"] = self.departure_reason_id.id
        if description_parts:
            employee_vals["departure_description"] = "\n".join(description_parts)
        employee.write(employee_vals)

        self._finalize_event(event, employee, contract=contract, previous=previous)
        self._mark_applied(employee, contract=contract)

    def _apply_generic_event(self, event):
        self.ensure_one()
        employee = self.employee_id.sudo()
        contract = self._current_contract(employee) if employee else False
        previous = self._actual_state(employee, contract) if employee else {}
        self._finalize_event(event, employee, contract=contract, previous=previous)
        self._mark_applied(employee, contract=contract)

    def _apply_from_order(self):
        for line in self:
            if line.order_state != "posted":
                raise UserError(_("Застосовувати можна лише проведений кадровий наказ."))
            if line.application_state == "applied":
                continue

            line.with_context(**{ENGINE_CONTEXT_KEY: True}).sudo().write({
                "last_application_attempt_at": fields.Datetime.now(),
                "application_error": False,
            })
            event = line._ensure_planned_event()

            if line.order_type == "hire":
                line._apply_hire(event)
            elif line.order_type in {
                "transfer",
                "position_change",
                "department_change",
                "salary_change",
                "schedule_change",
                "employment_condition_change",
            }:
                line._apply_employment_change(event)
            elif line.order_type == "leave":
                line._apply_leave(event)
            elif line.order_type == "termination":
                line._apply_termination(event)
            else:
                line._apply_generic_event(event)
        return True

    @api.model
    def _cron_apply_due_lines(self):
        today = fields.Date.context_today(self)
        lines = self.sudo().search(
            [
                ("order_state", "=", "posted"),
                ("application_state", "=", "pending"),
                ("effective_date", "<=", today),
            ],
            order="effective_date asc, order_id asc, sequence asc, id asc",
            limit=200,
        )
        for line in lines:
            old_error = line.application_error
            try:
                with self.env.cr.savepoint():
                    line.with_context(**{ENGINE_CONTEXT_KEY: True})._apply_from_order()
            except Exception as exc:  # cron must continue with unrelated employees
                _logger.exception(
                    "Failed to apply personnel order line %s from order %s",
                    line.id,
                    line.order_id.number,
                )
                line.invalidate_recordset()
                error = str(exc)[:4000]
                line.with_context(**{ENGINE_CONTEXT_KEY: True}).sudo().write({
                    "application_error": error,
                    "last_application_attempt_at": fields.Datetime.now(),
                })
                if error != old_error:
                    line.order_id.sudo().message_post(
                        body=_(
                            "Не вдалося автоматично застосувати кадрову дію для %s: %s"
                        ) % (line.employee_name or line.employee_id.name or _("працівника"), error)
                    )
        return True

    def write(self, vals):
        business_fields = {
            "employee_id", "employee_name", "employee_identification_id",
            "effective_date", "department_id", "job_id", "professional_category_id",
            "resource_calendar_id", "employment_end_date", "probation_months",
            "trial_date_end", "work_type", "hire_condition", "weekly_hours",
            "work_conditions", "allowance_note", "wage", "leave_type_id",
            "work_period_from", "work_period_to", "leave_date_from", "leave_date_to",
            "health_assistance", "departure_reason_id", "legal_reason", "legal_article",
            "termination_basis", "basis_document_number", "basis_document_date",
            "unused_leave_days", "severance_amount", "note",
        }
        if (
            business_fields.intersection(vals)
            and not self.env.context.get(ENGINE_CONTEXT_KEY)
            and self.filtered(lambda line: line.order_id.state in {"posted", "cancelled"})
        ):
            raise UserError(
                "Рядки проведеного або скасованого кадрового наказу не можна змінювати."
            )
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda line: line.order_id.state in {"posted", "cancelled"}):
            raise UserError(
                "Рядки проведеного або скасованого кадрового наказу не можна видаляти."
            )
        return super().unlink()
