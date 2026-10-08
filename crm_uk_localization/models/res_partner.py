import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .company_legal_party import AUTHORITY_BASIS_SELECTION
from .legal_reference import KVED_CLASSIFIER_SELECTION


SYNC_CONTEXT_KEY = "l10n_ua_skip_employee_partner_sync"
IDENTITY_PARTNER_TO_EMPLOYEE = {
    "name": "name",
    "image_1920": "image_1920",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    company_type = fields.Selection(
        selection=[
            ("person", "Фізична особа"),
            ("company", "Юридична особа"),
        ],
        string="Тип особи",
    )

    l10n_ua_is_fop = fields.Boolean(
        string="Фізична особа-підприємець (ФОП)",
        index=True,
        help=(
            "Ознака підприємницького статусу фізичної особи. "
            "ФОП залишається фізичною особою і не є юридичною особою."
        ),
    )

    l10n_ua_short_name = fields.Char(string="Скорочене найменування")
    l10n_ua_kopfg_id = fields.Many2one(
        "l10n_ua.kopfg",
        string="Організаційно-правова форма (КОПФГ)",
        ondelete="restrict",
        domain=[("selectable", "=", True), ("active", "=", True)],
    )
    l10n_ua_legal_status = fields.Selection(
        [
            ("active", "Діюча / ФОП зареєстрований"),
            ("terminating", "У стані припинення"),
            ("terminated", "Припинена / ФОП припинено"),
        ],
        string="Реєстраційний статус",
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
        help="Індивідуальний податковий номер платника ПДВ — 12 цифр.",
    )
    l10n_ua_vat_registration_date = fields.Date(
        string="Дата реєстрації платником ПДВ"
    )
    l10n_ua_vat_cancellation_date = fields.Date(
        string="Дата анулювання реєстрації ПДВ"
    )

    l10n_ua_activity_classifier = fields.Selection(
        KVED_CLASSIFIER_SELECTION,
        string="Версія класифікатора видів діяльності",
        default="kved_2010",
        required=True,
    )
    l10n_ua_main_kved_id = fields.Many2one(
        "l10n_ua.kved",
        string="Основний вид діяльності",
        ondelete="restrict",
    )
    l10n_ua_kved_ids = fields.Many2many(
        "l10n_ua.kved",
        "res_partner_l10n_ua_kved_rel",
        "partner_id",
        "kved_id",
        string="Додаткові види діяльності",
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

    # Особисті HR-дані зберігаються на контакті, а не дублюються в hr.employee.
    # Стандартні partner.email/mobile лишаються робочими контактами працівника.
    l10n_ua_private_street = fields.Char(
        string="Домашня адреса: вулиця",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_street2 = fields.Char(
        string="Домашня адреса: рядок 2",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_city = fields.Char(
        string="Домашня адреса: населений пункт",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_state_id = fields.Many2one(
        "res.country.state",
        string="Домашня адреса: область",
        ondelete="restrict",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_zip = fields.Char(
        string="Домашня адреса: індекс",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_country_id = fields.Many2one(
        "res.country",
        string="Домашня адреса: країна",
        ondelete="restrict",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_phone = fields.Char(
        string="Особистий телефон",
        groups="hr.group_hr_user",
    )
    l10n_ua_private_email = fields.Char(
        string="Особистий email",
        groups="hr.group_hr_user",
    )

    l10n_ua_rnokpp = fields.Char(
        string="РНОКПП",
        compute="_compute_l10n_ua_rnokpp",
        inverse="_inverse_l10n_ua_rnokpp",
        search="_search_l10n_ua_rnokpp",
        groups=(
            "hr.group_hr_user,"
            "crm_uk_localization.group_ua_company_legal_data_manager"
        ),
    )
    l10n_ua_passport_number = fields.Char(
        string="Паспорт / документ, що посвідчує особу",
        compute="_compute_l10n_ua_passport_number",
        inverse="_inverse_l10n_ua_passport_number",
        search="_search_l10n_ua_passport_number",
        groups="hr.group_hr_user",
    )

    @api.depends(
        "id_numbers",
        "id_numbers.name",
        "id_numbers.category_id",
        "id_numbers.active",
        "id_numbers.status",
    )
    def _compute_l10n_ua_rnokpp(self):
        self._compute_identification("l10n_ua_rnokpp", "ua_rnokpp")

    def _l10n_ua_inverse_identification_sudo(self, field_name, category_code):
        """Write protected Ukrainian identifiers without granting broad ID ACLs."""
        Category = self.env["res.partner.id_category"].sudo()
        IdNumber = self.env["res.partner.id_number"].sudo()
        category = Category.search([("code", "=", category_code)], limit=1)
        if not category:
            raise ValidationError(
                _("Не знайдено категорію ідентифікатора: %s") % category_code
            )

        for partner in self:
            value = (partner[field_name] or "").strip()
            existing = IdNumber.search(
                [
                    ("partner_id", "=", partner.id),
                    ("category_id", "=", category.id),
                    ("active", "=", True),
                    ("status", "!=", "close"),
                ]
            )
            if len(existing) > 1:
                raise ValidationError(
                    _(
                        "Для контакту знайдено кілька активних "
                        "ідентифікаторів одного типу."
                    )
                )
            if existing:
                if value:
                    existing.name = value
                else:
                    existing.active = False
            elif value:
                IdNumber.create(
                    {
                        "partner_id": partner.id,
                        "category_id": category.id,
                        "name": value,
                        "status": "open",
                    }
                )

    def _inverse_l10n_ua_rnokpp(self):
        self._l10n_ua_inverse_identification_sudo(
            "l10n_ua_rnokpp", "ua_rnokpp"
        )

    def _search_l10n_ua_rnokpp(self, operator, value):
        return self._search_identification("ua_rnokpp", operator, value)

    @api.depends(
        "id_numbers",
        "id_numbers.name",
        "id_numbers.category_id",
        "id_numbers.active",
        "id_numbers.status",
    )
    def _compute_l10n_ua_passport_number(self):
        self._compute_identification("l10n_ua_passport_number", "ua_passport")

    def _inverse_l10n_ua_passport_number(self):
        self._l10n_ua_inverse_identification_sudo(
            "l10n_ua_passport_number", "ua_passport"
        )

    def _search_l10n_ua_passport_number(self, operator, value):
        return self._search_identification("ua_passport", operator, value)

    @api.model
    def _l10n_ua_fop_kopfg(self):
        return self.env["l10n_ua.kopfg"].search(
            [("code", "=", "910")],
            limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        fop_kopfg = self._l10n_ua_fop_kopfg()
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            is_legal = vals.get("company_type") == "company" or bool(
                vals.get("is_company")
            )
            is_fop = bool(vals.get("l10n_ua_is_fop")) and not is_legal
            if is_legal:
                vals["l10n_ua_is_fop"] = False
            elif is_fop:
                vals["is_company"] = False
                if fop_kopfg:
                    vals["l10n_ua_kopfg_id"] = fop_kopfg.id
            if (is_legal or is_fop) and not vals.get("l10n_ua_legal_status"):
                vals["l10n_ua_legal_status"] = "active"
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        # Subject type changes need per-record normalization because the same
        # write may be called on a multi-record set with different old states.
        subject_keys = {"company_type", "is_company", "l10n_ua_is_fop"}
        if len(self) > 1 and subject_keys.intersection(vals):
            result = True
            for partner in self:
                result = partner.write(vals) and result
            return result

        vals = dict(vals)
        if len(self) == 1 and subject_keys.intersection(vals):
            partner = self
            if "company_type" in vals:
                target_is_company = vals["company_type"] == "company"
            else:
                target_is_company = bool(vals.get("is_company", partner.is_company))
            target_is_fop = bool(
                vals.get("l10n_ua_is_fop", partner.l10n_ua_is_fop)
            ) and not target_is_company

            if target_is_company:
                vals["l10n_ua_is_fop"] = False
                if (
                    "l10n_ua_kopfg_id" not in vals
                    and partner.l10n_ua_kopfg_id.code == "910"
                ):
                    vals["l10n_ua_kopfg_id"] = False
                if not vals.get("l10n_ua_legal_status") and not partner.l10n_ua_legal_status:
                    vals["l10n_ua_legal_status"] = "active"
            elif target_is_fop:
                vals["is_company"] = False
                fop_kopfg = self._l10n_ua_fop_kopfg()
                if fop_kopfg:
                    vals["l10n_ua_kopfg_id"] = fop_kopfg.id
                if not vals.get("l10n_ua_legal_status") and not partner.l10n_ua_legal_status:
                    vals["l10n_ua_legal_status"] = "active"
            else:
                # A plain physical person must not keep business-only
                # classifier links that would be hidden and inconsistent.
                vals.setdefault("l10n_ua_kopfg_id", False)
                vals.setdefault("l10n_ua_main_kved_id", False)
                vals.setdefault("l10n_ua_kved_ids", [(5, 0, 0)])
                vals.setdefault("l10n_ua_legal_status", False)

        result = super().write(vals)

        if not self.env.context.get(SYNC_CONTEXT_KEY):
            identity_values = {
                employee_field: vals[partner_field]
                for partner_field, employee_field in IDENTITY_PARTNER_TO_EMPLOYEE.items()
                if partner_field in vals
            }
            if identity_values:
                for partner in self:
                    employees = partner.sudo().employee_ids
                    if employees:
                        employees.with_context(**{SYNC_CONTEXT_KEY: True}).write(
                            identity_values
                        )
        return result

    @api.onchange("l10n_ua_is_fop")
    def _onchange_l10n_ua_is_fop(self):
        if self.l10n_ua_is_fop:
            self.is_company = False
            fop_kopfg = self._l10n_ua_fop_kopfg()
            if fop_kopfg:
                self.l10n_ua_kopfg_id = fop_kopfg
            if not self.l10n_ua_legal_status:
                self.l10n_ua_legal_status = "active"
        elif not self.is_company:
            self.l10n_ua_kopfg_id = False
            self.l10n_ua_main_kved_id = False
            self.l10n_ua_kved_ids = False
            self.l10n_ua_legal_status = False

    @api.onchange("l10n_ua_activity_classifier")
    def _onchange_l10n_ua_activity_classifier(self):
        self.l10n_ua_main_kved_id = False
        self.l10n_ua_kved_ids = False

    @api.constrains("l10n_ua_is_fop", "is_company")
    def _check_l10n_ua_subject_type(self):
        for partner in self:
            if partner.is_company and partner.l10n_ua_is_fop:
                raise ValidationError(
                    _("ФОП є фізичною особою і не може одночасно бути юридичною особою.")
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

    @api.constrains("l10n_ua_kopfg_id", "is_company", "l10n_ua_is_fop")
    def _check_l10n_ua_kopfg_subject(self):
        for partner in self:
            kopfg = partner.l10n_ua_kopfg_id
            if not kopfg:
                continue
            if partner.l10n_ua_is_fop and kopfg.code != "910":
                raise ValidationError(_("Для ФОП КОПФГ має бути 910."))
            if partner.is_company and kopfg.code == "910":
                raise ValidationError(
                    _("КОПФГ 910 призначений для фізичної особи-підприємця.")
                )
            if not partner.is_company and not partner.l10n_ua_is_fop:
                raise ValidationError(
                    _("КОПФГ застосовується до юридичних осіб і ФОП.")
                )

    @api.constrains(
        "l10n_ua_vat_registered",
        "l10n_ua_vat_number",
        "l10n_ua_vat_registration_date",
        "l10n_ua_vat_cancellation_date",
        "country_id",
        "is_company",
        "l10n_ua_is_fop",
    )
    def _check_l10n_ua_vat_data(self):
        for partner in self:
            if not (partner.is_company or partner.l10n_ua_is_fop):
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

    @api.constrains(
        "l10n_ua_activity_classifier",
        "l10n_ua_main_kved_id",
        "l10n_ua_kved_ids",
        "is_company",
        "l10n_ua_is_fop",
    )
    def _check_l10n_ua_kveds(self):
        for partner in self:
            main = partner.l10n_ua_main_kved_id
            additional = partner.l10n_ua_kved_ids
            if (main or additional) and not (
                partner.is_company or partner.l10n_ua_is_fop
            ):
                raise ValidationError(
                    _(
                        "Види економічної діяльності застосовуються "
                        "до юридичних осіб і ФОП."
                    )
                )
            if main and main in additional:
                raise ValidationError(
                    _(
                        "Основний вид діяльності не потрібно дублювати "
                        "у переліку додаткових."
                    )
                )
            for kved in main | additional:
                if not kved.selectable:
                    raise ValidationError(
                        _("Можна призначати лише позиції, дозволені для вибору.")
                    )
                if kved.classifier != partner.l10n_ua_activity_classifier:
                    raise ValidationError(
                        _(
                            "Усі види діяльності мають належати "
                            "до вибраної версії класифікатора."
                        )
                    )

    @api.constrains("l10n_ua_statutory_capital")
    def _check_l10n_ua_statutory_capital(self):
        for partner in self:
            if partner.l10n_ua_statutory_capital < 0:
                raise ValidationError(_("Статутний капітал не може бути від'ємним."))
