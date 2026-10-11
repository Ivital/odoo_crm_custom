from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .constants import ENGINE_CONTEXT_KEY


class HrPersonnelEmploymentPeriod(models.Model):
    _name = "hr.personnel.employment.period"
    _description = "Фактичний трудовий період"
    _order = "date_start asc, first_observed_date asc, id asc"
    _rec_name = "name"

    name = fields.Char(
        string="Трудовий період",
        compute="_compute_name",
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Працівник",
        required=True,
        ondelete="restrict",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Підприємство",
        required=True,
        ondelete="restrict",
        index=True,
    )

    date_start = fields.Date(
        string="Дата початку",
        index=True,
        help=(
            "Фактична дата початку трудового періоду, "
            "якщо вона підтверджена джерелом. "
            "Порожнє значення означає, що початок "
            "ще не встановлено."
        ),
    )

    date_end = fields.Date(
        string="Дата завершення",
        index=True,
        help=(
            "Фактична дата завершення трудового періоду, "
            "якщо вона підтверджена джерелом. "
            "Порожнє значення не означає, що працівник "
            "працює зараз: дата може бути просто невідомою."
        ),
    )

    first_observed_date = fields.Date(
        string="Перша відома дата у джерелах",
        required=True,
        index=True,
        help=(
            "Найперша дата кадрового факту, з якого було "
            "створено цей історичний трудовий період. "
            "Не підміняє невідому дату прийняття."
        ),
    )

    personnel_number = fields.Char(
        string="Табельний номер трудового періоду",
        index=True,
        help=(
            "Табельний номер, підтверджений для цього "
            "трудового періоду. Якщо джерело його не містить, "
            "значення залишається порожнім."
        ),
    )

    origin_order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Перший відомий кадровий факт",
        required=True,
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )

    start_order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Джерело дати початку",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )

    end_order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Джерело дати завершення",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )

    start_known = fields.Boolean(
        string="Дата початку підтверджена",
        compute="_compute_boundary_state",
    )

    end_known = fields.Boolean(
        string="Дата завершення підтверджена",
        compute="_compute_boundary_state",
    )

    boundary_state = fields.Selection(
        [
            ("known", "Початок і завершення відомі"),
            ("end_unknown", "Дата завершення не встановлена"),
            ("start_unknown", "Дата початку не встановлена"),
            ("both_unknown", "Межі періоду не встановлені"),
        ],
        string="Стан меж періоду",
        compute="_compute_boundary_state",
    )

    _sql_constraints = [
        (
            "origin_order_line_unique",
            "unique(origin_order_line_id)",
            (
                "Для одного джерельного кадрового факту "
                "може бути створено лише один трудовий період."
            ),
        ),
        (
            "date_range_valid",
            (
                "CHECK("
                "date_start IS NULL "
                "OR date_end IS NULL "
                "OR date_end >= date_start"
                ")"
            ),
            "Дата завершення не може передувати даті початку.",
        ),
    ]

    @api.depends(
        "employee_id.name",
        "date_start",
        "date_end",
        "first_observed_date",
    )
    def _compute_name(self):
        for period in self:
            start = (
                fields.Date.to_string(period.date_start)
                if period.date_start
                else "?"
            )

            end = (
                fields.Date.to_string(period.date_end)
                if period.date_end
                else "?"
            )

            period.name = (
                f"{period.employee_id.name or ''}: "
                f"{start} — {end}"
            )

    @api.depends("date_start", "date_end")
    def _compute_boundary_state(self):
        for period in self:
            period.start_known = bool(
                period.date_start
            )

            period.end_known = bool(
                period.date_end
            )

            if (
                period.date_start
                and period.date_end
            ):
                period.boundary_state = "known"

            elif period.date_start:
                period.boundary_state = (
                    "end_unknown"
                )

            elif period.date_end:
                period.boundary_state = (
                    "start_unknown"
                )

            else:
                period.boundary_state = (
                    "both_unknown"
                )

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for period in self:
            if (
                period.date_start
                and period.date_end
                and period.date_end
                < period.date_start
            ):
                raise ValidationError(
                    _(
                        "Дата завершення трудового періоду "
                        "не може передувати даті початку."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(
            ENGINE_CONTEXT_KEY
        ):
            raise UserError(
                _(
                    "Фактичні трудові періоди створюються "
                    "лише кадровим механізмом."
                )
            )

        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(
            ENGINE_CONTEXT_KEY
        ):
            raise UserError(
                _(
                    "Фактичний трудовий період не можна "
                    "редагувати вручну."
                )
            )

        return super().write(vals)

    def unlink(self):
        if not self.env.context.get(
            ENGINE_CONTEXT_KEY
        ):
            raise UserError(
                _(
                    "Фактичні трудові періоди "
                    "не можна видаляти вручну."
                )
            )

        return super().unlink()


class HrPersonnelOrderLineEmploymentPeriod(models.Model):
    _inherit = "hr.personnel.order.line"

    employment_period_id = fields.Many2one(
        "hr.personnel.employment.period",
        string="Фактичний трудовий період",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )


class HrPersonnelEventEmploymentPeriod(models.Model):
    _inherit = "hr.personnel.event"

    employment_period_id = fields.Many2one(
        "hr.personnel.employment.period",
        string="Фактичний трудовий період",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
