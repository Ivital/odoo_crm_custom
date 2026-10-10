from odoo import fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    l10n_ua_personnel_order_line_id = fields.Many2one(
        "hr.personnel.order.line",
        string="Кадрова дія-підстава",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )
    l10n_ua_personnel_order_id = fields.Many2one(
        related="l10n_ua_personnel_order_line_id.order_id",
        string="Кадровий наказ-підстава",
        store=True,
        readonly=True,
    )
    l10n_ua_work_period_from = fields.Date(
        string="Робочий період з",
        readonly=True,
    )
    l10n_ua_work_period_to = fields.Date(
        string="Робочий період по",
        readonly=True,
    )
    l10n_ua_calendar_days = fields.Integer(
        string="Календарні дні за наказом",
        readonly=True,
    )
    l10n_ua_health_assistance = fields.Boolean(
        string="Матеріальна допомога на оздоровлення",
        readonly=True,
    )
