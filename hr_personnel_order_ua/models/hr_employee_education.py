from odoo import fields, models


EDUCATION_LEVEL_SELECTION = [
    ("basic_secondary", "Базова загальна середня"),
    ("complete_secondary", "Повна загальна середня"),
    ("vocational", "Професійно-технічна"),
    ("incomplete_higher", "Неповна вища"),
    ("basic_higher", "Базова вища"),
    ("complete_higher", "Повна вища"),
    ("other", "Інша"),
]

STUDY_FORM_SELECTION = [
    ("full_time", "Денна"),
    ("evening", "Вечірня"),
    ("part_time", "Заочна"),
    ("other", "Інша"),
]


class HrEmployeeEducation(models.Model):
    _name = "hr.employee.education"
    _description = "Освіта працівника"
    _order = "sequence, graduation_year, id"

    sequence = fields.Integer(default=10)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Працівник",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="employee_id.company_id",
        string="Підприємство",
        store=True,
        index=True,
        readonly=True,
    )
    education_level = fields.Selection(
        EDUCATION_LEVEL_SELECTION,
        string="Рівень / вид освіти",
    )
    institution_name = fields.Char(
        string="Назва освітнього закладу",
        required=True,
    )
    specialty = fields.Char(
        string="Спеціальність (професія)",
    )
    qualification = fields.Char(
        string="Кваліфікація",
    )
    study_form = fields.Selection(
        STUDY_FORM_SELECTION,
        string="Форма навчання",
    )
    document_type = fields.Char(
        string="Вид документа про освіту",
    )
    document_series = fields.Char(
        string="Серія документа",
    )
    document_number = fields.Char(
        string="Номер документа",
    )
    issue_date = fields.Date(
        string="Дата видачі документа",
    )
    graduation_year = fields.Integer(
        string="Рік закінчення",
    )
    note = fields.Text(
        string="Примітка",
    )
    source = fields.Char(
        string="Джерело",
        readonly=True,
        copy=False,
    )
    source_reference = fields.Char(
        string="Посилання на джерело",
        readonly=True,
        copy=False,
    )

    def _l10n_ua_p2_document_text(self):
        self.ensure_one()
        parts = []
        if self.document_type:
            parts.append(self.document_type.strip())

        series_number = " ".join(
            part.strip()
            for part in [
                self.document_series or "",
                self.document_number or "",
            ]
            if part and part.strip()
        )
        if series_number:
            parts.append(series_number)

        return ", ".join(parts)

    def _l10n_ua_p2_study_form_label(self):
        self.ensure_one()
        if not self.study_form:
            return ""
        return dict(
            self._fields["study_form"]._description_selection(self.env)
        ).get(self.study_form, self.study_form)
