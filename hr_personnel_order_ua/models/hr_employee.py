from odoo import _, fields, models


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
            "context": {
                "default_company_id": self.company_id.id,
            },
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
