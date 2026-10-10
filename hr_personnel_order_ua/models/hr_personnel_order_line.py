from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
    company_id = fields.Many2one(
        related="order_id.company_id",
        store=True,
        index=True,
    )
    order_type = fields.Selection(
        related="order_id.order_type",
        store=True,
        index=True,
    )
    order_state = fields.Selection(
        related="order_id.state",
        store=True,
        index=True,
    )

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

    previous_department_id = fields.Many2one(
        "hr.department", string="Попередній підрозділ", readonly=True
    )
    previous_job_id = fields.Many2one(
        "hr.job", string="Попередня посада", readonly=True
    )
    previous_resource_calendar_id = fields.Many2one(
        "resource.calendar", string="Попередній графік", readonly=True
    )
    previous_wage = fields.Monetary(
        string="Попередній оклад",
        currency_field="currency_id",
        readonly=True,
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
    work_type = fields.Selection(
        [
            ("main", "Основне місце роботи"),
            ("part_time", "За сумісництвом"),
        ],
        string="Вид роботи",
        default="main",
    )
    hire_condition = fields.Selection(
        [
            ("competition", "На конкурсній основі"),
            ("contract", "За умовами контракту"),
            ("fixed_work", "На час виконання певної роботи"),
            ("replacement", "На період відсутності основного працівника"),
            ("personnel_reserve", "Із кадрового резерву"),
            ("internship", "За результатами успішного стажування"),
            ("transfer", "Переведення"),
            ("other", "Інша умова"),
        ],
        string="Умова прийняття",
    )
    weekly_hours = fields.Float(string="Тривалість робочого тижня, год.")
    work_conditions = fields.Text(string="Умови праці")
    allowance_note = fields.Text(string="Надбавки / доплати")
    wage = fields.Monetary(
        string="Оклад / тарифна ставка",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
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
    health_assistance = fields.Boolean(string="Матеріальна допомога на оздоровлення")

    departure_reason_id = fields.Many2one(
        "hr.departure.reason",
        string="Причина звільнення",
    )
    legal_reason = fields.Char(string="Формулювання причини")
    legal_article = fields.Char(string="Стаття КЗпП / правова підстава")
    termination_basis = fields.Text(string="Документальна підстава звільнення")
    basis_document_number = fields.Char(string="Номер документа-підстави")
    basis_document_date = fields.Date(string="Дата документа-підстави")
    unused_leave_days = fields.Float(
        string="Компенсація невикористаної відпустки, днів"
    )
    severance_amount = fields.Monetary(
        string="Вихідна допомога",
        currency_field="currency_id",
    )

    contract_id = fields.Many2one(
        "hr.contract",
        string="Створений / змінений контракт",
        readonly=True,
        copy=False,
    )
    leave_id = fields.Many2one(
        "hr.leave",
        string="Створена відпустка",
        readonly=True,
        copy=False,
    )
    event_ids = fields.One2many(
        "hr.personnel.event",
        "order_line_id",
        string="Кадрові події",
        readonly=True,
    )
    note = fields.Text(string="Примітка")

    @api.model
    def _employee_snapshot_values(self, employee):
        contract = getattr(employee, "contract_id", False)
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

    @api.constrains("work_period_from", "work_period_to")
    def _check_work_period(self):
        for line in self:
            if (
                line.work_period_from
                and line.work_period_to
                and line.work_period_from > line.work_period_to
            ):
                raise ValidationError(
                    "Початок робочого періоду не може бути пізніше завершення."
                )

    @api.constrains("leave_date_from", "leave_date_to")
    def _check_leave_period(self):
        for line in self:
            if (
                line.leave_date_from
                and line.leave_date_to
                and line.leave_date_from > line.leave_date_to
            ):
                raise ValidationError(
                    "Початок відпустки не може бути пізніше завершення."
                )

    @api.constrains(
        "order_type", "leave_type_id", "leave_date_from", "leave_date_to"
    )
    def _check_leave_data(self):
        for line in self.filtered(lambda item: item.order_type == "leave"):
            if (
                not line.leave_type_id
                or not line.leave_date_from
                or not line.leave_date_to
            ):
                raise ValidationError(
                    "Для наказу про відпустку необхідно вказати вид "
                    "та період відпустки."
                )

    @api.constrains("probation_months")
    def _check_probation_months(self):
        for line in self:
            if line.probation_months < 0:
                raise ValidationError(
                    "Випробувальний строк не може бути від'ємним."
                )

    def write(self, vals):
        business_fields = {
            "employee_id",
            "employee_name",
            "employee_identification_id",
            "effective_date",
            "department_id",
            "job_id",
            "professional_category_id",
            "resource_calendar_id",
            "employment_end_date",
            "probation_months",
            "trial_date_end",
            "work_type",
            "hire_condition",
            "weekly_hours",
            "work_conditions",
            "allowance_note",
            "wage",
            "leave_type_id",
            "work_period_from",
            "work_period_to",
            "leave_date_from",
            "leave_date_to",
            "health_assistance",
            "departure_reason_id",
            "legal_reason",
            "legal_article",
            "termination_basis",
            "basis_document_number",
            "basis_document_date",
            "unused_leave_days",
            "severance_amount",
            "note",
        }
        if business_fields.intersection(vals):
            if self.filtered(
                lambda line: line.order_id.state in {"posted", "cancelled"}
            ):
                raise UserError(
                    "Рядки проведеного або скасованого кадрового наказу "
                    "не можна змінювати."
                )
        return super().write(vals)

    def unlink(self):
        if self.filtered(
            lambda line: line.order_id.state in {"posted", "cancelled"}
        ):
            raise UserError(
                "Рядки проведеного або скасованого кадрового наказу "
                "не можна видаляти."
            )
        return super().unlink()
