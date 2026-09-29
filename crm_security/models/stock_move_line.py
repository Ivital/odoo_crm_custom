from odoo import api, models
from odoo.exceptions import AccessError


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _crm_security_check_auditor_write(self):
        user = self.env.user

        if (
            user.has_group("crm_security.group_auditor")
            and not user.has_group("stock.group_stock_user")
        ):
            raise AccessError(
                "Auditor has read-only access to stock move lines."
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._crm_security_check_auditor_write()
        return super().create(vals_list)

    def write(self, vals):
        self._crm_security_check_auditor_write()
        return super().write(vals)

    def unlink(self):
        self._crm_security_check_auditor_write()
        return super().unlink()
