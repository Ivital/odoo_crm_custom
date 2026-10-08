from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ua_short_name = fields.Char(
        related="partner_id.l10n_ua_short_name", readonly=False
    )
    l10n_ua_kopfg_id = fields.Many2one(
        related="partner_id.l10n_ua_kopfg_id", readonly=False
    )
    l10n_ua_legal_status = fields.Selection(
        related="partner_id.l10n_ua_legal_status", readonly=False
    )
    l10n_ua_registration_date = fields.Date(
        related="partner_id.l10n_ua_registration_date", readonly=False
    )
    l10n_ua_edr_record_number = fields.Char(
        related="partner_id.l10n_ua_edr_record_number", readonly=False
    )
    l10n_ua_last_registration_action_date = fields.Date(
        related="partner_id.l10n_ua_last_registration_action_date", readonly=False
    )
    l10n_ua_tax_system = fields.Selection(
        related="partner_id.l10n_ua_tax_system", readonly=False
    )
    l10n_ua_single_tax_group = fields.Selection(
        related="partner_id.l10n_ua_single_tax_group", readonly=False
    )
    l10n_ua_single_tax_rate = fields.Float(
        related="partner_id.l10n_ua_single_tax_rate", readonly=False
    )
    l10n_ua_tax_authority = fields.Char(
        related="partner_id.l10n_ua_tax_authority", readonly=False
    )
    l10n_ua_vat_registered = fields.Boolean(
        related="partner_id.l10n_ua_vat_registered", readonly=False
    )
    l10n_ua_vat_number = fields.Char(
        related="partner_id.l10n_ua_vat_number", readonly=False
    )
    l10n_ua_vat_registration_date = fields.Date(
        related="partner_id.l10n_ua_vat_registration_date", readonly=False
    )
    l10n_ua_vat_cancellation_date = fields.Date(
        related="partner_id.l10n_ua_vat_cancellation_date", readonly=False
    )
    l10n_ua_activity_classifier = fields.Selection(
        related="partner_id.l10n_ua_activity_classifier", readonly=False
    )
    l10n_ua_main_kved_id = fields.Many2one(
        related="partner_id.l10n_ua_main_kved_id", readonly=False
    )
    l10n_ua_kved_ids = fields.Many2many(
        related="partner_id.l10n_ua_kved_ids", readonly=False
    )
    l10n_ua_currency_id = fields.Many2one(
        related="partner_id.l10n_ua_currency_id", readonly=False
    )
    l10n_ua_statutory_capital = fields.Monetary(
        related="partner_id.l10n_ua_statutory_capital",
        currency_field="l10n_ua_currency_id",
        readonly=False,
    )
    l10n_ua_manager_partner_id = fields.Many2one(
        related="partner_id.l10n_ua_manager_partner_id", readonly=False
    )
    l10n_ua_manager_position = fields.Char(
        related="partner_id.l10n_ua_manager_position", readonly=False
    )
    l10n_ua_manager_appointment_date = fields.Date(
        related="partner_id.l10n_ua_manager_appointment_date", readonly=False
    )
    l10n_ua_manager_authority_basis = fields.Selection(
        related="partner_id.l10n_ua_manager_authority_basis", readonly=False
    )
    l10n_ua_manager_authority_basis_note = fields.Char(
        related="partner_id.l10n_ua_manager_authority_basis_note", readonly=False
    )
    l10n_ua_representation_restrictions = fields.Text(
        related="partner_id.l10n_ua_representation_restrictions", readonly=False
    )
    l10n_ua_authorized_person_ids = fields.One2many(
        related="partner_id.l10n_ua_authorized_person_ids", readonly=False
    )
    l10n_ua_participant_ids = fields.One2many(
        related="partner_id.l10n_ua_participant_ids", readonly=False
    )
    l10n_ua_beneficial_owner_ids = fields.One2many(
        related="partner_id.l10n_ua_beneficial_owner_ids", readonly=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            company.partner_id.l10n_ua_currency_id = company.currency_id
        return companies

    def write(self, vals):
        result = super().write(vals)
        if "currency_id" in vals:
            for company in self:
                company.partner_id.l10n_ua_currency_id = company.currency_id
        return result
