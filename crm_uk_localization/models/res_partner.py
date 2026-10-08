import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .company_legal_party import AUTHORITY_BASIS_SELECTION


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ua_short_name = fields.Char(string="Скорочене найменування")
    l10n_ua_kopfg_id = fields.Many2one(
        "l10n_ua.kopfg",
        string="Організаційно-правова форма (КОПФГ)",
        ondelete="restrict",
    )
    l10n_ua_legal_status = fields.Selection(
        [
            ("active", "Діюча"),
            ("terminating", "У стані припинення"),
            ("terminated", "Припинена"),
        ],
        string="Статус юридичної особи",
        default="active",
    )
    l10n_ua_registration_date = fields.Date(string="Дата державної реєстрації")
    l10n_ua_edr_record_number = fields.Char(string="Номер запису в ЄДР")
    l10n_ua_last_registration_action_date = fields.Date(
        string="Дата останньої реєстраційної дії"
    )

    l10n_ua_tax_system = fields.Selection(
        [
            ("general", "Загальна система"),
            ("simplified", "Спрощена система"),
            ("nonprofit", "Неприбуткова організація"),
            ("other", "Інше"),
        ],
        string="Система оподаткування",
    )
    l10n_ua_single_tax_group = fields.Selection(
        [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")],
        string="Група єдиного податку",
    )
    l10n_ua_single_tax_rate = fields.Float(
        string="Ставка єдиного податку, %",
        digits=(5, 2),
    )
    l10n_ua_tax_authority = fields.Char(string="Контролюючий орган")

    l10n_ua_vat_registered = fields.Boolean(string="Платник ПДВ")
    l10n_ua_vat_number = fields.Char(
        string="ІПН платника ПДВ",
        help=(
            "Індивідуальний податковий номер платника ПДВ. "
            "Для української юридичної особи — 12 цифр."
        ),
    )
    l10n_ua_vat_registration_date = fields.Date(
        string="Дата реєстрації платником ПДВ"
    )
    l10n_ua_vat_cancellation_date = fields.Date(
        string="Дата анулювання реєстрації ПДВ"
    )

    l10n_ua_main_kved_id = fields.Many2one(
        "l10n_ua.kved",
        string="Основний КВЕД",
        ondelete="restrict",
    )
    l10n_ua_kved_ids = fields.Many2many(
        "l10n_ua.kved",
        "res_partner_l10n_ua_kved_rel",
        "partner_id",
        "kved_id",
        string="Додаткові КВЕД",
    )

    l10n_ua_currency_id = fields.Many2one(
        "res.currency",
        string="Валюта юридичних даних",
        default=lambda self: self.env.company.currency_id,
    )
    l10n_ua_statutory_capital = fields.Monetary(
        string="Статутний капітал",
        currency_field="l10n_ua_currency_id",
    )

    l10n_ua_manager_partner_id = fields.Many2one(
        "res.partner",
        string="Керівник",
        ondelete="restrict",
    )
    l10n_ua_manager_position = fields.Char(string="Посада керівника")
    l10n_ua_manager_appointment_date = fields.Date(string="Дата призначення")
    l10n_ua_manager_authority_basis = fields.Selection(
        AUTHORITY_BASIS_SELECTION,
        string="Діє на підставі",
    )
    l10n_ua_manager_authority_basis_note = fields.Char(
        string="Уточнення підстави"
    )
    l10n_ua_representation_restrictions = fields.Text(
        string="Обмеження представництва"
    )

    l10n_ua_authorized_person_ids = fields.One2many(
        "l10n_ua.company.authorized.person",
        "legal_entity_id",
        string="Інші уповноважені особи",
        groups="crm_uk_localization.group_ua_company_legal_data_manager",
    )
    l10n_ua_participant_ids = fields.One2many(
        "l10n_ua.company.participant",
        "legal_entity_id",
        string="Засновники / учасники",
        groups="crm_uk_localization.group_ua_company_legal_data_manager",
    )
    l10n_ua_beneficial_owner_ids = fields.One2many(
        "l10n_ua.company.beneficial.owner",
        "legal_entity_id",
        string="Кінцеві бенефіціарні власники",
        groups="crm_uk_localization.group_ua_company_legal_data_manager",
    )

    @api.constrains("company_registry", "country_id", "is_company")
    def _check_l10n_ua_company_registry(self):
        for partner in self:
            value = (partner.company_registry or "").strip()
            if (
                partner.is_company
                and partner.country_id.code == "UA"
                and value
                and not re.fullmatch(r"\d{8}", value)
            ):
                raise ValidationError(
                    _(
                        "Код ЄДРПОУ української юридичної особи "
                        "має містити рівно 8 цифр."
                    )
                )

    @api.constrains(
        "l10n_ua_vat_registered",
        "l10n_ua_vat_number",
        "l10n_ua_vat_registration_date",
        "l10n_ua_vat_cancellation_date",
        "country_id",
        "is_company",
    )
    def _check_l10n_ua_vat_data(self):
        for partner in self:
            if not partner.is_company:
                continue

            number = (partner.l10n_ua_vat_number or "").strip()
            is_ua = partner.country_id.code == "UA"

            if is_ua and number and not re.fullmatch(r"\d{12}", number):
                raise ValidationError(
                    _("ІПН платника ПДВ має містити рівно 12 цифр.")
                )

            if partner.l10n_ua_vat_registered and not number:
                raise ValidationError(
                    _(
                        "Для чинного платника ПДВ необхідно зазначити "
                        "ІПН платника ПДВ."
                    )
                )

            if (
                partner.l10n_ua_vat_registered
                and partner.l10n_ua_vat_cancellation_date
            ):
                raise ValidationError(
                    _(
                        "Для чинного платника ПДВ дата анулювання "
                        "реєстрації має бути порожньою."
                    )
                )

            if (
                partner.l10n_ua_vat_registration_date
                and partner.l10n_ua_vat_cancellation_date
                and partner.l10n_ua_vat_cancellation_date
                < partner.l10n_ua_vat_registration_date
            ):
                raise ValidationError(
                    _(
                        "Дата анулювання ПДВ не може бути раніше "
                        "дати реєстрації платником ПДВ."
                    )
                )

    @api.constrains("l10n_ua_main_kved_id", "l10n_ua_kved_ids")
    def _check_l10n_ua_kveds(self):
        for partner in self:
            if (
                partner.l10n_ua_main_kved_id
                and partner.l10n_ua_main_kved_id in partner.l10n_ua_kved_ids
            ):
                raise ValidationError(
                    _(
                        "Основний КВЕД не потрібно дублювати "
                        "у переліку додаткових КВЕД."
                    )
                )

    @api.constrains("l10n_ua_statutory_capital")
    def _check_l10n_ua_statutory_capital(self):
        for partner in self:
            if partner.l10n_ua_statutory_capital < 0:
                raise ValidationError(
                    _("Статутний капітал не може бути від'ємним.")
                )
