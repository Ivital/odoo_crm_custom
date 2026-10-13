from datetime import timedelta
from html import escape
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import UserError


PERSONNEL_RESUME_EVENT_TYPES = {
    "hire",
    "transfer",
    "position_change",
    "department_change",
    "salary_change",
    "schedule_change",
    "employment_condition_change",
    "termination",
}


class HrResumeLinePersonnelHistory(models.Model):
    _inherit = "hr.resume.line"

    l10n_ua_personnel_event_id = fields.Many2one(
        "hr.personnel.event",
        string="Кадрова подія-джерело",
        readonly=True,
        copy=False,
        ondelete="cascade",
        index=True,
    )
    l10n_ua_employment_period_id = fields.Many2one(
        "hr.personnel.employment.period",
        string="Трудовий період-джерело",
        readonly=True,
        copy=False,
        ondelete="cascade",
        index=True,
    )
    l10n_ua_generated_from_personnel_history = fields.Boolean(
        string="Сформовано з кадрової історії",
        readonly=True,
        copy=False,
        default=False,
        index=True,
    )

    _sql_constraints = [
        (
            "l10n_ua_resume_personnel_event_unique",
            "unique(l10n_ua_personnel_event_id)",
            "Для однієї кадрової події може існувати лише один рядок досвіду.",
        ),
    ]


class HrEmployeeResumeHistory(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _l10n_ua_resume_name_key(self, value):
        normalized = unicodedata.normalize(
            "NFKC",
            value or "",
        ).casefold()
        return "".join(
            character
            for character in normalized
            if character.isalnum()
        )

    @api.model
    def _l10n_ua_experience_type(self):
        experience_type = self.env.ref(
            "hr_skills.resume_type_experience",
            raise_if_not_found=False,
        )
        if experience_type:
            return experience_type

        line_types = (
            self.env["hr.resume.line.type"]
            .sudo()
            .with_context(active_test=False)
            .search([])
        )
        for line_type in line_types:
            if (line_type.name or "").strip().casefold() in {
                "experience",
                "досвід",
            }:
                return line_type

        raise UserError(
            _(
                "Не знайдено тип рядка резюме «Experience / Досвід»."
            )
        )

    def _l10n_ua_resume_history_events(self):
        self.ensure_one()
        return self.env["hr.personnel.event"].sudo().search(
            [
                ("employee_id", "=", self.id),
                ("status", "=", "applied"),
                ("event_type", "in", sorted(PERSONNEL_RESUME_EVENT_TYPES)),
            ],
            order="effective_date asc, id asc",
        )

    def _l10n_ua_resume_history_periods(self):
        self.ensure_one()
        return self.env["hr.personnel.employment.period"].sudo().search(
            [("employee_id", "=", self.id)],
            order="date_start asc, first_observed_date asc, id asc",
        )

    def _l10n_ua_resume_factual_start(self):
        self.ensure_one()

        dates = [
            period.date_start
            for period in self._l10n_ua_resume_history_periods()
            if period.date_start
        ]
        dates.extend(
            contract.date_start
            for contract in self.contract_ids
            if (
                contract.state != "cancel"
                and contract.date_start
            )
        )
        if self.service_hire_date:
            dates.append(self.service_hire_date)

        return min(dates) if dates else False

    def _l10n_ua_resume_event_description(self, event):
        self.ensure_one()

        selection = dict(
            event._fields["event_type"]._description_selection(
                self.env
            )
        )
        event_label = selection.get(
            event.event_type,
            event.event_type or "",
        )

        items = []
        if event_label:
            items.append(
                f"<strong>{escape(event_label)}</strong>"
            )

        if event.new_job_id:
            items.append(
                "Посада: "
                f"{escape(event.new_job_id.name or '')}"
            )
        elif event.previous_job_id:
            items.append(
                "Посада: "
                f"{escape(event.previous_job_id.name or '')}"
            )

        if event.new_department_id:
            items.append(
                "Підрозділ: "
                f"{escape(event.new_department_id.name or '')}"
            )
        elif event.previous_department_id:
            items.append(
                "Підрозділ: "
                f"{escape(event.previous_department_id.name or '')}"
            )

        if event.new_resource_calendar_id:
            items.append(
                "Графік: "
                f"{escape(event.new_resource_calendar_id.name or '')}"
            )

        if event.professional_category_id:
            items.append(
                "Категорія / розряд: "
                f"{escape(event.professional_category_id.name or '')}"
            )

        if event.order_id:
            order_text = (
                f"Наказ №{event.order_id.number}"
            )
            if event.order_id.order_date:
                order_text += (
                    " від "
                    f"{fields.Date.to_string(event.order_id.order_date)}"
                )
            items.append(escape(order_text))

        if event.description:
            items.append(
                escape(event.description)
            )

        return "".join(
            f"<p>{item}</p>"
            for item in items
            if item
        )

    def _l10n_ua_resume_period_description(self, period):
        self.ensure_one()

        line = period.origin_order_line_id
        items = [
            "<strong>Початок трудового періоду</strong>",
        ]

        if line.job_id:
            items.append(
                "Посада: "
                f"{escape(line.job_id.name or '')}"
            )

        if line.department_id:
            items.append(
                "Підрозділ: "
                f"{escape(line.department_id.name or '')}"
            )

        if line.order_id:
            order_text = f"Наказ №{line.order_id.number}"
            if line.order_id.order_date:
                order_text += (
                    " від "
                    f"{fields.Date.to_string(line.order_id.order_date)}"
                )
            items.append(escape(order_text))

        return "".join(
            f"<p>{item}</p>"
            for item in items
            if item
        )

    def _l10n_ua_resume_period_at(self, periods, value):
        self.ensure_one()
        if not value:
            return periods[:0]

        matching = periods.filtered(
            lambda period:
                (
                    not period.date_start
                    or period.date_start <= value
                )
                and (
                    not period.date_end
                    or period.date_end >= value
                )
        )
        return matching[:1]

    def _l10n_ua_resume_company_line(self, line):
        self.ensure_one()

        company_key = self._l10n_ua_resume_name_key(
            self.company_id.name
        )
        line_key = self._l10n_ua_resume_name_key(
            line.name
        )
        return bool(
            company_key
            and line_key
            and company_key == line_key
        )

    def l10n_ua_sync_resume_history(
        self,
        cleanup_legacy=False,
    ):
        experience_type = (
            self._l10n_ua_experience_type()
        )
        Resume = (
            self.env["hr.resume.line"]
            .sudo()
            .with_context(active_test=False)
        )

        for employee in self:
            events = (
                employee._l10n_ua_resume_history_events()
            )
            periods = (
                employee._l10n_ua_resume_history_periods()
            )

            generated = Resume.search(
                [
                    (
                        "employee_id",
                        "=",
                        employee.id,
                    ),
                    (
                        "l10n_ua_generated_from_personnel_history",
                        "=",
                        True,
                    ),
                ]
            )
            if generated:
                generated.unlink()

            if cleanup_legacy:
                legacy = Resume.search(
                    [
                        (
                            "employee_id",
                            "=",
                            employee.id,
                        ),
                        (
                            "line_type_id",
                            "=",
                            experience_type.id,
                        ),
                        (
                            "l10n_ua_generated_from_personnel_history",
                            "=",
                            False,
                        ),
                    ]
                )
                company_legacy = legacy.filtered(
                    employee._l10n_ua_resume_company_line
                )
                if company_legacy:
                    company_legacy.unlink()

            entries = []

            event_dates = {
                event.effective_date
                for event in events
                if event.effective_date
            }

            for period in periods:
                if (
                    period.date_start
                    and period.date_start
                    not in event_dates
                ):
                    entries.append(
                        {
                            "date": period.date_start,
                            "kind": "period",
                            "record": period,
                            "sort_id": -period.id,
                        }
                    )

            for event in events:
                if not event.effective_date:
                    continue
                entries.append(
                    {
                        "date": event.effective_date,
                        "kind": "event",
                        "record": event,
                        "sort_id": event.id,
                    }
                )

            if not entries:
                factual_start = (
                    employee._l10n_ua_resume_factual_start()
                )
                if factual_start:
                    entries.append(
                        {
                            "date": factual_start,
                            "kind": "fallback",
                            "record": False,
                            "sort_id": 0,
                        }
                    )

            entries.sort(
                key=lambda item: (
                    item["date"],
                    item["sort_id"],
                )
            )

            for index, item in enumerate(entries):
                start = item["date"]
                next_start = (
                    entries[index + 1]["date"]
                    if index + 1 < len(entries)
                    else False
                )

                end = False
                if next_start:
                    end = (
                        next_start - timedelta(days=1)
                        if next_start > start
                        else start
                    )
                elif item["kind"] == "event":
                    event = item["record"]
                    if event.event_type == "termination":
                        end = start
                    else:
                        period = (
                            event.employment_period_id
                            or employee._l10n_ua_resume_period_at(
                                periods,
                                start,
                            )
                        )
                        if (
                            period
                            and period.date_end
                            and period.date_end >= start
                        ):
                            end = period.date_end
                elif item["kind"] == "period":
                    period = item["record"]
                    if (
                        period.date_end
                        and period.date_end >= start
                    ):
                        end = period.date_end

                vals = {
                    "employee_id": employee.id,
                    "line_type_id": experience_type.id,
                    "name": (
                        employee.company_id.name
                        or self.env.company.name
                    ),
                    "date_start": start,
                    "date_end": end,
                    "display_type": "classic",
                    "l10n_ua_generated_from_personnel_history": True,
                }

                if item["kind"] == "event":
                    event = item["record"]
                    vals.update(
                        {
                            "description":
                                employee._l10n_ua_resume_event_description(
                                    event
                                ),
                            "l10n_ua_personnel_event_id":
                                event.id,
                            "l10n_ua_employment_period_id":
                                event.employment_period_id.id
                                or False,
                        }
                    )

                elif item["kind"] == "period":
                    period = item["record"]
                    vals.update(
                        {
                            "description":
                                employee._l10n_ua_resume_period_description(
                                    period
                                ),
                            "l10n_ua_employment_period_id":
                                period.id,
                        }
                    )

                else:
                    details = []
                    if employee.job_id:
                        details.append(
                            "Посада: "
                            f"{escape(employee.job_id.name or '')}"
                        )
                    if employee.department_id:
                        details.append(
                            "Підрозділ: "
                            f"{escape(employee.department_id.name or '')}"
                        )
                    vals["description"] = "".join(
                        f"<p>{item}</p>"
                        for item in details
                    )

                Resume.create(vals)

        return True


class HrPersonnelEventResumeSync(models.Model):
    _inherit = "hr.personnel.event"

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)

        if not self.env.context.get(
            "skip_personnel_resume_sync"
        ):
            employees = events.filtered(
                lambda event:
                    event.status == "applied"
                    and event.employee_id
            ).mapped("employee_id")
            if employees:
                employees.l10n_ua_sync_resume_history()

        return events

    def write(self, vals):
        before_employees = self.mapped("employee_id")

        result = super().write(vals)

        if self.env.context.get(
            "skip_personnel_resume_sync"
        ):
            return result

        watched = {
            "employee_id",
            "effective_date",
            "status",
            "previous_department_id",
            "new_department_id",
            "previous_job_id",
            "new_job_id",
            "previous_resource_calendar_id",
            "new_resource_calendar_id",
            "professional_category_id",
            "work_type",
            "hire_condition",
            "weekly_hours",
            "work_conditions",
            "allowance_note",
            "employment_period_id",
            "description",
        }

        if watched.intersection(vals):
            employees = (
                before_employees
                | self.mapped("employee_id")
            )
            if employees:
                employees.l10n_ua_sync_resume_history()

        return result


class HrPersonnelEmploymentPeriodResumeSync(models.Model):
    _inherit = "hr.personnel.employment.period"

    @api.model_create_multi
    def create(self, vals_list):
        periods = super().create(vals_list)

        if not self.env.context.get(
            "skip_personnel_resume_sync"
        ):
            employees = periods.mapped("employee_id")
            if employees:
                employees.l10n_ua_sync_resume_history()

        return periods

    def write(self, vals):
        before_employees = self.mapped("employee_id")

        result = super().write(vals)

        if self.env.context.get(
            "skip_personnel_resume_sync"
        ):
            return result

        if {
            "employee_id",
            "date_start",
            "date_end",
            "first_observed_date",
            "origin_order_line_id",
            "start_order_line_id",
            "end_order_line_id",
        }.intersection(vals):
            employees = (
                before_employees
                | self.mapped("employee_id")
            )
            if employees:
                employees.l10n_ua_sync_resume_history()

        return result
