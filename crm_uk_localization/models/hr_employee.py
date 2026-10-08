from odoo import api, fields, models

from .res_partner import SYNC_CONTEXT_KEY


RELATED_PERSONAL_FIELDS = {
    "private_street",
    "private_street2",
    "private_city",
    "private_state_id",
    "private_zip",
    "private_country_id",
    "private_phone",
    "private_email",
    "country_id",
    "gender",
    "birthday",
    "place_of_birth",
    "country_of_birth",
    "identification_id",
    "passport_id",
}


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    private_street = fields.Char(
        related="work_contact_id.l10n_ua_private_street",
        readonly=False,
        groups="hr.group_hr_user",
    )
    private_street2 = fields.Char(
        related="work_contact_id.l10n_ua_private_street2",
        readonly=False,
        groups="hr.group_hr_user",
    )
    private_city = fields.Char(
        related="work_contact_id.l10n_ua_private_city",
        readonly=False,
        groups="hr.group_hr_user",
    )
    private_state_id = fields.Many2one(
        related="work_contact_id.l10n_ua_private_state_id",
        readonly=False,
        domain="[('country_id', '=?', private_country_id)]",
        groups="hr.group_hr_user",
    )
    private_zip = fields.Char(
        related="work_contact_id.l10n_ua_private_zip",
        readonly=False,
        groups="hr.group_hr_user",
    )
    private_country_id = fields.Many2one(
        related="work_contact_id.l10n_ua_private_country_id",
        readonly=False,
        groups="hr.group_hr_user",
    )
    private_phone = fields.Char(
        related="work_contact_id.l10n_ua_private_phone",
        readonly=False,
        groups="hr.group_hr_user",
    )
    private_email = fields.Char(
        related="work_contact_id.l10n_ua_private_email",
        readonly=False,
        groups="hr.group_hr_user",
    )
    country_id = fields.Many2one(
        related="work_contact_id.nationality_id",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    gender = fields.Selection(
        related="work_contact_id.gender",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    birthday = fields.Date(
        related="work_contact_id.birthdate_date",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    place_of_birth = fields.Char(
        related="work_contact_id.birth_city",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    country_of_birth = fields.Many2one(
        related="work_contact_id.birth_country_id",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    identification_id = fields.Char(
        related="work_contact_id.l10n_ua_rnokpp",
        readonly=False,
        string="РНОКПП",
        groups="hr.group_hr_user",
        tracking=True,
    )
    passport_id = fields.Char(
        related="work_contact_id.l10n_ua_passport_number",
        readonly=False,
        string="Паспорт / документ, що посвідчує особу",
        groups="hr.group_hr_user",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        # A new employee receives work_contact_id inside standard hr.create().
        # Hold values of writable related personal fields until that contact exists.
        prepared = []
        pending_personal = []
        for incoming in vals_list:
            vals = dict(incoming)
            pending = {
                key: vals.pop(key)
                for key in list(vals)
                if key in RELATED_PERSONAL_FIELDS
            }
            prepared.append(vals)
            pending_personal.append(pending)

        employees = super().create(prepared)

        for employee, pending in zip(employees, pending_personal):
            if pending:
                employee.write(pending)

        if not self.env.context.get(SYNC_CONTEXT_KEY):
            employees._l10n_ua_sync_identity_to_contact()
        return employees

    def _l10n_ua_sync_identity_to_contact(self):
        for employee in self:
            if not employee.work_contact_id:
                continue
            employee.work_contact_id.sudo().with_context(
                **{SYNC_CONTEXT_KEY: True}
            ).write(
                {
                    "name": employee.name,
                    "image_1920": employee.image_1920,
                }
            )

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get(SYNC_CONTEXT_KEY):
            return result
        if {"name", "image_1920", "work_contact_id"}.intersection(vals):
            self._l10n_ua_sync_identity_to_contact()
        return result
