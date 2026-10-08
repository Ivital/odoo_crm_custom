from odoo import api, fields, models


MARITAL_SELECTION = [
    ("single", "Неодружений / незаміжня"),
    ("married", "Одружений / заміжня"),
    ("cohabitant", "Цивільний шлюб"),
    ("widower", "Вдівець / вдова"),
    ("divorced", "Розлучений / розлучена"),
]

CERTIFICATE_SELECTION = [
    ("graduate", "Середня / професійна освіта"),
    ("bachelor", "Бакалавр"),
    ("master", "Магістр"),
    ("doctor", "Доктор"),
    ("other", "Інше"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ua_marital = fields.Selection(
        MARITAL_SELECTION,
        string="Сімейний стан",
        default="single",
        groups="hr.group_hr_user",
    )
    l10n_ua_spouse_complete_name = fields.Char(
        string="ПІБ чоловіка / дружини",
        groups="hr.group_hr_user",
    )
    l10n_ua_spouse_birthdate = fields.Date(
        string="Дата народження чоловіка / дружини",
        groups="hr.group_hr_user",
    )
    l10n_ua_children = fields.Integer(
        string="Кількість дітей на утриманні",
        groups="hr.group_hr_user",
    )
    l10n_ua_ssnid = fields.Char(
        string="Номер соціального страхування",
        groups="hr.group_hr_user",
    )
    l10n_ua_sinid = fields.Char(
        string="Номер соціального забезпечення",
        groups="hr.group_hr_user",
    )
    l10n_ua_permit_no = fields.Char(
        string="Дозвіл на роботу",
        groups="hr.group_hr_user",
    )
    l10n_ua_visa_no = fields.Char(
        string="Номер візи",
        groups="hr.group_hr_user",
    )
    l10n_ua_visa_expire = fields.Date(
        string="Строк дії візи",
        groups="hr.group_hr_user",
    )
    l10n_ua_work_permit_expiration_date = fields.Date(
        string="Строк дії дозволу на роботу",
        groups="hr.group_hr_user",
    )
    l10n_ua_additional_note = fields.Text(
        string="Додаткова особиста інформація",
        groups="hr.group_hr_user",
    )
    l10n_ua_certificate = fields.Selection(
        CERTIFICATE_SELECTION,
        string="Рівень освіти",
        groups="hr.group_hr_user",
    )
    l10n_ua_study_field = fields.Char(
        string="Спеціальність",
        groups="hr.group_hr_user",
    )
    l10n_ua_study_school = fields.Char(
        string="Навчальний заклад",
        groups="hr.group_hr_user",
    )
    l10n_ua_emergency_contact = fields.Char(
        string="Контакт у разі надзвичайної ситуації",
        groups="hr.group_hr_user",
    )
    l10n_ua_emergency_phone = fields.Char(
        string="Телефон для екстреного зв'язку",
        groups="hr.group_hr_user",
    )

    # Organizational data stays canonical on hr.employee. These fields only
    # expose the current employee card on the Contact form without duplication.
    l10n_ua_employee_id = fields.Many2one(
        "hr.employee",
        string="Основна картка працівника",
        compute="_compute_l10n_ua_employee_id",
        compute_sudo=True,
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_active = fields.Boolean(
        related="l10n_ua_employee_id.active",
        string="Активний працівник",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_identification_id = fields.Char(
        related="l10n_ua_employee_id.identification_id",
        string="Табельний номер",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_company_id = fields.Many2one(
        related="l10n_ua_employee_id.company_id",
        string="Підприємство",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_department_id = fields.Many2one(
        related="l10n_ua_employee_id.department_id",
        string="Підрозділ",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_job_id = fields.Many2one(
        related="l10n_ua_employee_id.job_id",
        string="Посада",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_job_title = fields.Char(
        related="l10n_ua_employee_id.job_title",
        string="Назва посади",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_parent_id = fields.Many2one(
        related="l10n_ua_employee_id.parent_id",
        string="Керівник",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_coach_id = fields.Many2one(
        related="l10n_ua_employee_id.coach_id",
        string="Наставник",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_work_location_id = fields.Many2one(
        related="l10n_ua_employee_id.work_location_id",
        string="Робоче місце",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_work_address_id = fields.Many2one(
        related="l10n_ua_employee_id.address_id",
        string="Робоча адреса",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_work_phone = fields.Char(
        related="l10n_ua_employee_id.work_phone",
        string="Робочий телефон",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_work_email = fields.Char(
        related="l10n_ua_employee_id.work_email",
        string="Робочий email",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_mobile_phone = fields.Char(
        related="l10n_ua_employee_id.mobile_phone",
        string="Робочий мобільний",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_user_id = fields.Many2one(
        related="l10n_ua_employee_id.user_id",
        string="Користувач Odoo",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_type = fields.Selection(
        related="l10n_ua_employee_id.employee_type",
        string="Тип працівника",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_resource_calendar_id = fields.Many2one(
        related="l10n_ua_employee_id.resource_calendar_id",
        string="Робочий графік",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_bank_account_id = fields.Many2one(
        related="l10n_ua_employee_id.bank_account_id",
        string="Рахунок для виплат",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_barcode = fields.Char(
        related="l10n_ua_employee_id.barcode",
        string="ID бейджа",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_pin = fields.Char(
        related="l10n_ua_employee_id.pin",
        string="PIN",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_distance_home_work = fields.Integer(
        related="l10n_ua_employee_id.distance_home_work",
        string="Відстань дім—робота",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_distance_home_work_unit = fields.Selection(
        related="l10n_ua_employee_id.distance_home_work_unit",
        string="Одиниця відстані",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_notes = fields.Text(
        related="l10n_ua_employee_id.notes",
        string="HR-нотатки",
        groups="hr.group_hr_user",
    )
    l10n_ua_employee_category_ids = fields.Many2many(
        related="l10n_ua_employee_id.category_ids",
        string="Теги працівника",
        groups="hr.group_hr_user",
    )

    @api.depends(
        "employee_ids",
        "employee_ids.active",
        "employee_ids.company_id",
    )
    def _compute_l10n_ua_employee_id(self):
        for partner in self:
            employees = partner.with_context(active_test=False).employee_ids
            current_active = employees.filtered(
                lambda employee: employee.active
                and employee.company_id == self.env.company
            )
            active = employees.filtered("active")
            current = employees.filtered(
                lambda employee: employee.company_id == self.env.company
            )
            partner.l10n_ua_employee_id = (
                current_active[:1]
                or active[:1]
                or current[:1]
                or employees[:1]
            )
