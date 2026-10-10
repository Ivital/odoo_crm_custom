from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrPersonnelOrderReport(models.Model):
    _inherit = "hr.personnel.order"

    def _l10n_ua_print_order_form(self, expected_type, report_xmlid, form_name):
        if not self:
            raise UserError(_("Не вибрано кадровий наказ для друку."))

        invalid = self.filtered(lambda order: order.order_type != expected_type)
        if invalid:
            raise ValidationError(
                _("%s можна друкувати лише для відповідного типу кадрового наказу.")
                % form_name
            )

        return self.env.ref(report_xmlid).report_action(self)

    def action_print_p1(self):
        return self._l10n_ua_print_order_form(
            "hire",
            "hr_personnel_order_ua.action_report_personnel_order_p1",
            _("Форму П-1"),
        )

    def action_print_p3(self):
        return self._l10n_ua_print_order_form(
            "leave",
            "hr_personnel_order_ua.action_report_personnel_order_p3",
            _("Форму П-3"),
        )

    def action_print_p4(self):
        return self._l10n_ua_print_order_form(
            "termination",
            "hr_personnel_order_ua.action_report_personnel_order_p4",
            _("Форму П-4"),
        )


class HrEmployeePersonnelReport(models.Model):
    _inherit = "hr.employee"

    l10n_ua_p2_card_number = fields.Char(
        string="Номер особової картки П-2",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_ua_p2_card_date = fields.Date(
        string="Дата заповнення картки П-2",
        groups="hr.group_hr_user",
        tracking=True,
    )

    l10n_ua_p2_last_workplace = fields.Char(
        string="Останнє місце роботи до підприємства",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_ua_p2_last_job = fields.Char(
        string="Посада / професія на останньому місці роботи",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_ua_p2_last_departure_date = fields.Date(
        string="Дата звільнення з попереднього місця роботи",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_ua_p2_last_departure_reason = fields.Char(
        string="Причина звільнення з попереднього місця роботи",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_ua_p2_total_service_as_of = fields.Date(
        string="Стаж роботи станом на",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_total_service_years = fields.Integer(
        string="Загальний стаж: років",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_total_service_months = fields.Integer(
        string="Загальний стаж: місяців",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_total_service_days = fields.Integer(
        string="Загальний стаж: днів",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_seniority_years = fields.Integer(
        string="Стаж для надбавки: років",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_seniority_months = fields.Integer(
        string="Стаж для надбавки: місяців",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_seniority_days = fields.Integer(
        string="Стаж для надбавки: днів",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_pension_info = fields.Text(
        string="Відомості про отримання пенсії",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_registered_address = fields.Text(
        string="Місце проживання за державною реєстрацією",
        groups="hr.group_hr_user",
    )

    l10n_ua_p2_military_group = fields.Char(
        string="Військовий облік: група обліку",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_category = fields.Char(
        string="Військовий облік: категорія обліку",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_composition = fields.Char(
        string="Військовий облік: склад",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_rank = fields.Char(
        string="Військове звання",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_specialty = fields.Char(
        string="Військово-облікова спеціальність №",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_fitness = fields.Char(
        string="Придатність до військової служби",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_tcc_registered = fields.Char(
        string="ТЦК та СП за місцем реєстрації",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_tcc_actual = fields.Char(
        string="ТЦК та СП за місцем фактичного проживання",
        groups="hr.group_hr_user",
    )
    l10n_ua_p2_military_special_register = fields.Char(
        string="Перебування на спеціальному обліку",
        groups="hr.group_hr_user",
    )

    @api.constrains(
        "l10n_ua_p2_total_service_years",
        "l10n_ua_p2_total_service_months",
        "l10n_ua_p2_total_service_days",
        "l10n_ua_p2_seniority_years",
        "l10n_ua_p2_seniority_months",
        "l10n_ua_p2_seniority_days",
    )
    def _check_l10n_ua_p2_service_values(self):
        for employee in self:
            values = [
                employee.l10n_ua_p2_total_service_years,
                employee.l10n_ua_p2_total_service_months,
                employee.l10n_ua_p2_total_service_days,
                employee.l10n_ua_p2_seniority_years,
                employee.l10n_ua_p2_seniority_months,
                employee.l10n_ua_p2_seniority_days,
            ]
            if any(value < 0 for value in values):
                raise ValidationError(_("Значення стажу не можуть бути від'ємними."))

    def _l10n_ua_report_selection_label(self, field_name):
        self.ensure_one()
        field = self._fields.get(field_name)
        if not field or field.type != "selection":
            return ""
        value = self[field_name]
        if not value:
            return ""
        selection = field._description_selection(self.env)
        return dict(selection).get(value, value)

    def _l10n_ua_report_private_address(self):
        self.ensure_one()
        parts = [
            self.private_zip,
            self.private_state_id.name if self.private_state_id else False,
            self.private_city,
            self.private_street,
            self.private_street2,
            self.private_country_id.name if self.private_country_id else False,
        ]
        return ", ".join(str(part).strip() for part in parts if part)

    def _l10n_ua_report_passport_record(self):
        self.ensure_one()
        partner = self.work_contact_id.sudo()
        if not partner:
            return self.env["res.partner.id_number"]
        return self.env["res.partner.id_number"].sudo().search(
            [
                ("partner_id", "=", partner.id),
                ("category_id.code", "=", "ua_passport"),
                ("active", "=", True),
                ("status", "!=", "close"),
            ],
            order="date_issued desc, id desc",
            limit=1,
        )

    def _l10n_ua_report_employment_events(self):
        self.ensure_one()
        return self.env["hr.personnel.event"].sudo().search(
            [
                ("employee_id", "=", self.id),
                ("status", "=", "applied"),
                (
                    "event_type",
                    "in",
                    [
                        "hire",
                        "transfer",
                        "position_change",
                        "department_change",
                        "salary_change",
                        "schedule_change",
                        "employment_condition_change",
                    ],
                ),
            ],
            order="effective_date asc, id asc",
        )

    def _l10n_ua_report_leaves(self):
        self.ensure_one()
        return self.env["hr.leave"].sudo().search(
            [
                ("employee_id", "=", self.id),
                ("state", "=", "validate"),
            ],
            order="request_date_from asc, id asc",
        )

    def _l10n_ua_report_latest_medical_exam(self):
        self.ensure_one()
        return self.env["hr.employee.medical.examination"].sudo().search(
            [
                ("employee_id", "=", self.id),
                ("state", "=", "done"),
            ],
            order="date desc, id desc",
            limit=1,
        )

    def action_print_personal_card_p2(self):
        if not self:
            raise UserError(_("Не вибрано працівника для друку П-2."))
        return self.env.ref(
            "hr_personnel_order_ua.action_report_personal_card_p2"
        ).report_action(self)
