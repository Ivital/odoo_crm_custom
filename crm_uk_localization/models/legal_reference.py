from odoo import api, fields, models


class L10nUaKved(models.Model):
    _name = "l10n_ua.kved"
    _description = "КВЕД України"
    _order = "code"

    code = fields.Char(string="Код", required=True, index=True)
    name = fields.Char(string="Назва", required=True, translate=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Код КВЕД має бути унікальним."),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} — {record.name}"


class L10nUaKopfg(models.Model):
    _name = "l10n_ua.kopfg"
    _description = "КОПФГ України"
    _order = "code"

    code = fields.Char(string="Код", required=True, index=True)
    name = fields.Char(string="Назва", required=True, translate=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Код КОПФГ має бути унікальним."),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} — {record.name}"
