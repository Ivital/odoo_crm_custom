from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .constants import ENGINE_CONTEXT_KEY, ORDER_TYPE_SELECTION


class HrPersonnelOrder(models.Model):
    _name = "hr.personnel.order"
    _description = "Кадровий наказ"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "order_date desc, id desc"
    _rec_name = "number"

    number = fields.Char(
        string="Номер наказу",
        required=True,
        copy=False,
        default=lambda self: _("Новий"),
        tracking=True,
        index=True,
    )
    order_date = fields.Date(
        string="Дата наказу",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    order_type = fields.Selection(
        ORDER_TYPE_SELECTION,
        string="Тип наказу",
        required=True,
        tracking=True,
        index=True,
    )
    subject = fields.Char(string="Заголовок", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Підприємство",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        index=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Відповідальний кадровик",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        domain="[('share', '=', False)]",
    )
    signer_id = fields.Many2one(
        "hr.employee",
        string="Підписант",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    basis = fields.Text(string="Підстава", tracking=True)
    note = fields.Text(string="Примітки", tracking=True)
    cancellation_reason = fields.Text(string="Причина скасування", tracking=True)

    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("submitted", "На погодженні"),
            ("approved", "Погоджено"),
            ("signed", "Підписано"),
            ("posted", "Проведено"),
            ("cancelled", "Скасовано"),
        ],
        string="Статус",
        required=True,
        default="draft",
        copy=False,
        tracking=True,
        index=True,
    )

    line_ids = fields.One2many(
        "hr.personnel.order.line",
        "order_id",
        string="Працівники / кадрові дії",
        copy=True,
    )
    event_ids = fields.One2many(
        "hr.personnel.event",
        "order_id",
        string="Кадрові події",
        readonly=True,
    )
    line_count = fields.Integer(string="Кількість рядків", compute="_compute_counts")
    event_count = fields.Integer(string="Кількість подій", compute="_compute_counts")
    pending_line_count = fields.Integer(string="Очікує застосування", compute="_compute_counts")
    failed_line_count = fields.Integer(string="Помилки застосування", compute="_compute_counts")

    submitted_at = fields.Datetime(string="Передано на погодження", readonly=True, copy=False)
    submitted_by_id = fields.Many2one("res.users", string="Передав", readonly=True, copy=False)
    approved_at = fields.Datetime(string="Погоджено", readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", string="Погодив", readonly=True, copy=False)
    signed_at = fields.Datetime(string="Підписано", readonly=True, copy=False)
    signed_by_id = fields.Many2one("res.users", string="Позначив підписаним", readonly=True, copy=False)
    posted_at = fields.Datetime(string="Проведено", readonly=True, copy=False)
    posted_by_id = fields.Many2one("res.users", string="Провів", readonly=True, copy=False)
    cancelled_at = fields.Datetime(string="Скасовано", readonly=True, copy=False)
    cancelled_by_id = fields.Many2one("res.users", string="Скасував", readonly=True, copy=False)

    _sql_constraints = [
        (
            "number_company_unique",
            "unique(number, company_id)",
            "Номер кадрового наказу має бути унікальним у межах підприємства.",
        ),
    ]

    @api.depends(
        "line_ids",
        "line_ids.application_state",
        "line_ids.application_error",
        "event_ids",
    )
    def _compute_counts(self):
        for order in self:
            order.line_count = len(order.line_ids)
            order.event_count = len(order.event_ids)
            order.pending_line_count = len(
                order.line_ids.filtered(lambda line: line.application_state == "pending")
            )
            order.failed_line_count = len(order.line_ids.filtered("application_error"))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("number", _("Новий")) == _("Новий"):
                vals["number"] = sequence.next_by_code("hr.personnel.order") or _("Новий")
        return super().create(vals_list)

    def _ensure_state(self, allowed_states):
        invalid = self.filtered(lambda order: order.state not in allowed_states)
        if invalid:
            raise UserError(
                _("Операція недоступна для наказу у статусі: %s")
                % ", ".join(invalid.mapped("state"))
            )

    def _ensure_has_lines(self):
        if self.filtered(lambda order: not order.line_ids):
            raise ValidationError(_("Кадровий наказ повинен містити хоча б один рядок."))

    def action_submit(self):
        self._ensure_state({"draft"})
        self._ensure_has_lines()
        self.mapped("line_ids")._validate_for_post()
        self.write({
            "state": "submitted",
            "submitted_at": fields.Datetime.now(),
            "submitted_by_id": self.env.user.id,
        })
        return True

    def action_approve(self):
        self._ensure_state({"submitted"})
        self.write({
            "state": "approved",
            "approved_at": fields.Datetime.now(),
            "approved_by_id": self.env.user.id,
        })
        return True

    def action_sign(self):
        self._ensure_state({"approved"})
        self.write({
            "state": "signed",
            "signed_at": fields.Datetime.now(),
            "signed_by_id": self.env.user.id,
        })
        return True

    def action_post(self):
        """Post the legal order and apply all actions that are already effective."""
        self._ensure_state({"signed"})
        self._ensure_has_lines()
        self.mapped("line_ids")._validate_for_post()

        now = fields.Datetime.now()
        self.write({
            "state": "posted",
            "posted_at": now,
            "posted_by_id": self.env.user.id,
        })

        today = fields.Date.context_today(self)
        for order in self:
            for line in order.line_ids.sorted(lambda item: (item.sequence, item.id)):
                engine_line = line.with_context(**{ENGINE_CONTEXT_KEY: True})
                if line.order_type == "leave" or line.effective_date <= today:
                    engine_line._apply_from_order()
                else:
                    engine_line._ensure_planned_event()
        return True

    def action_retry_pending(self):
        self._ensure_state({"posted"})
        today = fields.Date.context_today(self)
        for order in self:
            due = order.line_ids.filtered(
                lambda line: line.application_state == "pending"
                and (line.order_type == "leave" or line.effective_date <= today)
            )
            for line in due.sorted(lambda item: (item.effective_date, item.sequence, item.id)):
                line.with_context(**{ENGINE_CONTEXT_KEY: True})._apply_from_order()
        return True

    def action_cancel(self):
        self._ensure_state({"draft", "submitted", "approved", "signed"})
        self.write({
            "state": "cancelled",
            "cancelled_at": fields.Datetime.now(),
            "cancelled_by_id": self.env.user.id,
        })
        return True

    def action_reset_to_draft(self):
        self._ensure_state({"cancelled"})
        self.write({
            "state": "draft",
            "submitted_at": False,
            "submitted_by_id": False,
            "approved_at": False,
            "approved_by_id": False,
            "signed_at": False,
            "signed_by_id": False,
            "cancelled_at": False,
            "cancelled_by_id": False,
        })
        return True

    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Кадрові події"),
            "res_model": "hr.personnel.event",
            "view_mode": "list,form",
            "domain": [("order_id", "=", self.id)],
            "context": {"create": False},
        }

    def unlink(self):
        if self.filtered(lambda order: order.state != "draft"):
            raise UserError(_("Видаляти можна лише кадрові накази у статусі «Чернетка»."))
        return super().unlink()

    def write(self, vals):
        locked_fields = {
            "number", "order_date", "order_type", "subject", "company_id",
            "responsible_user_id", "signer_id", "basis", "note", "line_ids",
        }
        if locked_fields.intersection(vals):
            if self.filtered(lambda order: order.state in {"posted", "cancelled"}):
                raise UserError(
                    _("Проведений або скасований кадровий наказ не можна змінювати.")
                )
        return super().write(vals)
