from odoo import api, models, _
from odoo.exceptions import ValidationError


class ResPartnerIdNumber(models.Model):
    _inherit = "res.partner.id_number"

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        Category = self.env["res.partner.id_category"]
        for incoming in vals_list:
            vals = dict(incoming)
            category = Category.browse(vals.get("category_id")).exists()
            if category.code in {"ua_rnokpp", "ua_passport"} and vals.get("name"):
                vals["name"] = vals["name"].strip()
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        target_category = (
            self.env["res.partner.id_category"].browse(vals.get("category_id")).exists()
            if vals.get("category_id")
            else self[:1].category_id
        )
        if vals.get("name") and target_category.code in {"ua_rnokpp", "ua_passport"}:
            vals["name"] = vals["name"].strip()
        return super().write(vals)

    @api.constrains("name", "category_id", "active", "status")
    def _check_l10n_ua_rnokpp(self):
        for record in self:
            if record.category_id.code != "ua_rnokpp":
                continue
            number = (record.name or "").strip()
            if not re_fullmatch_digits_10(number):
                raise ValidationError(_("РНОКПП має містити рівно 10 цифр."))
            duplicate = self.search(
                [
                    ("id", "!=", record.id),
                    ("category_id.code", "=", "ua_rnokpp"),
                    ("name", "=", number),
                    ("active", "=", True),
                    ("status", "!=", "close"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("Такий РНОКПП уже використовується в іншому контакті.")
                )


def re_fullmatch_digits_10(value):
    return len(value) == 10 and value.isdigit()
