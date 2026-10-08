from odoo import api, fields, models


KVED_CLASSIFIER_SELECTION = [
    ("kved_2010", "КВЕД-2010 (ДК 009:2010)"),
    ("nace_2_1_ua", "NACE 2.1-UA (з 01.01.2027)"),
]


class L10nUaKved(models.Model):
    _name = "l10n_ua.kved"
    _description = "Класифікація видів економічної діяльності України"
    _order = "classifier, code"
    _rec_names_search = ("code", "name", "section_name")

    classifier = fields.Selection(
        KVED_CLASSIFIER_SELECTION,
        string="Класифікатор",
        required=True,
        default="kved_2010",
        index=True,
    )
    code = fields.Char(string="Код", required=True, index=True)
    name = fields.Char(string="Назва", required=True, translate=True, index=True)
    section_code = fields.Char(string="Секція", index=True)
    section_name = fields.Char(string="Назва секції", translate=True)
    division_code = fields.Char(string="Розділ", index=True)
    group_code = fields.Char(string="Група", index=True)
    selectable = fields.Boolean(
        string="Можна призначати суб'єкту",
        default=True,
        index=True,
    )
    valid_from = fields.Date(string="Чинний з")
    valid_to = fields.Date(string="Чинний до")
    source_url = fields.Char(string="Офіційне джерело")
    active = fields.Boolean(default=True, index=True)

    _sql_constraints = [
        (
            "classifier_code_unique",
            "unique(classifier, code)",
            "Код виду діяльності має бути унікальним у межах версії класифікатора.",
        ),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} — {record.name}"


class L10nUaKopfg(models.Model):
    _name = "l10n_ua.kopfg"
    _description = "КОПФГ України (ДК 002:2004)"
    _order = "code"
    _rec_names_search = ("code", "name", "previous_code")

    code = fields.Char(string="Код", required=True, index=True)
    name = fields.Char(string="Назва", required=True, translate=True, index=True)
    previous_code = fields.Char(string="Попередній код", index=True)
    group_code = fields.Char(string="Група", index=True)
    selectable = fields.Boolean(
        string="Можна призначати суб'єкту",
        default=True,
        index=True,
    )
    obsolete = fields.Boolean(
        string="Нова державна реєстрація не передбачається",
        default=False,
        index=True,
    )
    valid_from = fields.Date(string="Чинний з")
    source_url = fields.Char(string="Офіційне джерело")
    active = fields.Boolean(default=True, index=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Код КОПФГ має бути унікальним."),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} — {record.name}"
