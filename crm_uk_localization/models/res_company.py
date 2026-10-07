import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .company_legal_party import AUTHORITY_BASIS_SELECTION


class ResCompany(models.Model):
    _inherit = "res.company"

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
        help="Індивідуальний податковий номер платника ПДВ. Для української юридичної особи — 12 цифр.",
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
        "res_company_l10n_ua_kved_rel",
        "company_id",
        "kved_id",
        string="Додаткові КВЕД",
    )

    l10n_ua_statutory_capital = fields.Monetary(
        string="Статутний капітал",
        currency_field="currency_id",
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
        "company_id",
        string="Інші уповноважені особи",
        groups="crm_uk_localization.group_ua_company_legal_data_manager",
    )
    l10n_ua_participant_ids = fields.One2many(
        "l10n_ua.company.participant",
        "company_id",
        string="Засновники / учасники",
        groups="crm_uk_localization.group_ua_company_legal_data_manager",
    )
    l10n_ua_beneficial_owner_ids = fields.One2many(
        "l10n_ua.company.beneficial.owner",
        "company_id",
        string="Кінцеві бенефіціарні власники",
        groups="crm_uk_localization.group_ua_company_legal_data_manager",
    )

    @api.constrains("company_registry", "country_id")
    def _check_l10n_ua_company_registry(self):
        for company in self:
            value = (company.company_registry or "").strip()
            if company.country_code == "UA" and value and not re.fullmatch(r"\d{8}", value):
                raise ValidationError(
                    _("Код ЄДРПОУ української юридичної особи має містити рівно 8 цифр.")
                )

    @api.constrains(
        "l10n_ua_vat_registered",
        "l10n_ua_vat_number",
        "l10n_ua_vat_registration_date",
        "l10n_ua_vat_cancellation_date",
    )
    def _check_l10n_ua_vat_data(self):
        for company in self:
            number = (company.l10n_ua_vat_number or "").strip()

            if number and not re.fullmatch(r"\d{12}", number):
                raise ValidationError(
                    _("ІПН платника ПДВ має містити рівно 12 цифр.")
                )

            if company.l10n_ua_vat_registered and not number:
                raise ValidationError(
                    _("Для чинного платника ПДВ необхідно зазначити ІПН платника ПДВ.")
                )

            if company.l10n_ua_vat_registered and company.l10n_ua_vat_cancellation_date:
                raise ValidationError(
                    _("Для чинного платника ПДВ дата анулювання реєстрації має бути порожньою.")
                )

            if (
                company.l10n_ua_vat_registration_date
                and company.l10n_ua_vat_cancellation_date
                and company.l10n_ua_vat_cancellation_date
                < company.l10n_ua_vat_registration_date
            ):
                raise ValidationError(
                    _("Дата анулювання ПДВ не може бути раніше дати реєстрації платником ПДВ.")
                )

    @api.constrains("l10n_ua_main_kved_id", "l10n_ua_kved_ids")
    def _check_l10n_ua_kveds(self):
        for company in self:
            if company.l10n_ua_main_kved_id and company.l10n_ua_main_kved_id in company.l10n_ua_kved_ids:
                raise ValidationError(
                    _("Основний КВЕД не потрібно дублювати у переліку додаткових КВЕД.")
                )

    @api.constrains("l10n_ua_statutory_capital")
    def _check_l10n_ua_statutory_capital(self):
        for company in self:
            if company.l10n_ua_statutory_capital < 0:
                raise ValidationError(_("Статутний капітал не може бути від'ємним."))
