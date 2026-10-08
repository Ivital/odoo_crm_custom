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
    "l10n_ua_rnokpp",
    "passport_id",
    "marital",
    "spouse_complete_name",
    "spouse_birthdate",
    "children",
    "ssnid",
    "sinid",
    "permit_no",
    "visa_no",
    "visa_expire",
    "work_permit_expiration_date",
    "additional_note",
    "certificate",
    "study_field",
    "study_school",
    "emergency_contact",
    "emergency_phone",
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
    l10n_ua_rnokpp = fields.Char(
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
    marital = fields.Selection(
        related="work_contact_id.l10n_ua_marital",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    spouse_complete_name = fields.Char(
        related="work_contact_id.l10n_ua_spouse_complete_name",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    spouse_birthdate = fields.Date(
        related="work_contact_id.l10n_ua_spouse_birthdate",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    children = fields.Integer(
        related="work_contact_id.l10n_ua_children",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    ssnid = fields.Char(
        related="work_contact_id.l10n_ua_ssnid",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    sinid = fields.Char(
        related="work_contact_id.l10n_ua_sinid",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    permit_no = fields.Char(
        related="work_contact_id.l10n_ua_permit_no",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    visa_no = fields.Char(
        related="work_contact_id.l10n_ua_visa_no",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    visa_expire = fields.Date(
        related="work_contact_id.l10n_ua_visa_expire",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    work_permit_expiration_date = fields.Date(
        related="work_contact_id.l10n_ua_work_permit_expiration_date",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    additional_note = fields.Text(
        related="work_contact_id.l10n_ua_additional_note",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    certificate = fields.Selection(
        related="work_contact_id.l10n_ua_certificate",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    study_field = fields.Char(
        related="work_contact_id.l10n_ua_study_field",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    study_school = fields.Char(
        related="work_contact_id.l10n_ua_study_school",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    emergency_contact = fields.Char(
        related="work_contact_id.l10n_ua_emergency_contact",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )
    emergency_phone = fields.Char(
        related="work_contact_id.l10n_ua_emergency_phone",
        readonly=False,
        groups="hr.group_hr_user",
        tracking=True,
    )

    def _create_work_contacts(self):
        """Create employee contacts as children of the employee company."""
        result = super()._create_work_contacts()
        for employee in self:
            partner = employee.work_contact_id
            company_partner = employee.company_id.partner_id
            if (
                partner
                and company_partner
                and partner != company_partner
                and not partner.parent_id
            ):
                partner.sudo().with_context(
                    **{SYNC_CONTEXT_KEY: True}
                ).write(
                    {
                        "parent_id": company_partner.id,
                        "type": "contact",
                    }
                )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        # Writable related personal fields cannot be written before standard HR
        # creates/links work_contact_id. Hold them and write after super().
        # identification_id deliberately remains the Employee ID/tabular number.
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
        """Keep the visible contact identity aligned with its Employee card."""
        for employee in self:
            if not employee.work_contact_id:
                continue
            employee.work_contact_id.sudo().with_context(
                **{SYNC_CONTEXT_KEY: True}
            ).write(
                {
                    "name": employee.name,
                    "image_1920": employee.image_1920,
                    "function": employee.job_title,
                    "phone": employee.work_phone,
                }
            )

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get(SYNC_CONTEXT_KEY):
            return result

        identity_triggers = {
            "name",
            "image_1920",
            "work_contact_id",
            "job_id",
            "job_title",
            "address_id",
            "work_phone",
        }
        if identity_triggers.intersection(vals):
            self._l10n_ua_sync_identity_to_contact()
        return result
