from odoo import fields, models
from odoo.exceptions import UserError

from .constants import HIRE_CONDITION_SELECTION, WORK_TYPE_SELECTION


class HrPersonnelEvent(models.Model):
    _name = "hr.personnel.event"
    _description = "Кадрова подія"
    _order = "effective_date desc, id desc"

    name = fields.Char(string="Опис події", required=True, index=True)
    order_id = fields.Many2one(
        "hr.personnel.order",
        string="Кадровий наказ",
        required=True,
        ondelete="restrict",
        index=True,
    )
    order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Рядок наказу",
        required=True,
        ondelete="restrict",
        index=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Працівник",
        index=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id",
        store=True,
        index=True,
    )
    event_type = fields.Selection(
        related="order_id.order_type",
        store=True,
        string="Тип події",
        index=True,
    )
    effective_date = fields.Date(
        string="Дата набрання чинності",
        required=True,
        index=True,
    )
    status = fields.Selection(
        [
            ("planned", "Заплановано"),
            ("applied", "Застосовано"),
            ("reversed", "Скасовано компенсуючою подією"),
        ],
        string="Статус",
        required=True,
        default="planned",
        index=True,
    )

    previous_department_id = fields.Many2one("hr.department", string="Попередній підрозділ")
    new_department_id = fields.Many2one("hr.department", string="Новий підрозділ")
    previous_job_id = fields.Many2one("hr.job", string="Попередня посада")
    new_job_id = fields.Many2one("hr.job", string="Нова посада")
    previous_resource_calendar_id = fields.Many2one(
        "resource.calendar", string="Попередній графік"
    )
    new_resource_calendar_id = fields.Many2one(
        "resource.calendar", string="Новий графік"
    )
    previous_wage = fields.Monetary(
        string="Попередній оклад",
        currency_field="currency_id",
    )
    new_wage = fields.Monetary(
        string="Новий оклад",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    professional_category_id = fields.Many2one(
        "hr.professional.category",
        string="Професійна категорія / розряд",
    )
    work_type = fields.Selection(WORK_TYPE_SELECTION, string="Вид роботи")
    hire_condition = fields.Selection(
        HIRE_CONDITION_SELECTION,
        string="Умова прийняття / зміни умов",
    )
    weekly_hours = fields.Float(string="Тривалість робочого тижня, год.")
    work_conditions = fields.Text(string="Умови праці")
    allowance_note = fields.Text(string="Надбавки / доплати")

    leave_type_id = fields.Many2one("hr.leave.type", string="Вид відпустки")
    work_period_from = fields.Date(string="Робочий період з")
    work_period_to = fields.Date(string="Робочий період по")
    leave_date_from = fields.Date(string="Відпустка з")
    leave_date_to = fields.Date(string="Відпустка по")
    leave_calendar_days = fields.Integer(string="Календарні дні за наказом")
    health_assistance = fields.Boolean(string="Матеріальна допомога на оздоровлення")

    departure_reason_id = fields.Many2one("hr.departure.reason", string="Причина звільнення")
    legal_reason = fields.Char(string="Формулювання причини")
    legal_article = fields.Char(string="Стаття КЗпП / правова підстава")
    termination_basis = fields.Text(string="Документальна підстава звільнення")
    basis_document_number = fields.Char(string="Номер документа-підстави")
    basis_document_date = fields.Date(string="Дата документа-підстави")
    unused_leave_days = fields.Float(string="Компенсація невикористаної відпустки, днів")
    severance_amount = fields.Monetary(
        string="Вихідна допомога",
        currency_field="currency_id",
    )

    contract_id = fields.Many2one("hr.contract", string="Контракт", readonly=True)
    leave_id = fields.Many2one("hr.leave", string="Відпустка", readonly=True)
    description = fields.Text(string="Деталі")

    applied_at = fields.Datetime(string="Застосовано", readonly=True)
    applied_by_id = fields.Many2one("res.users", string="Застосував", readonly=True)
    reversed_at = fields.Datetime(string="Скасовано", readonly=True)
    reversed_by_id = fields.Many2one("res.users", string="Скасував", readonly=True)

    def write(self, vals):
        if not self.env.context.get("personnel_event_maintenance"):
            raise UserError(
                "Кадрова подія є незмінним журналом. "
                "Зміни дозволені лише через кадровий механізм застосування/скасування."
            )
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("personnel_event_maintenance"):
            raise UserError("Кадрові події не можна видаляти.")
        return super().unlink()
