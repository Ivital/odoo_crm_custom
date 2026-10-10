from odoo import _, fields, models

from .constants import HIRE_CONDITION_SELECTION, WORK_TYPE_SELECTION


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    personnel_order_count = fields.Integer(
        string="Кадрові накази",
        compute="_compute_personnel_counts",
    )
    personnel_event_count = fields.Integer(
        string="Кадрова історія",
        compute="_compute_personnel_counts",
    )

    l10n_ua_current_contract_id = fields.Many2one(
        related="contract_id",
        string="Поточний контракт",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_contract_date_start = fields.Date(
        related="contract_id.date_start",
        string="Дата початку поточного контракту",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_contract_date_end = fields.Date(
        related="contract_id.date_end",
        string="Дата завершення поточного контракту",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_trial_date_end = fields.Date(
        related="contract_id.trial_date_end",
        string="Дата завершення випробування",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_currency_id = fields.Many2one(
        related="contract_id.currency_id",
        string="Валюта оплати",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_wage = fields.Monetary(
        related="contract_id.wage",
        string="Поточний оклад / тарифна ставка",
        currency_field="l10n_ua_current_currency_id",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_professional_category_id = fields.Many2one(
        related="contract_id.professional_category_id",
        string="Професійна категорія / розряд",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        related="contract_id.l10n_ua_work_type",
        string="Вид роботи",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_hire_condition = fields.Selection(
        HIRE_CONDITION_SELECTION,
        related="contract_id.l10n_ua_hire_condition",
        string="Умова прийняття / зміни умов",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_weekly_hours = fields.Float(
        related="contract_id.l10n_ua_weekly_hours",
        string="Тривалість робочого тижня, год.",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_work_conditions = fields.Text(
        related="contract_id.l10n_ua_work_conditions",
        string="Умови праці",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_allowance_note = fields.Text(
        related="contract_id.l10n_ua_allowance_note",
        string="Надбавки / доплати",
        readonly=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_current_order_id = fields.Many2one(
        related="contract_id.l10n_ua_personnel_order_id",
        string="Поточний наказ-підстава",
        readonly=True,
        groups="hr.group_hr_user",
    )

    def _compute_personnel_counts(self):
        OrderLine = self.env["hr.personnel.order.line"].sudo()
        Event = self.env["hr.personnel.event"].sudo()
        for employee in self:
            lines = OrderLine.search([("employee_id", "=", employee.id)])
            employee.personnel_order_count = len(lines.mapped("order_id"))
            employee.personnel_event_count = Event.search_count(
                [("employee_id", "=", employee.id)]
            )

    def action_view_personnel_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Кадрові накази"),
            "res_model": "hr.personnel.order",
            "view_mode": "list,form",
            "domain": [("line_ids.employee_id", "=", self.id)],
            "context": {"default_company_id": self.company_id.id},
        }

    def action_view_personnel_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Кадрова історія"),
            "res_model": "hr.personnel.event",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"create": False},
        }
