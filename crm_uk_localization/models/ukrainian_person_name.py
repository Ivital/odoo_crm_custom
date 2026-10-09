from odoo import api, fields, models


def _split_ukrainian_person_name(name):
    """Split Ukrainian PІB as: surname, given name, patronymic.

    Patronymics consisting of more than one token (for example "Сагіт огли")
    are preserved intact.
    """
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
    # OCA technical field `lastname2` is reused by the Ukrainian localization
    # as the patronymic field. Keeping the technical field avoids a parallel
    # identity store while changing its business meaning and UI label.
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


class ResPartner(models.Model):
    _inherit = "res.partner"

    lastname = fields.Char(string="Прізвище", index=True)
    firstname = fields.Char(string="Ім'я", index=True)
    lastname2 = fields.Char(string="По батькові")

    @api.model
    def _get_computed_name(self, lastname, firstname, lastname2=None):
        return _compose_ukrainian_person_name(lastname, firstname, lastname2)

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
