from odoo import api, fields, models

from .res_partner import SYNC_CONTEXT_KEY


def _split_ukrainian_person_name(name):
    """Split Ukrainian ПІБ as surname, given name, patronymic."""
    clean = " ".join((name or "").split())
    if not clean:
        return {
            "lastname": False,
            "firstname": False,
            "lastname2": False,
        }

    parts = clean.split(" ")
    return {
        "lastname": parts[0] or False,
        "firstname": parts[1] if len(parts) >= 2 else False,
        "lastname2": " ".join(parts[2:]) if len(parts) >= 3 else False,
    }


def _compose_ukrainian_person_name(lastname, firstname, patronymic=None):
    return " ".join(
        part.strip()
        for part in (lastname, firstname, patronymic)
        if isinstance(part, str) and part.strip()
    )


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    lastname = fields.Char(string="Прізвище")
    firstname = fields.Char(string="Ім'я")
    lastname2 = fields.Char(string="По батькові")


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _get_name(self, lastname, firstname):
        return _compose_ukrainian_person_name(lastname, firstname)

    @api.model
    def _get_name_lastnames(self, lastname, firstname, lastname2=None):
        return _compose_ukrainian_person_name(lastname, firstname, lastname2)

    @api.model
    def _get_inverse_name(self, name):
        return _split_ukrainian_person_name(name)

    def _update_partner_firstname(self):
        if self.env.context.get(SYNC_CONTEXT_KEY):
            return

        for employee in self:
            partners = employee.mapped("user_id.partner_id")
            partners |= employee.mapped("work_contact_id")
            if not partners:
                continue

            partners.sudo().with_context(**{SYNC_CONTEXT_KEY: True}).write(
                {
                    "lastname": employee.lastname,
                    "firstname": employee.firstname,
                    "lastname2": employee.lastname2,
                    "middlename": False,
                }
            )


class ResPartner(models.Model):
    _inherit = "res.partner"

    lastname = fields.Char(string="Прізвище", index=True)
    firstname = fields.Char(string="Ім'я", index=True)
    lastname2 = fields.Char(string="По батькові")

    @api.model
    def _get_computed_name(self, lastname, firstname, lastname2=None):
        return _compose_ukrainian_person_name(lastname, firstname, lastname2)

    @api.depends("firstname", "lastname", "lastname2")
    def _compute_name(self):
        for partner in self:
            partner.name = _compose_ukrainian_person_name(
                partner.lastname,
                partner.firstname,
                partner.lastname2,
            )

    @api.model
    def _get_inverse_name(self, name, is_company=False):
        clean = " ".join((name or "").split())
        if is_company:
            return {
                "lastname": clean or False,
                "firstname": False,
                "lastname2": False,
            }
        return _split_ukrainian_person_name(clean)

    def _inverse_name(self):
        for partner in self:
            values = self._get_inverse_name(partner.name, partner.is_company)
            if "middlename" in partner._fields:
                values["middlename"] = False
            partner.update(values)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            if vals.get("middlename") and not vals.get("lastname2"):
                vals["lastname2"] = vals["middlename"]
            if "middlename" in vals:
                vals["middlename"] = False
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)

        if vals.get("middlename") and not vals.get("lastname2"):
            vals["lastname2"] = vals["middlename"]
        if "middlename" in vals:
            vals["middlename"] = False

        identity_values = {
            field_name: vals[field_name]
            for field_name in ("lastname", "firstname", "lastname2")
            if field_name in vals
        }

        result = super().write(vals)

        if identity_values and not self.env.context.get(SYNC_CONTEXT_KEY):
            for partner in self:
                employees = partner.sudo().with_context(
                    active_test=False
                ).employee_ids
                if employees:
                    employees.with_context(
                        **{SYNC_CONTEXT_KEY: True}
                    ).write(identity_values)

        return result
