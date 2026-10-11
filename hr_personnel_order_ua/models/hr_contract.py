from odoo import fields, models

from .constants import HIRE_CONDITION_SELECTION, WORK_TYPE_SELECTION


class HrContract(models.Model):
    _inherit = "hr.contract"

    l10n_ua_personnel_order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Остання кадрова дія-підстава",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )
    l10n_ua_personnel_order_id = fields.Many2one(
        related="l10n_ua_personnel_order_line_id.order_id",
        string="Останній кадровий наказ",
        store=True,
        readonly=True,
    )

    l10n_ua_hire_order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Рядок наказу про прийняття",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )
    l10n_ua_hire_order_id = fields.Many2one(
        related="l10n_ua_hire_order_line_id.order_id",
        string="Наказ про прийняття",
        store=True,
        readonly=True,
    )

    l10n_ua_personnel_number = fields.Char(
        string="Табельний номер трудового періоду",
        copy=False,
        tracking=True,
        index=True,
        help=(
            "Табельний номер, який належав працівнику саме в межах "
            "цього трудового періоду. Не змінюється при наступному "
            "повторному прийнятті працівника з іншим табельним номером."
        ),
    )
    l10n_ua_work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="Вид роботи",
        tracking=True,
    )
    l10n_ua_hire_condition = fields.Selection(
        HIRE_CONDITION_SELECTION,
        string="Умова прийняття / зміни умов",
        tracking=True,
    )
    l10n_ua_weekly_hours = fields.Float(
        string="Тривалість робочого тижня, год.",
        tracking=True,
    )
    l10n_ua_work_conditions = fields.Text(
        string="Умови праці",
        tracking=True,
    )
    l10n_ua_allowance_note = fields.Text(
        string="Надбавки / доплати",
        tracking=True,
    )
