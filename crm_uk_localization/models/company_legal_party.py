from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


AUTHORITY_BASIS_SELECTION = [
    ("statute", "Статут"),
    ("order", "Наказ"),
    ("power_of_attorney", "Довіреність"),
    ("other", "Інше"),
]


class L10nUaCompanyAuthorizedPerson(models.Model):
    _name = "l10n_ua.company.authorized.person"
    _description = "Уповноважена особа підприємства"
    _order = "date_from desc, id desc"

    company_id = fields.Many2one(
        "res.company",
        string="Підприємство",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Особа",
        required=True,
        ondelete="restrict",
    )
    position = fields.Char(string="Посада")
    authority_basis = fields.Selection(
        AUTHORITY_BASIS_SELECTION,
        string="Діє на підставі",
    )
    authority_basis_note = fields.Char(string="Уточнення підстави")
    date_from = fields.Date(string="Повноваження з")
    date_to = fields.Date(string="Повноваження до")
    representation_restrictions = fields.Text(string="Обмеження представництва")
    active = fields.Boolean(default=True)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(_("Дата завершення повноважень не може бути раніше дати початку."))


class L10nUaCompanyParticipant(models.Model):
    _name = "l10n_ua.company.participant"
    _description = "Засновник або учасник підприємства"
    _order = "ownership_share desc, id"

    company_id = fields.Many2one(
        "res.company",
        string="Підприємство",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Засновник / учасник",
        required=True,
        ondelete="restrict",
    )
    ownership_share = fields.Float(string="Частка, %", digits=(5, 2))
    contribution_amount = fields.Monetary(
        string="Внесок до статутного капіталу",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    date_from = fields.Date(string="Участь з")
    date_to = fields.Date(string="Участь до")
    active = fields.Boolean(default=True)

    @api.constrains("ownership_share")
    def _check_ownership_share(self):
        for record in self:
            if record.ownership_share < 0 or record.ownership_share > 100:
                raise ValidationError(_("Частка учасника має бути в межах від 0 до 100 %."))

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(_("Дата завершення участі не може бути раніше дати початку."))


class L10nUaCompanyBeneficialOwner(models.Model):
    _name = "l10n_ua.company.beneficial.owner"
    _description = "Кінцевий бенефіціарний власник підприємства"
    _order = "ownership_share desc, id"

    company_id = fields.Many2one(
        "res.company",
        string="Підприємство",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Кінцевий бенефіціар",
        required=True,
        ondelete="restrict",
    )
    ownership_share = fields.Float(string="Частка володіння, %", digits=(5, 2))
    control_type = fields.Selection(
        [
            ("direct", "Прямий вирішальний вплив"),
            ("indirect", "Непрямий вирішальний вплив"),
            ("other", "Інший характер контролю"),
        ],
        string="Характер контролю",
    )
    control_description = fields.Text(string="Опис контролю")
    date_from = fields.Date(string="Контроль з")
    date_to = fields.Date(string="Контроль до")
    active = fields.Boolean(default=True)

    @api.constrains("ownership_share")
    def _check_ownership_share(self):
        for record in self:
            if record.ownership_share < 0 or record.ownership_share > 100:
                raise ValidationError(_("Частка бенефіціара має бути в межах від 0 до 100 %."))

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(_("Дата завершення контролю не може бути раніше дати початку."))
