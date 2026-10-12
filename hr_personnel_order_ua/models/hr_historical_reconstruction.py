import unicodedata

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .constants import ENGINE_CONTEXT_KEY, ORDER_TYPE_SELECTION


ENTRY_MODE_SELECTION = [
    ("current", "Поточний кадровий процес"),
    ("historical", "Історичне відновлення"),
]


SOURCE_STATUS_SELECTION = [
    ("normal", "Чинний запис джерела"),
    ("annulled", "Анульований у джерелі"),
]


IDENTITY_RESOLUTION_SELECTION = [
    ("unresolved", "Не визначено"),
    ("matched", "Зіставлено з наявною карткою"),
    ("new", "Нова історична картка"),
    ("ambiguous", "Неоднозначне зіставлення"),
]


class HrJobHistoricalCanonical(models.Model):
    _inherit = "hr.job"

    @api.model
    def l10n_ua_canonical_job_name(self, name):
        """
        Canonical display form for job names imported from
        historical sources.

        - collapse whitespace;
        - first character uppercase;
        - preserve the rest of the wording.
        """
        compact = " ".join(
            (name or "").split()
        ).strip()

        if not compact:
            raise ValidationError(
                _("Назва посади не може бути порожньою.")
            )

        return (
            compact[:1].upper()
            + compact[1:]
        )

    @api.model
    def l10n_ua_job_name_key(self, name):
        # Unicode compatibility normalization is required
        # before whitespace folding and casefolding. Without
        # NFKC, visually equivalent compatibility forms such
        # as ASCII "ABC" and FULLWIDTH "ＡＢＣ" produce
        # different historical job identity keys.
        normalized = unicodedata.normalize(
            "NFKC",
            name or "",
        )

        return " ".join(
            normalized.split()
        ).strip().casefold()

    @api.model
    def l10n_ua_find_canonical_job(
        self,
        source_name,
        company=False,
    ):
        company = company or self.env.company

        key = self.l10n_ua_job_name_key(
            source_name
        )

        candidates = (
            self.with_context(active_test=False)
            .search(
                [
                    (
                        "company_id",
                        "in",
                        [
                            False,
                            company.id,
                        ],
                    )
                ]
            )
        )

        matches = candidates.filtered(
            lambda job:
                self.l10n_ua_job_name_key(
                    job.name
                )
                == key
        )

        if len(matches) > 1:
            raise ValidationError(
                _(
                    "Назва посади «%(name)s» "
                    "відповідає кільком записам "
                    "довідника: %(jobs)s."
                )
                % {
                    "name": source_name,
                    "jobs": ", ".join(
                        matches.mapped(
                            "display_name"
                        )
                    ),
                }
            )

        return matches[:1]

    @api.model
    def l10n_ua_get_or_create_canonical_job(
        self,
        source_name,
        company=False,
    ):
        company = company or self.env.company

        existing = (
            self.l10n_ua_find_canonical_job(
                source_name,
                company=company,
            )
        )

        if existing:
            return existing

        return self.create(
            {
                "name":
                    self.l10n_ua_canonical_job_name(
                        source_name
                    ),
                "company_id":
                    company.id,
            }
        )


class HrPersonnelOrderHistorical(models.Model):
    _inherit = "hr.personnel.order"

    entry_mode = fields.Selection(
        ENTRY_MODE_SELECTION,
        string="Режим внесення",
        required=True,
        default="current",
        tracking=True,
        index=True,
    )

    source_register_key = fields.Char(
        string="Код журналу-джерела",
        copy=False,
        index=True,
        help=(
            "Стабільний машинний код джерела, "
            "наприклад personnel-long-orders."
        ),
    )

    source_register_name = fields.Char(
        string="Назва журналу-джерела",
        copy=False,
    )

    source_year = fields.Integer(
        string="Рік журналу-джерела",
        copy=False,
        index=True,
        help=(
            "Рік первинного реєстраційного журналу. "
            "Це реквізит джерела, а не заміна дати "
            "чи року самого кадрового наказу."
        ),
    )

    source_row = fields.Integer(
        string="Рядок у журналі",
        copy=False,
        index=True,
    )

    source_key = fields.Char(
        string="Унікальний ключ джерела",
        copy=False,
        index=True,
        help=(
            "Стабільний ключ для повторного безпечного "
            "імпорту одного й того самого запису."
        ),
    )

    source_status = fields.Selection(
        SOURCE_STATUS_SELECTION,
        string="Статус у джерелі",
        required=True,
        default="normal",
        copy=False,
        index=True,
    )

    source_text = fields.Text(
        string="Оригінальний текст запису",
        copy=False,
    )

    source_note = fields.Text(
        string="Оригінальна графа «Примітки»",
        copy=False,
    )

    def init(self):
        super().init()

        # Historical source rows may legitimately reuse the
        # same legal order number. Modern/current personnel
        # orders must retain the original number/year
        # uniqueness contract.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                hr_personnel_order_current_number_company_year_uidx
            ON hr_personnel_order (
                number,
                company_id,
                order_year
            )
            WHERE entry_mode = 'current'
            """
        )

        # Archival idempotency is tied to the physical source
        # location, independently from the legal order number
        # and independently from the free-form source_key.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                hr_personnel_order_historical_source_row_uidx
            ON hr_personnel_order (
                company_id,
                source_register_key,
                source_year,
                source_row
            )
            WHERE entry_mode = 'historical'
              AND source_register_key IS NOT NULL
              AND source_year IS NOT NULL
              AND source_row > 0
            """
        )

    @api.constrains(
        "number",
        "company_id",
        "order_year",
        "entry_mode",
    )
    def _check_current_order_number_unique(self):
        for order in self:
            if (
                order.entry_mode != "current"
                or not order.number
                or not order.company_id
                or not order.order_year
            ):
                continue

            duplicate = self.search_count(
                [
                    (
                        "id",
                        "!=",
                        order.id,
                    ),
                    (
                        "entry_mode",
                        "=",
                        "current",
                    ),
                    (
                        "number",
                        "=",
                        order.number,
                    ),
                    (
                        "company_id",
                        "=",
                        order.company_id.id,
                    ),
                    (
                        "order_year",
                        "=",
                        order.order_year,
                    ),
                ]
            )

            if duplicate:
                raise ValidationError(
                    _(
                        "Номер кадрового наказу %(number)s "
                        "вже використано для поточного "
                        "кадрового процесу %(year)s року."
                    )
                    % {
                        "number": order.number,
                        "year": order.order_year,
                    }
                )

    def write(self, vals):
        if (
            "entry_mode" in vals
            and self.filtered(
                lambda order: order.state != "draft"
            )
        ):
            raise UserError(
                _(
                    "Режим внесення можна змінювати "
                    "лише у чернетці."
                )
            )

        source_fields = {
            "source_register_key",
            "source_register_name",
            "source_year",
            "source_row",
            "source_key",
            "source_status",
            "source_text",
            "source_note",
        }

        if (
            source_fields.intersection(vals)
            and self.filtered(
                lambda order:
                    order.state
                    in {"posted", "cancelled"}
            )
        ):
            raise UserError(
                _(
                    "Джерельні реквізити "
                    "зареєстрованого історичного "
                    "наказу змінювати не можна."
                )
            )

        return super().write(vals)

    def action_submit(self):
        historical = self.filtered(
            lambda order:
                order.entry_mode == "historical"
        )

        if historical:
            raise UserError(
                _(
                    "Історичний наказ не проходить "
                    "сучасний маршрут погодження. "
                    "Використайте "
                    "«Зареєструвати історичний»."
                )
            )

        return super().action_submit()

    def action_post(self):
        historical = self.filtered(
            lambda order:
                order.entry_mode == "historical"
        )

        if historical:
            raise UserError(
                _(
                    "Історичний наказ проводиться "
                    "через операцію "
                    "«Зареєструвати історичний»."
                )
            )

        return super().action_post()

    def _validate_historical_source_contract(self):
        """
        Source-backed records use strict provenance and
        identity rules.

        Legacy/manual historical drafts without source_key
        remain supported, but the journal importer always
        supplies source_key and therefore receives the strict
        checks below.
        """
        for order in self:
            if not order.source_key:
                continue

            missing = []

            if not (
                order.source_register_key
                or ""
            ).strip():
                missing.append(
                    "source_register_key"
                )

            if not (
                order.source_register_name
                or ""
            ).strip():
                missing.append(
                    "source_register_name"
                )

            if order.source_year <= 0:
                missing.append(
                    "source_year"
                )

            if order.source_row <= 0:
                missing.append(
                    "source_row"
                )

            if not (
                order.source_text
                or ""
            ).strip():
                missing.append(
                    "source_text"
                )

            if missing:
                raise ValidationError(
                    _(
                        "Для історичного запису "
                        "%(number)s відсутні "
                        "джерельні реквізити: "
                        "%(fields)s."
                    )
                    % {
                        "number": order.number,
                        "fields":
                            ", ".join(missing),
                    }
                )

            if order.source_status == "annulled":
                continue

            for line in order.line_ids:
                line_missing = []

                if not (
                    line.source_line_key
                    or ""
                ).strip():
                    line_missing.append(
                        "source_line_key"
                    )

                if not (
                    line.source_text
                    or ""
                ).strip():
                    line_missing.append(
                        "source_text"
                    )

                if line_missing:
                    raise ValidationError(
                        _(
                            "Для рядка наказу "
                            "%(number)s відсутні "
                            "джерельні реквізити: "
                            "%(fields)s."
                        )
                        % {
                            "number":
                                order.number,
                            "fields":
                                ", ".join(
                                    line_missing
                                ),
                        }
                    )

                resolution = (
                    line.identity_resolution
                )

                if resolution in {
                    False,
                    "unresolved",
                    "ambiguous",
                }:
                    raise ValidationError(
                        _(
                            "Не можна реєструвати "
                            "%(number)s: особу "
                            "«%(person)s» ще не "
                            "ідентифіковано однозначно."
                        )
                        % {
                            "number":
                                order.number,
                            "person":
                                (
                                    line.source_person_name
                                    or line.employee_name
                                    or line.employee_id.name
                                    or "?"
                                ),
                        }
                    )

                if (
                    resolution == "matched"
                    and not line.employee_id
                ):
                    raise ValidationError(
                        _(
                            "Статус «зіставлено» "
                            "вимагає вибраної картки "
                            "працівника."
                        )
                    )

                if resolution == "new":
                    if line.employee_id:
                        raise ValidationError(
                            _(
                                "Для статусу «нова "
                                "історична картка» "
                                "employee_id має бути "
                                "порожнім."
                            )
                        )

                    if not (
                        (
                            line.employee_name
                            or ""
                        ).strip()
                        or (
                            line.source_person_name
                            or ""
                        ).strip()
                    ):
                        raise ValidationError(
                            _(
                                "Для нової історичної "
                                "особи вкажіть ПІБ "
                                "з первинного джерела."
                            )
                        )

        return True

    def action_register_historical(self):
        self._ensure_state({"draft"})

        invalid = self.filtered(
            lambda order:
                order.entry_mode != "historical"
        )

        if invalid:
            raise UserError(
                _(
                    "Операція доступна лише "
                    "для історичних наказів."
                )
            )

        self._validate_historical_source_contract()

        now = fields.Datetime.now()

        annulled = self.filtered(
            lambda order:
                order.source_status == "annulled"
        )

        for order in annulled:
            order.write(
                {
                    "state": "cancelled",
                    "cancelled_at": now,
                    "cancelled_by_id":
                        self.env.user.id,
                    "cancellation_reason":
                        (
                            order.source_note
                            or _(
                                "Анульовано "
                                "у первинному джерелі."
                            )
                        ),
                }
            )

        normal = self - annulled

        if normal:
            normal._ensure_has_lines()

            normal.mapped(
                "line_ids"
            )._validate_for_post()

            normal.write(
                {
                    "state": "posted",
                    "posted_at": now,
                    "posted_by_id":
                        self.env.user.id,
                }
            )

            for order in normal:
                lines = order.line_ids.sorted(
                    key=lambda line: (
                        line.effective_date,
                        line.sequence,
                        line.id,
                    )
                )

                for line in lines:
                    line.with_context(
                        **{
                            ENGINE_CONTEXT_KEY:
                                True
                        }
                    )._apply_from_order()

        return True



class HrPersonnelOrderLineHistorical(models.Model):
    _inherit = "hr.personnel.order.line"

    entry_mode = fields.Selection(
        related="order_id.entry_mode",
        string="Режим внесення",
        store=True,
        readonly=True,
        index=True,
    )

    historical_action_type = fields.Selection(
        ORDER_TYPE_SELECTION,
        string="Тип історичної кадрової дії",
        help=(
            "Для історичних наказів дозволяє "
            "в одному наказі мати кадрові дії "
            "різних типів."
        ),
    )

    action_type = fields.Selection(
        ORDER_TYPE_SELECTION,
        string="Тип кадрової дії",
        compute="_compute_action_type",
        store=True,
        readonly=True,
        index=True,
    )

    source_line_key = fields.Char(
        string="Ключ рядка джерела",
        copy=False,
        index=True,
    )

    source_person_name = fields.Char(
        string="ПІБ як у джерелі",
        copy=False,
        index=True,
    )

    source_text = fields.Text(
        string="Оригінальний текст фрагмента",
        copy=False,
    )

    interpretation_note = fields.Text(
        string="Нормалізоване тлумачення",
        copy=False,
        help=(
            "Пояснює, як текст джерела "
            "перетворено на кадрову дію. "
            "Оригінальний текст не змінюється."
        ),
    )

    identity_resolution = fields.Selection(
        IDENTITY_RESOLUTION_SELECTION,
        string="Ідентифікація особи",
        default="unresolved",
        copy=False,
        index=True,
    )

    identity_match_basis = fields.Text(
        string="Підстава зіставлення особи",
        copy=False,
    )

    @api.depends(
        "entry_mode",
        "order_type",
        "historical_action_type",
    )
    def _compute_action_type(self):
        for line in self:
            if (
                line.entry_mode == "historical"
                and line.historical_action_type
            ):
                line.action_type = (
                    line.historical_action_type
                )
            else:
                line.action_type = line.order_type

    def write(self, vals):
        protected_fields = {
            "historical_action_type",
            "source_line_key",
            "source_person_name",
            "source_text",
            "interpretation_note",
            "identity_resolution",
            "identity_match_basis",
        }

        if (
            protected_fields.intersection(vals)
            and not self.env.context.get(
                ENGINE_CONTEXT_KEY
            )
            and self.filtered(
                lambda line:
                    line.order_state
                    in {"posted", "cancelled"}
            )
        ):
            raise UserError(
                _(
                    "Джерельні та інтерпретаційні "
                    "дані історичного рядка "
                    "не можна змінювати після "
                    "реєстрації наказу."
                )
            )

        return super().write(vals)

    @api.constrains(
        "order_id",
        "source_line_key",
    )
    def _check_source_line_key_unique(self):
        for line in self:
            key = (
                line.source_line_key
                or ""
            ).strip()

            if not key:
                continue

            duplicate = self.search_count(
                [
                    (
                        "order_id",
                        "=",
                        line.order_id.id,
                    ),
                    (
                        "source_line_key",
                        "=",
                        key,
                    ),
                    (
                        "id",
                        "!=",
                        line.id,
                    ),
                ]
            )

            if duplicate:
                raise ValidationError(
                    _(
                        "Ключ рядка джерела "
                        "«%s» вже використаний "
                        "у цьому наказі."
                    )
                    % key
                )


    # ========================================================
    # Factual employment-period lookup
    # ========================================================

    def _historical_period_at_date(
        self,
        employee,
        target_date=False,
    ):
        self.ensure_one()

        if not employee:
            return self.env[
                "hr.personnel.employment.period"
            ]

        target_date = (
            target_date
            or self._event_effective_date()
        )

        Period = self.env[
            "hr.personnel.employment.period"
        ].sudo()

        # Prefer periods with an actually known start date.
        period = Period.search(
            [
                (
                    "employee_id",
                    "=",
                    employee.id,
                ),
                (
                    "company_id",
                    "=",
                    self.company_id.id,
                ),
                (
                    "date_start",
                    "!=",
                    False,
                ),
                (
                    "date_start",
                    "<=",
                    target_date,
                ),
                "|",
                (
                    "date_end",
                    "=",
                    False,
                ),
                (
                    "date_end",
                    ">=",
                    target_date,
                ),
            ],
            order="date_start desc, id desc",
            limit=1,
        )

        if period:
            return period

        # A person can first appear in the available archive
        # as a transfer, leave or dismissal. Such a period has
        # an unknown real start but a known first observation.
        return Period.search(
            [
                (
                    "employee_id",
                    "=",
                    employee.id,
                ),
                (
                    "company_id",
                    "=",
                    self.company_id.id,
                ),
                (
                    "date_start",
                    "=",
                    False,
                ),
                (
                    "first_observed_date",
                    "<=",
                    target_date,
                ),
                "|",
                (
                    "date_end",
                    "=",
                    False,
                ),
                (
                    "date_end",
                    ">=",
                    target_date,
                ),
            ],
            order=(
                "first_observed_date desc, "
                "id desc"
            ),
            limit=1,
        )

    def _historical_resolve_employee(self):
        self.ensure_one()

        if self.employee_id:
            return self.employee_id.sudo()

        if self.identity_resolution != "new":
            raise ValidationError(
                _(
                    "Історичну особу не "
                    "ідентифіковано однозначно."
                )
            )

        name = (
            (
                self.employee_name
                or ""
            ).strip()
            or (
                self.source_person_name
                or ""
            ).strip()
        )

        if not name:
            raise ValidationError(
                _(
                    "Для нової історичної особи "
                    "не вказано ПІБ."
                )
            )

        Employee = (
            self.env["hr.employee"]
            .sudo()
            .with_context(
                active_test=False,

                # OCA hr_employee_calendar_planning normally
                # requires every employee to have calendar
                # planning rows. A historical-only employee is
                # not operationally employed now and therefore
                # must not receive a current working calendar.
                skip_employee_calendars_required=True,
            )
        )

        # OCA hr_employee_id generates an employee number after
        # create() whenever identification_id is empty. Use a
        # transaction-local unique sentinel so that generator is
        # never invoked. It is cleared immediately after all
        # create() overrides have completed.
        temporary_identification = (
            "__historical_pending__:"
            f"{self.company_id.id}:{self.id}"
        )

        vals = {
            "name":
                name,
            "company_id":
                self.company_id.id,

            # Historical discovery must never make the person
            # operationally employed now.
            "active":
                False,

            "identification_id":
                temporary_identification,

            # ResourceMixin still creates the required
            # resource.resource, but without assigning a
            # current working calendar.
            "resource_calendar_id":
                False,

            "department_id":
                False,
            "job_id":
                False,
            "service_hire_date":
                False,
        }

        # Do not acquire a hard dependency on
        # hr_employee_calendar_planning. When it is installed,
        # explicitly suppress its default calendar_ids value.
        if "calendar_ids" in Employee._fields:
            vals["calendar_ids"] = []

        employee = Employee.create(
            vals
        )

        employee.invalidate_recordset()

        calendar_ids = (
            employee.calendar_ids
            if "calendar_ids" in employee._fields
            else False
        )

        # Check before clearing the sentinel. If another addon
        # has manufactured operational state, fail the whole
        # historical transaction instead of trying to clean up
        # generated calendars afterwards.
        if (
            employee.identification_id
            != temporary_identification
            or employee.resource_calendar_id
            or calendar_ids
            or employee.department_id
            or employee.job_id
            or employee.service_hire_date
            or employee.contract_id
            or employee.active
        ):
            raise ValidationError(
                _(
                    "Не вдалося створити історичну картку "
                    "%(employee)s без поточних кадрових "
                    "атрибутів. Операцію скасовано."
                )
                % {
                    "employee":
                        name,
                }
            )

        # NULL is the truthful value: the historical source does
        # not provide a current personnel number.
        employee.write(
            {
                "identification_id":
                    False,
            }
        )

        employee.invalidate_recordset()

        if (
            employee.identification_id
            or employee.resource_calendar_id
            or (
                "calendar_ids"
                in employee._fields
                and employee.calendar_ids
            )
            or employee.department_id
            or employee.job_id
            or employee.service_hire_date
            or employee.contract_id
            or employee.active
        ):
            raise ValidationError(
                _(
                    "Історична картка %(employee)s "
                    "отримала поточні кадрові атрибути. "
                    "Операцію скасовано."
                )
                % {
                    "employee":
                        name,
                }
            )

        return employee

    def _historical_create_partial_period(
        self,
        employee,
        target_date=False,
    ):
        self.ensure_one()

        target_date = (
            target_date
            or self._event_effective_date()
        )

        period = self._historical_period_at_date(
            employee,
            target_date,
        )

        if period:
            return period

        return (
            self.env[
                "hr.personnel.employment.period"
            ]
            .sudo()
            .with_context(
                **{ENGINE_CONTEXT_KEY: True}
            )
            .create(
                {
                    "employee_id":
                        employee.id,
                    "company_id":
                        self.company_id.id,
                    # Unknown start remains genuinely NULL.
                    "date_start":
                        False,
                    "date_end":
                        False,
                    "first_observed_date":
                        target_date,
                    "personnel_number":
                        (
                            self.employee_identification_id
                            or False
                        ),
                    "origin_order_line_id":
                        self.id,
                    "start_order_line_id":
                        False,
                    "end_order_line_id":
                        False,
                }
            )
        )

    def _historical_unknown_start_candidates(
        self,
        employee,
    ):
        """
        Periods first discovered from a later fact
        (transfer/leave/termination) may have date_start=NULL.
        A subsequently imported earlier hire can refine exactly
        one such period instead of creating an overlap.
        """
        self.ensure_one()

        if not employee:
            return self.env[
                "hr.personnel.employment.period"
            ]

        return (
            self.env[
                "hr.personnel.employment.period"
            ]
            .sudo()
            .search(
                [
                    (
                        "employee_id",
                        "=",
                        employee.id,
                    ),
                    (
                        "company_id",
                        "=",
                        self.company_id.id,
                    ),
                    (
                        "date_start",
                        "=",
                        False,
                    ),
                    (
                        "first_observed_date",
                        ">",
                        self.effective_date,
                    ),
                    "|",
                    (
                        "date_end",
                        "=",
                        False,
                    ),
                    (
                        "date_end",
                        ">=",
                        self.effective_date,
                    ),
                ],
                order=(
                    "first_observed_date asc, "
                    "id asc"
                ),
                limit=2,
            )
        )

    def _historical_events_as_of(
        self,
        period,
    ):
        """
        Return all immutable factual events that were effective
        not later than this line's historical effective date.

        State is reconstructed by replaying facts. We therefore
        do not depend on whichever event happened to be imported
        last into PostgreSQL.
        """
        self.ensure_one()

        if not period:
            return self.env[
                "hr.personnel.event"
            ]

        events = (
            self.env["hr.personnel.event"]
            .sudo()
            .search(
                [
                    (
                        "employment_period_id",
                        "=",
                        period.id,
                    ),
                    (
                        "status",
                        "=",
                        "applied",
                    ),
                    (
                        "effective_date",
                        "<=",
                        self._event_effective_date(),
                    ),
                ]
            )
        )

        # Registration source row provides deterministic
        # ordering for same-day historical facts. Legacy/manual
        # rows fall back to their database identifiers.
        return events.sorted(
            key=lambda event: (
                event.effective_date,
                (
                    event.order_id.source_row
                    or event.order_id.id
                ),
                (
                    event.order_line_id.sequence
                    or 0
                ),
                event.id,
            )
        )

    def _historical_empty_state(self):
        return {
            "department_id": False,
            "job_id": False,
            "resource_calendar_id": False,
            "wage": 0.0,
            "calendar_unknown": True,
            "wage_unknown": True,
        }

    def _historical_apply_line_to_state(
        self,
        state,
        line,
    ):
        """
        Apply one immutable source fact to an as-of state.

        This function is shared by ordinary historical lookup
        and snapshot reconciliation, so both paths use exactly
        the same temporal semantics.
        """
        result = dict(state)

        action_type = line.action_type

        if action_type == "hire":
            result["department_id"] = (
                line.department_id.id
                or False
            )

            result["job_id"] = (
                line.job_id.id
                or False
            )

            result[
                "resource_calendar_id"
            ] = (
                line.resource_calendar_id.id
                or False
            )

            result["calendar_unknown"] = (
                not bool(
                    line.resource_calendar_id
                )
            )

            result["wage"] = (
                line.wage
                if line.wage > 0
                else 0.0
            )

            result["wage_unknown"] = (
                line.wage <= 0
            )

            return result

        if (
            action_type
            in {
                "transfer",
                "department_change",
                "employment_condition_change",
            }
            and line.department_id
        ):
            result["department_id"] = (
                line.department_id.id
            )

        if (
            action_type
            in {
                "transfer",
                "position_change",
                "employment_condition_change",
            }
            and line.job_id
        ):
            result["job_id"] = (
                line.job_id.id
            )

        if (
            action_type
            in {
                "transfer",
                "schedule_change",
                "employment_condition_change",
            }
            and line.resource_calendar_id
        ):
            result[
                "resource_calendar_id"
            ] = (
                line.resource_calendar_id.id
            )

            result[
                "calendar_unknown"
            ] = False

        if (
            action_type == "salary_change"
            or (
                action_type
                in {
                    "transfer",
                    "employment_condition_change",
                }
                and line.wage > 0
            )
        ):
            result["wage"] = (
                line.wage
            )

            result[
                "wage_unknown"
            ] = False

        return result

    def _historical_state(
        self,
        period,
    ):
        """
        Reconstruct state as-of the current historical line by
        replaying immutable source facts in effective order.
        """
        self.ensure_one()

        state = (
            self._historical_empty_state()
        )

        for event in self._historical_events_as_of(
            period
        ):
            state = (
                self._historical_apply_line_to_state(
                    state,
                    event.order_line_id,
                )
            )

        return state

    def _historical_all_period_events(
        self,
        period,
    ):
        self.ensure_one()

        events = (
            self.env["hr.personnel.event"]
            .sudo()
            .search(
                [
                    (
                        "employment_period_id",
                        "=",
                        period.id,
                    ),
                    (
                        "status",
                        "=",
                        "applied",
                    ),
                ]
            )
        )

        return events.sorted(
            key=lambda event: (
                event.effective_date,
                (
                    event.order_id.source_year
                    or event.effective_date.year
                ),
                (
                    event.order_id.source_register_key
                    or ""
                ),
                (
                    event.order_id.source_row
                    or event.order_id.id
                ),
                (
                    event.order_line_id.sequence
                    or 0
                ),
                event.id,
            )
        )

    def _historical_reconcile_event_snapshots(
        self,
        period,
    ):
        """
        previous_*/new_* fields are derived temporal snapshots,
        not independent source facts.

        When an older order is imported after a newer one,
        recompute those snapshots for the whole factual period.
        Source data itself is never changed.
        """
        self.ensure_one()

        state = (
            self._historical_empty_state()
        )

        for event in (
            self._historical_all_period_events(
                period
            )
        ):
            previous = dict(state)

            state = (
                self._historical_apply_line_to_state(
                    state,
                    event.order_line_id,
                )
            )

            vals = {
                "previous_department_id":
                    previous["department_id"],
                "previous_job_id":
                    previous["job_id"],
                "previous_resource_calendar_id":
                    (
                        False
                        if previous[
                            "calendar_unknown"
                        ]
                        else previous[
                            "resource_calendar_id"
                        ]
                    ),
                "previous_wage":
                    (
                        0.0
                        if previous[
                            "wage_unknown"
                        ]
                        else previous["wage"]
                    ),
                "new_department_id":
                    state["department_id"],
                "new_job_id":
                    state["job_id"],
                "new_resource_calendar_id":
                    (
                        False
                        if state[
                            "calendar_unknown"
                        ]
                        else state[
                            "resource_calendar_id"
                        ]
                    ),
                "new_wage":
                    (
                        0.0
                        if state[
                            "wage_unknown"
                        ]
                        else state["wage"]
                    ),
                "l10n_ua_historical_calendar_unknown":
                    state["calendar_unknown"],
                "l10n_ua_historical_wage_unknown":
                    state["wage_unknown"],
            }

            event.with_context(
                personnel_event_maintenance=True
            ).write(vals)

    # ========================================================
    # Historical line snapshots
    # ========================================================

    def _historical_snapshot_values(
        self,
        employee,
    ):
        self.ensure_one()

        period = (
            self._historical_period_at_date(
                employee
            )
        )

        state = self._historical_state(
            period
        )

        return {
            "employee_name":
                employee.name,
            "employee_identification_id":
                (
                    period.personnel_number
                    if period
                    else False
                ),
            "previous_department_id":
                state["department_id"],
            "previous_job_id":
                state["job_id"],
            "previous_resource_calendar_id":
                (
                    False
                    if state["calendar_unknown"]
                    else state[
                        "resource_calendar_id"
                    ]
                ),
            "previous_wage":
                (
                    0.0
                    if state["wage_unknown"]
                    else state["wage"]
                ),
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for line, incoming in zip(
            records,
            vals_list,
        ):
            if (
                line.entry_mode != "historical"
                or not line.employee_id
            ):
                continue

            snapshot = (
                line._historical_snapshot_values(
                    line.employee_id
                )
            )

            updates = {}

            for field_name in (
                "employee_name",
                "employee_identification_id",
                "previous_department_id",
                "previous_job_id",
                "previous_resource_calendar_id",
                "previous_wage",
            ):
                if field_name not in incoming:
                    updates[field_name] = (
                        snapshot[field_name]
                    )

            if updates:
                line.with_context(
                    **{ENGINE_CONTEXT_KEY: True}
                ).write(updates)

        return records

    @api.onchange(
        "employee_id",
        "effective_date",
        "entry_mode",
    )
    def _onchange_historical_employee_snapshot(
        self,
    ):
        for line in self:
            if (
                line.entry_mode != "historical"
                or not line.employee_id
            ):
                continue

            snapshot = (
                line._historical_snapshot_values(
                    line.employee_id
                )
            )

            line.employee_name = snapshot[
                "employee_name"
            ]

            line.previous_department_id = snapshot[
                "previous_department_id"
            ]

            line.previous_job_id = snapshot[
                "previous_job_id"
            ]

            line.previous_resource_calendar_id = (
                snapshot[
                    "previous_resource_calendar_id"
                ]
            )

            line.previous_wage = snapshot[
                "previous_wage"
            ]

            if snapshot[
                "employee_identification_id"
            ]:
                line.employee_identification_id = (
                    snapshot[
                        "employee_identification_id"
                    ]
                )

            elif line.action_type != "hire":
                line.employee_identification_id = False

    # ========================================================
    # Employee reference constraint
    # ========================================================

    @api.constrains(
        "action_type",
        "employee_id",
        "employee_name",
        "source_person_name",
        "identity_resolution",
        "entry_mode",
    )
    def _check_employee_reference(self):
        current = self.filtered(
            lambda line:
                line.entry_mode != "historical"
        )

        historical = self - current

        if current:
            super(
                HrPersonnelOrderLineHistorical,
                current,
            )._check_employee_reference()

        for line in historical:
            if line.employee_id:
                continue

            name = (
                (
                    line.employee_name
                    or ""
                ).strip()
                or (
                    line.source_person_name
                    or ""
                ).strip()
            )

            if (
                line.action_type == "hire"
                and name
            ):
                continue

            if (
                line.identity_resolution == "new"
                and name
            ):
                continue

            raise ValidationError(
                _(
                    "Для історичної кадрової дії "
                    "виберіть працівника або "
                    "позначте особу як нову "
                    "історичну картку."
                )
            )

    # ========================================================
    # Historical validation
    # ========================================================

    def _validate_for_post(self):
        current = self.filtered(
            lambda line:
                line.entry_mode != "historical"
        )

        historical = self - current

        if current:
            super(
                HrPersonnelOrderLineHistorical,
                current,
            )._validate_for_post()

        for line in historical:
            if not line.effective_date:
                raise ValidationError(
                    _("Вкажіть дату кадрової дії.")
                )

            name = (
                (
                    line.employee_name
                    or ""
                ).strip()
                or (
                    line.source_person_name
                    or ""
                ).strip()
            )

            if not line.employee_id and not (
                line.identity_resolution == "new"
                and name
            ):
                if not (
                    line.action_type == "hire"
                    and name
                ):
                    raise ValidationError(
                        _(
                            "Історичну особу "
                            "не ідентифіковано."
                        )
                    )

            action_type = line.action_type

            if action_type == "leave":
                if (
                    not line.leave_type_id
                    or not line.leave_date_from
                ):
                    raise ValidationError(
                        _(
                            "Для історичної відпустки "
                            "вкажіть вид та дату початку. "
                            "Дата завершення може "
                            "залишатися невідомою."
                        )
                    )

                if (
                    line.leave_date_to
                    and line.leave_date_to
                    < line.leave_date_from
                ):
                    raise ValidationError(
                        _(
                            "Дата завершення відпустки "
                            "не може передувати "
                            "даті початку."
                        )
                    )

            elif (
                action_type == "position_change"
                and not line.job_id
            ):
                raise ValidationError(
                    _(
                        "Для зміни посади "
                        "вкажіть нову посаду."
                    )
                )

            elif (
                action_type == "department_change"
                and not line.department_id
            ):
                raise ValidationError(
                    _(
                        "Для зміни підрозділу "
                        "вкажіть новий підрозділ."
                    )
                )

            elif (
                action_type == "schedule_change"
                and not line.resource_calendar_id
            ):
                raise ValidationError(
                    _(
                        "Для зміни графіка "
                        "вкажіть новий графік."
                    )
                )

            elif (
                action_type == "salary_change"
                and line.wage <= 0
            ):
                raise ValidationError(
                    _(
                        "Для зміни оплати праці "
                        "вкажіть додатний оклад."
                    )
                )

            elif (
                action_type == "transfer"
                and not any(
                    [
                        line.department_id,
                        line.job_id,
                        line.resource_calendar_id,
                        line.professional_category_id,
                        line.wage > 0,
                        line.work_type,
                        line.hire_condition,
                        line.weekly_hours > 0,
                        line.work_conditions,
                        line.allowance_note,
                    ]
                )
            ):
                raise ValidationError(
                    _(
                        "Для історичного "
                        "переведення вкажіть "
                        "хоча б одну змінену умову."
                    )
                )

        return True

    # ========================================================
    # Historical event state
    # ========================================================

    def _event_effective_date(self):
        self.ensure_one()

        if (
            self.action_type == "leave"
            and self.leave_date_from
        ):
            return self.leave_date_from

        return self.effective_date

    def _event_base_values(
        self,
        employee=False,
        status="planned",
    ):
        vals = super()._event_base_values(
            employee=employee,
            status=status,
        )

        if self.entry_mode != "historical":
            return vals

        target_employee = (
            employee
            or self.employee_id
        )

        period = (
            self.employment_period_id
            or (
                self._historical_period_at_date(
                    target_employee
                )
                if target_employee
                else False
            )
        )

        vals[
            "employee_identification_id"
        ] = (
            self.employee_identification_id
            or (
                period.personnel_number
                if period
                else False
            )
            or False
        )

        return vals

    def _actual_state(
        self,
        employee,
        contract=False,
    ):
        if self.entry_mode != "historical":
            return super()._actual_state(
                employee,
                contract=contract,
            )

        period = (
            self.employment_period_id
            or self._historical_period_at_date(
                employee
            )
        )

        state = self._historical_state(
            period
        )

        return {
            "previous_department_id":
                state["department_id"],
            "previous_job_id":
                state["job_id"],
            "previous_resource_calendar_id":
                (
                    False
                    if state["calendar_unknown"]
                    else state[
                        "resource_calendar_id"
                    ]
                ),
            "previous_wage":
                (
                    0.0
                    if state["wage_unknown"]
                    else state["wage"]
                ),
        }

    def _finalize_event(
        self,
        event,
        employee,
        contract=False,
        leave=False,
        previous=None,
        period=False,
    ):
        if self.entry_mode != "historical":
            return super()._finalize_event(
                event,
                employee,
                contract=contract,
                leave=leave,
                previous=previous,
            )

        period = (
            period
            or self.employment_period_id
            or self._historical_period_at_date(
                employee
            )
        )

        state = self._historical_state(
            period
        )

        previous = (
            previous
            or {
                "previous_department_id":
                    state["department_id"],
                "previous_job_id":
                    state["job_id"],
                "previous_resource_calendar_id":
                    (
                        False
                        if state["calendar_unknown"]
                        else state[
                            "resource_calendar_id"
                        ]
                    ),
                "previous_wage":
                    (
                        0.0
                        if state["wage_unknown"]
                        else state["wage"]
                    ),
            }
        )

        new_department_id = state[
            "department_id"
        ]

        new_job_id = state[
            "job_id"
        ]

        new_resource_calendar_id = state[
            "resource_calendar_id"
        ]

        new_wage = state["wage"]

        calendar_unknown = state[
            "calendar_unknown"
        ]

        wage_unknown = state[
            "wage_unknown"
        ]

        action_type = self.action_type

        if action_type == "hire":
            new_department_id = (
                self.department_id.id
                or False
            )

            new_job_id = (
                self.job_id.id
                or False
            )

            new_resource_calendar_id = (
                self.resource_calendar_id.id
                or False
            )

            new_wage = (
                self.wage
                if self.wage > 0
                else 0.0
            )

            calendar_unknown = not bool(
                self.resource_calendar_id
            )

            wage_unknown = (
                self.wage <= 0
            )

        elif action_type in {
            "transfer",
            "position_change",
            "department_change",
            "salary_change",
            "schedule_change",
            "employment_condition_change",
        }:
            if (
                action_type
                in {
                    "transfer",
                    "department_change",
                    "employment_condition_change",
                }
                and self.department_id
            ):
                new_department_id = (
                    self.department_id.id
                )

            if (
                action_type
                in {
                    "transfer",
                    "position_change",
                    "employment_condition_change",
                }
                and self.job_id
            ):
                new_job_id = self.job_id.id

            if (
                action_type
                in {
                    "transfer",
                    "schedule_change",
                    "employment_condition_change",
                }
                and self.resource_calendar_id
            ):
                new_resource_calendar_id = (
                    self.resource_calendar_id.id
                )

                calendar_unknown = False

            if (
                action_type == "salary_change"
                or (
                    action_type
                    in {
                        "transfer",
                        "employment_condition_change",
                    }
                    and self.wage > 0
                )
            ):
                new_wage = self.wage
                wage_unknown = False

        vals = dict(previous)

        vals.update(
            {
                "employee_id":
                    employee.id,
                "employee_identification_id":
                    (
                        self.employee_identification_id
                        or (
                            period.personnel_number
                            if period
                            else False
                        )
                        or False
                    ),
                "employment_period_id":
                    period.id
                    if period
                    else False,
                "status":
                    "applied",
                "new_department_id":
                    new_department_id,
                "new_job_id":
                    new_job_id,
                "new_resource_calendar_id":
                    (
                        False
                        if calendar_unknown
                        else new_resource_calendar_id
                    ),
                "new_wage":
                    (
                        0.0
                        if wage_unknown
                        else new_wage
                    ),
                "l10n_ua_historical_calendar_unknown":
                    calendar_unknown,
                "l10n_ua_historical_wage_unknown":
                    wage_unknown,

                # Historical reconstruction must never
                # create operational contract/leave links.
                "contract_id":
                    False,
                "leave_id":
                    False,
                "applied_at":
                    fields.Datetime.now(),
                "applied_by_id":
                    self.env.user.id,
            }
        )

        event.sudo().with_context(
            personnel_event_maintenance=True
        ).write(vals)

        if period:
            self._historical_reconcile_event_snapshots(
                period
            )

    def _mark_applied(
        self,
        employee,
        contract=False,
        leave=False,
        period=False,
    ):
        if self.entry_mode != "historical":
            return super()._mark_applied(
                employee,
                contract=contract,
                leave=leave,
            )

        period = (
            period
            or self.employment_period_id
            or self._historical_period_at_date(
                employee
            )
        )

        personnel_number = (
            self.employee_identification_id
            or (
                period.personnel_number
                if period
                else False
            )
            or False
        )

        self.with_context(
            **{ENGINE_CONTEXT_KEY: True}
        ).sudo().write(
            {
                "employee_id":
                    employee.id,
                "employee_name":
                    employee.name,
                "employee_identification_id":
                    personnel_number,
                "employment_period_id":
                    (
                        period.id
                        if period
                        else False
                    ),

                # Never bind historical facts to
                # operational records.
                "contract_id":
                    False,
                "leave_id":
                    False,

                "application_state":
                    "applied",
                "application_error":
                    False,
                "last_application_attempt_at":
                    fields.Datetime.now(),
                "applied_at":
                    fields.Datetime.now(),
                "applied_by_id":
                    self.env.user.id,
            }
        )

    # ========================================================
    # Historical hire
    # ========================================================

    def _apply_hire(self, event):
        if self.entry_mode != "historical":
            return super()._apply_hire(event)

        self.ensure_one()

        employee = (
            self._historical_resolve_employee()
        )

        # A hire cannot silently overlap a period already known
        # to cover that date. If it does, the source history
        # must be resolved explicitly instead of fabricating an
        # employment boundary.
        existing = (
            self._historical_period_at_date(
                employee,
                self.effective_date,
            )
        )

        if existing:
            raise ValidationError(
                _(
                    "На дату %(date)s для працівника "
                    "%(employee)s вже існує фактичний "
                    "трудовий період %(period)s. "
                    "Не можна автоматично створити "
                    "перекривний період."
                )
                % {
                    "date":
                        self.effective_date,
                    "employee":
                        employee.name,
                    "period":
                        existing.display_name,
                }
            )

        candidates = (
            self._historical_unknown_start_candidates(
                employee
            )
        )

        if len(candidates) > 1:
            raise ValidationError(
                _(
                    "Для працівника %(employee)s знайдено "
                    "кілька трудових періодів з невідомою "
                    "датою початку після %(date)s. "
                    "Автоматичне зіставлення неоднозначне."
                )
                % {
                    "employee":
                        employee.name,
                    "date":
                        self.effective_date,
                }
            )

        period = candidates[:1]

        if period:
            intervening = (
                self.env[
                    "hr.personnel.employment.period"
                ]
                .sudo()
                .search(
                    [
                        (
                            "employee_id",
                            "=",
                            employee.id,
                        ),
                        (
                            "company_id",
                            "=",
                            self.company_id.id,
                        ),
                        (
                            "id",
                            "!=",
                            period.id,
                        ),
                        (
                            "date_start",
                            "!=",
                            False,
                        ),
                        (
                            "date_start",
                            ">",
                            self.effective_date,
                        ),
                        (
                            "date_start",
                            "<=",
                            period.first_observed_date,
                        ),
                    ],
                    limit=1,
                )
            )

            if intervening:
                raise ValidationError(
                    _(
                        "Не можна автоматично уточнити "
                        "дату початку періоду %(period)s: "
                        "між %(hire_date)s та першою "
                        "відомою датою цього періоду вже "
                        "існує інший трудовий період "
                        "%(other)s."
                    )
                    % {
                        "period":
                            period.display_name,
                        "hire_date":
                            self.effective_date,
                        "other":
                            intervening.display_name,
                    }
                )

            vals = {
                "date_start":
                    self.effective_date,
                "first_observed_date":
                    min(
                        period.first_observed_date,
                        self.effective_date,
                    ),
                "origin_order_line_id":
                    self.id,
                "start_order_line_id":
                    self.id,
            }

            if self.employee_identification_id:
                if (
                    period.personnel_number
                    and period.personnel_number
                    != self.employee_identification_id
                ):
                    raise ValidationError(
                        _(
                            "Табельний номер %(new)s "
                            "суперечить уже відомому "
                            "номеру %(old)s цього "
                            "трудового періоду."
                        )
                        % {
                            "new":
                                self.employee_identification_id,
                            "old":
                                period.personnel_number,
                        }
                    )

                vals[
                    "personnel_number"
                ] = (
                    self.employee_identification_id
                )

            period.with_context(
                **{ENGINE_CONTEXT_KEY: True}
            ).write(vals)

        else:
            period = (
                self.env[
                    "hr.personnel.employment.period"
                ]
                .sudo()
                .with_context(
                    **{ENGINE_CONTEXT_KEY: True}
                )
                .create(
                    {
                        "employee_id":
                            employee.id,
                        "company_id":
                            self.company_id.id,
                        "date_start":
                            self.effective_date,

                        # Never manufacture an end date.
                        "date_end":
                            False,

                        "first_observed_date":
                            self.effective_date,
                        "personnel_number":
                            (
                                self.employee_identification_id
                                or False
                            ),
                        "origin_order_line_id":
                            self.id,
                        "start_order_line_id":
                            self.id,
                        "end_order_line_id":
                            False,
                    }
                )
            )

        previous = {
            "previous_department_id": False,
            "previous_job_id": False,
            "previous_resource_calendar_id": False,
            "previous_wage": 0.0,
        }

        self._finalize_event(
            event,
            employee,
            period=period,
            previous=previous,
        )

        self._mark_applied(
            employee,
            period=period,
        )

    # ========================================================
    # Historical employment changes
    # ========================================================

    def _apply_employment_change(
        self,
        event,
    ):
        if self.entry_mode != "historical":
            return super()._apply_employment_change(
                event
            )

        self.ensure_one()

        employee = (
            self._historical_resolve_employee()
        )

        period = (
            self._historical_period_at_date(
                employee
            )
            or self._historical_create_partial_period(
                employee
            )
        )

        previous = self._actual_state(
            employee
        )

        self._finalize_event(
            event,
            employee,
            period=period,
            previous=previous,
        )

        self._mark_applied(
            employee,
            period=period,
        )

    # ========================================================
    # Historical leave / absence
    # ========================================================

    def _apply_historical_leave(
        self,
        event,
    ):
        self.ensure_one()

        employee = (
            self._historical_resolve_employee()
        )

        period = (
            self._historical_period_at_date(
                employee,
                self._event_effective_date(),
            )
            or self._historical_create_partial_period(
                employee,
                self._event_effective_date(),
            )
        )

        previous = self._actual_state(
            employee
        )

        # Deliberately event-only. Historical reconstruction
        # must not create/validate operational leave records.
        self._finalize_event(
            event,
            employee,
            period=period,
            previous=previous,
        )

        self._mark_applied(
            employee,
            period=period,
        )

    # ========================================================
    # Historical termination
    # ========================================================

    def _apply_termination(
        self,
        event,
    ):
        if self.entry_mode != "historical":
            return super()._apply_termination(
                event
            )

        self.ensure_one()

        employee = (
            self._historical_resolve_employee()
        )

        period = (
            self._historical_period_at_date(
                employee,
                self.effective_date,
            )
            or self._historical_create_partial_period(
                employee,
                self.effective_date,
            )
        )

        previous = self._actual_state(
            employee
        )

        if (
            period.date_end
            and period.date_end
            != self.effective_date
        ):
            raise ValidationError(
                _(
                    "Трудовий період %(period)s вже має "
                    "підтверджену дату завершення %(date)s."
                )
                % {
                    "period":
                        period.display_name,
                    "date":
                        period.date_end,
                }
            )

        if not period.date_end:
            period.with_context(
                **{ENGINE_CONTEXT_KEY: True}
            ).write(
                {
                    "date_end":
                        self.effective_date,
                    "end_order_line_id":
                        self.id,
                }
            )

        # Current hr.employee.active / departure fields
        # intentionally remain untouched.
        self._finalize_event(
            event,
            employee,
            period=period,
            previous=previous,
        )

        self._mark_applied(
            employee,
            period=period,
        )

    # ========================================================
    # Other historical personnel facts
    # ========================================================

    def _apply_historical_generic(
        self,
        event,
    ):
        self.ensure_one()

        employee = (
            self._historical_resolve_employee()
        )

        period = (
            self._historical_period_at_date(
                employee
            )
            or self._historical_create_partial_period(
                employee
            )
        )

        previous = self._actual_state(
            employee
        )

        self._finalize_event(
            event,
            employee,
            period=period,
            previous=previous,
        )

        self._mark_applied(
            employee,
            period=period,
        )

    # ========================================================
    # Historical dispatcher
    # ========================================================

    def _apply_from_order(self):
        current = self.filtered(
            lambda line:
                line.entry_mode != "historical"
        )

        historical = self - current

        if current:
            super(
                HrPersonnelOrderLineHistorical,
                current,
            )._apply_from_order()

        for line in historical:
            if line.order_state != "posted":
                raise UserError(
                    _(
                        "Застосовувати можна "
                        "лише зареєстрований "
                        "історичний наказ."
                    )
                )

            if (
                line.application_state
                == "applied"
            ):
                continue

            line.with_context(
                **{ENGINE_CONTEXT_KEY: True}
            ).sudo().write(
                {
                    "last_application_attempt_at":
                        fields.Datetime.now(),
                    "application_error":
                        False,
                }
            )

            event = (
                line._ensure_planned_event()
            )

            action_type = line.action_type

            if action_type == "hire":
                line._apply_hire(event)

            elif action_type in {
                "transfer",
                "position_change",
                "department_change",
                "salary_change",
                "schedule_change",
                "employment_condition_change",
            }:
                line._apply_employment_change(
                    event
                )

            elif action_type == "leave":
                line._apply_historical_leave(
                    event
                )

            elif action_type == "termination":
                line._apply_termination(
                    event
                )

            else:
                line._apply_historical_generic(
                    event
                )

        return True


class HrPersonnelEventHistorical(models.Model):
    _inherit = "hr.personnel.event"

    l10n_ua_historical_calendar_unknown = fields.Boolean(
        string="Графік роботи на дату події не встановлено",
        readonly=True,
        copy=False,
    )

    l10n_ua_historical_wage_unknown = fields.Boolean(
        string="Оклад на дату події не встановлено",
        readonly=True,
        copy=False,
    )

    event_type = fields.Selection(
        ORDER_TYPE_SELECTION,
        related="order_line_id.action_type",
        store=True,
        string="Тип події",
        index=True,
    )
