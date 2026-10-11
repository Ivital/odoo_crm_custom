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
        return " ".join(
            (name or "").split()
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


class HrContractHistoricalReconstruction(models.Model):
    _inherit = "hr.contract"

    l10n_ua_historical_reconstruction = fields.Boolean(
        string="Історично відновлений трудовий період",
        readonly=True,
        copy=False,
        index=True,
    )

    l10n_ua_end_date_inferred = fields.Boolean(
        string="Дата завершення періоду попередня",
        readonly=True,
        copy=False,
        help=(
            "Дата завершення технічно виведена з початку "
            "наступного відомого трудового періоду. "
            "Це не підтверджена дата звільнення."
        ),
    )

    l10n_ua_end_date_unresolved = fields.Boolean(
        string="Дата завершення періоду не встановлена",
        readonly=True,
        copy=False,
        help=(
            "Історичний трудовий період відомий, але за "
            "наявними документами дата його завершення "
            "ще не встановлена."
        ),
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
                    if line.action_type != "hire":
                        raise ValidationError(
                            _(
                                "Нову історичну картку "
                                "можна створити лише "
                                "подією прийняття."
                            )
                        )

                    if line.employee_id:
                        raise ValidationError(
                            _(
                                "Для статусу «нова "
                                "історична картка» "
                                "employee_id має бути "
                                "порожнім."
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
    # Temporal contract lookup
    # ========================================================

    def _historical_contract_at_date(
        self,
        employee,
        target_date=False,
    ):
        self.ensure_one()

        if not employee:
            return self.env["hr.contract"]

        target_date = (
            target_date
            or self._event_effective_date()
        )

        return self.env["hr.contract"].sudo().search(
            [
                ("employee_id", "=", employee.id),
                ("company_id", "=", self.company_id.id),
                "|",
                ("state", "in", ["open", "close"]),
                "&",
                ("state", "=", "draft"),
                (
                    "l10n_ua_historical_reconstruction",
                    "=",
                    True,
                ),
                ("date_start", "<=", target_date),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", target_date),
            ],
            order="date_start desc, id desc",
            limit=1,
        )

    def _historical_next_contract(
        self,
        employee,
        after_date=False,
    ):
        self.ensure_one()

        if not employee:
            return self.env["hr.contract"]

        after_date = (
            after_date
            or self.effective_date
        )

        return self.env["hr.contract"].sudo().search(
            [
                ("employee_id", "=", employee.id),
                ("company_id", "=", self.company_id.id),
                "|",
                ("state", "in", ["open", "close"]),
                "&",
                ("state", "=", "draft"),
                (
                    "l10n_ua_historical_reconstruction",
                    "=",
                    True,
                ),
                ("date_start", ">", after_date),
            ],
            order="date_start asc, id asc",
            limit=1,
        )

    def _current_contract(self, employee):
        self.ensure_one()

        if self.entry_mode == "historical":
            return self._historical_contract_at_date(
                employee
            )

        return super()._current_contract(employee)

    def _historical_protected_current_baseline(
        self,
        employee,
    ):
        """
        Production may already contain an active employee card
        with current personnel number / position but without
        hr.contract. Such a card is the protected current state,
        not an empty historical employee.
        """
        self.ensure_one()

        if not employee:
            return False

        return bool(
            employee.active
            and not employee.contract_id
            and (
                employee.identification_id
                or employee.service_hire_date
                or employee.department_id
                or employee.job_id
            )
        )

    def _historical_matches_current_baseline(
        self,
        employee,
    ):
        """
        When we eventually reach the documented current rehire,
        materialize that period as the employee's real current
        contract instead of keeping the imported baseline
        permanently contract-less.
        """
        self.ensure_one()

        if not self._historical_protected_current_baseline(
            employee
        ):
            return False

        if not employee.service_hire_date:
            return False

        if (
            employee.service_hire_date
            != self.effective_date
        ):
            return False

        if (
            self.employee_identification_id
            and employee.identification_id
            and self.employee_identification_id
            != employee.identification_id
        ):
            return False

        return True

    # ========================================================
    # Historical line snapshots
    # ========================================================

    def _historical_snapshot_values(
        self,
        employee,
    ):
        self.ensure_one()

        contract = (
            self._historical_contract_at_date(
                employee
            )
        )

        if not contract:
            return {
                "employee_name": employee.name,
                "employee_identification_id": False,
                "previous_department_id": False,
                "previous_job_id": False,
                "previous_resource_calendar_id": False,
                "previous_wage": 0.0,
            }

        return {
            "employee_name": employee.name,
            "employee_identification_id": (
                contract.l10n_ua_personnel_number
                or False
            ),
            "previous_department_id": (
                contract.department_id.id
                or False
            ),
            "previous_job_id": (
                contract.job_id.id
                or False
            ),
            "previous_resource_calendar_id": (
                contract.resource_calendar_id.id
                or False
            ),
            "previous_wage": contract.wage,
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
    )
    def _check_employee_reference(self):
        for line in self:
            if line.action_type == "hire":
                if (
                    not line.employee_id
                    and not (
                        line.employee_name or ""
                    ).strip()
                ):
                    raise ValidationError(
                        _(
                            "Для наказу про прийняття "
                            "вкажіть існуючого "
                            "працівника або ПІБ."
                        )
                    )

            elif not line.employee_id:
                raise ValidationError(
                    _(
                        "Для цієї кадрової дії "
                        "необхідно вибрати працівника."
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

            action_type = line.action_type

            if action_type == "hire":
                if (
                    not line.employee_id
                    and not (
                        line.employee_name or ""
                    ).strip()
                ):
                    raise ValidationError(
                        _(
                            "Для історичного "
                            "прийняття вкажіть "
                            "працівника або ПІБ."
                        )
                    )

            elif action_type == "leave":
                if (
                    not line.employee_id
                    or not line.leave_type_id
                    or not line.leave_date_from
                    or not line.leave_date_to
                ):
                    raise ValidationError(
                        _(
                            "Для історичної відпустки "
                            "вкажіть працівника, вид "
                            "та період відпустки."
                        )
                    )

            elif action_type == "termination":
                if not line.employee_id:
                    raise ValidationError(
                        _(
                            "Для історичного "
                            "звільнення виберіть "
                            "працівника."
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
    # Event state at historical date
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

        contract = (
            self._historical_contract_at_date(
                target_employee
            )
            if target_employee
            else False
        )

        vals[
            "employee_identification_id"
        ] = (
            self.employee_identification_id
            or (
                contract.l10n_ua_personnel_number
                if contract
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

        contract = (
            contract
            or self._historical_contract_at_date(
                employee
            )
        )

        if not contract:
            return {
                "previous_department_id": False,
                "previous_job_id": False,
                "previous_resource_calendar_id": False,
                "previous_wage": 0.0,
            }

        return {
            "previous_department_id": (
                contract.department_id.id
                or False
            ),
            "previous_job_id": (
                contract.job_id.id
                or False
            ),
            "previous_resource_calendar_id": (
                contract.resource_calendar_id.id
                or False
            ),
            "previous_wage": contract.wage,
        }

    def _finalize_event(
        self,
        event,
        employee,
        contract=False,
        leave=False,
        previous=None,
    ):
        if self.entry_mode != "historical":
            return super()._finalize_event(
                event,
                employee,
                contract=contract,
                leave=leave,
                previous=previous,
            )

        previous = (
            previous
            or self._actual_state(
                employee,
                contract=contract,
            )
        )

        vals = dict(previous)

        vals.update(
            {
                "employee_id": employee.id,
                "employee_identification_id": (
                    self.employee_identification_id
                    or (
                        contract.l10n_ua_personnel_number
                        if contract
                        else False
                    )
                    or False
                ),
                "status": "applied",
                "new_department_id": (
                    contract.department_id.id
                    if contract
                    else False
                ),
                "new_job_id": (
                    contract.job_id.id
                    if contract
                    else False
                ),
                "new_resource_calendar_id": (
                    contract.resource_calendar_id.id
                    if contract
                    else False
                ),
                "new_wage": (
                    contract.wage
                    if contract
                    else self.wage
                ),
                "contract_id": (
                    contract.id
                    if contract
                    else False
                ),
                "leave_id": (
                    leave.id
                    if leave
                    else False
                ),
                "applied_at":
                    fields.Datetime.now(),
                "applied_by_id":
                    self.env.user.id,
            }
        )

        event.sudo().with_context(
            personnel_event_maintenance=True
        ).write(vals)

    def _mark_applied(
        self,
        employee,
        contract=False,
        leave=False,
    ):
        if self.entry_mode != "historical":
            return super()._mark_applied(
                employee,
                contract=contract,
                leave=leave,
            )

        personnel_number = (
            self.employee_identification_id
            or (
                contract.l10n_ua_personnel_number
                if contract
                else False
            )
            or False
        )

        self.with_context(
            **{ENGINE_CONTEXT_KEY: True}
        ).sudo().write(
            {
                "employee_id": employee.id,
                "employee_name": employee.name,
                "employee_identification_id":
                    personnel_number,
                "contract_id": (
                    contract.id
                    if contract
                    else False
                ),
                "leave_id": (
                    leave.id
                    if leave
                    else False
                ),
                "application_state": "applied",
                "application_error": False,
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

        Employee = (
            self.env["hr.employee"]
            .sudo()
            .with_context(active_test=False)
        )

        Contract = self.env["hr.contract"].sudo()

        employee = (
            self.employee_id.sudo()
            if self.employee_id
            else False
        )

        employee_existed = bool(employee)

        if not employee:
            # Historical-only people must not appear as
            # employees working today merely because we are
            # currently reconstructing an old year.
            employee = Employee.create(
                {
                    "name":
                        self.employee_name.strip(),
                    "company_id":
                        self.company_id.id,
                    "active": False,
                }
            )

        protected_current = (
            employee_existed
            and self._historical_protected_current_baseline(
                employee
            )
        )

        matches_current = (
            protected_current
            and self._historical_matches_current_baseline(
                employee
            )
        )

        existing = (
            self._historical_contract_at_date(
                employee,
                self.effective_date,
            )
        )

        if existing:
            raise ValidationError(
                _(
                    "На дату %(date)s працівник "
                    "%(employee)s вже має "
                    "трудовий період %(contract)s."
                )
                % {
                    "date": self.effective_date,
                    "employee": employee.name,
                    "contract":
                        existing.display_name,
                }
            )

        next_contract = (
            self._historical_next_contract(
                employee,
                self.effective_date,
            )
        )

        date_end = self.employment_end_date

        # Never infer or manufacture the end of an old
        # employment period. A later contract is evidence
        # only that a later period exists, not evidence of
        # the legal dismissal date of this one.
        if (
            next_contract
            and date_end
            and date_end >= next_contract.date_start
        ):
            raise ValidationError(
                _(
                    "Історичний трудовий період "
                    "перетинається з наступним "
                    "контрактом %s."
                )
                % next_contract.display_name
            )

        # The imported modern employee card can itself provide
        # a known current start date. Again: validate an
        # explicit historical end, but never infer one.
        if (
            protected_current
            and not matches_current
            and employee.service_hire_date
            and employee.service_hire_date
            > self.effective_date
            and date_end
            and date_end
            >= employee.service_hire_date
        ):
            raise ValidationError(
                _(
                    "Історичний трудовий період "
                    "перетинається з поточним "
                    "періодом працівника, який "
                    "починається %s."
                )
                % employee.service_hire_date
            )

        if matches_current:
            today = fields.Date.context_today(self)

            contract_state = (
                "open"
                if (
                    not date_end
                    or date_end >= today
                )
                else "close"
            )

            end_date_unresolved = False

        elif date_end:
            contract_state = "close"
            end_date_unresolved = False

        else:
            # Unknown end stays NULL. Draft keeps an
            # unresolved historical period out of Odoo's
            # current operational contract semantics.
            contract_state = "draft"
            end_date_unresolved = True

        personnel_number = (
            self.employee_identification_id
            or (
                employee.identification_id
                if matches_current
                else False
            )
            or False
        )

        contract_vals = {
            "name": (
                f"{self.order_id.number} — "
                f"{employee.name}"
            ),
            "employee_id": employee.id,
            "company_id": self.company_id.id,
            "date_start": self.effective_date,
            "date_end": date_end,
            "trial_date_end":
                self.trial_date_end,
            "wage": self.wage or 0.0,
            "state": contract_state,
            "l10n_ua_personnel_order_line_id":
                self.id,
            "l10n_ua_hire_order_line_id":
                self.id,
            "l10n_ua_personnel_number":
                personnel_number,
            "l10n_ua_work_type": (
                self.work_type or "main"
            ),
            "l10n_ua_hire_condition": (
                self.hire_condition or False
            ),
            "l10n_ua_weekly_hours":
                self.weekly_hours,
            "l10n_ua_work_conditions": (
                self.work_conditions or False
            ),
            "l10n_ua_allowance_note": (
                self.allowance_note or False
            ),
            "l10n_ua_historical_reconstruction":
                True,
            # 3.15 policy: never synthesize date_end.
            "l10n_ua_end_date_inferred":
                False,
            "l10n_ua_end_date_unresolved":
                end_date_unresolved,
        }

        contract = Contract.create(
            contract_vals
        )

        # hr.contract derives these fields from the employee
        # on create. Historical facts must overwrite those
        # current-card defaults.
        historical_contract_vals = {
            "department_id": (
                self.department_id.id
                if self.department_id
                else (
                    employee.department_id.id
                    if (
                        matches_current
                        and employee.department_id
                    )
                    else False
                )
            ),
            "job_id": (
                self.job_id.id
                if self.job_id
                else (
                    employee.job_id.id
                    if (
                        matches_current
                        and employee.job_id
                    )
                    else False
                )
            ),
            "resource_calendar_id": (
                self.resource_calendar_id.id
                if self.resource_calendar_id
                else (
                    employee.resource_calendar_id.id
                    if (
                        matches_current
                        and employee.resource_calendar_id
                    )
                    else False
                )
            ),
        }

        if self.professional_category_id:
            historical_contract_vals[
                "professional_category_id"
            ] = (
                self.professional_category_id.id
            )

        contract.write(
            historical_contract_vals
        )

        if matches_current:
            # Only an explicitly matched modern period may
            # become the operational current contract.
            employee.write(
                {
                    "contract_id": contract.id,
                }
            )

        # For every other historical hire we intentionally do
        # NOT write active/current personnel number/current
        # department/current job/current hire date to
        # hr.employee. Those are present-day operational
        # fields, not a reconstruction scratchpad.

        previous = {
            "previous_department_id": False,
            "previous_job_id": False,
            "previous_resource_calendar_id": False,
            "previous_wage": 0.0,
        }

        self._finalize_event(
            event,
            employee,
            contract=contract,
            previous=previous,
        )

        self._mark_applied(
            employee,
            contract=contract,
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

        employee = self.employee_id.sudo()

        contract = (
            self._historical_contract_at_date(
                employee
            )
        )

        if not contract:
            raise ValidationError(
                _(
                    "Для історичної кадрової "
                    "зміни не знайдено "
                    "трудовий період працівника "
                    "%s на дату %s."
                )
                % (
                    employee.name,
                    self.effective_date,
                )
            )

        previous = self._actual_state(
            employee,
            contract=contract,
        )

        action_type = self.action_type

        contract_vals = {
            "l10n_ua_personnel_order_line_id":
                self.id,
        }

        employee_vals = {}

        if (
            action_type
            in {
                "transfer",
                "department_change",
                "employment_condition_change",
            }
            and self.department_id
        ):
            contract_vals[
                "department_id"
            ] = self.department_id.id

            employee_vals[
                "department_id"
            ] = self.department_id.id

        if (
            action_type
            in {
                "transfer",
                "position_change",
                "employment_condition_change",
            }
            and self.job_id
        ):
            contract_vals[
                "job_id"
            ] = self.job_id.id

            employee_vals[
                "job_id"
            ] = self.job_id.id

        if (
            action_type
            in {
                "transfer",
                "schedule_change",
                "employment_condition_change",
            }
            and self.resource_calendar_id
        ):
            contract_vals[
                "resource_calendar_id"
            ] = (
                self.resource_calendar_id.id
            )

            employee_vals[
                "resource_calendar_id"
            ] = (
                self.resource_calendar_id.id
            )

        if self.professional_category_id:
            contract_vals[
                "professional_category_id"
            ] = (
                self.professional_category_id.id
            )

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
            contract_vals["wage"] = self.wage

        if self.work_type:
            contract_vals[
                "l10n_ua_work_type"
            ] = self.work_type

        if self.hire_condition:
            contract_vals[
                "l10n_ua_hire_condition"
            ] = self.hire_condition

        if self.weekly_hours > 0:
            contract_vals[
                "l10n_ua_weekly_hours"
            ] = self.weekly_hours

        if self.work_conditions:
            contract_vals[
                "l10n_ua_work_conditions"
            ] = self.work_conditions

        if self.allowance_note:
            contract_vals[
                "l10n_ua_allowance_note"
            ] = self.allowance_note

        contract.write(contract_vals)

        next_contract = (
            self._historical_next_contract(
                employee,
                self.effective_date,
            )
        )

        # Historical backfill changes the temporal contract
        # and immutable event ledger only. It must never
        # rewrite today's employee card merely because no
        # later historical year has been imported yet.

        self._finalize_event(
            event,
            employee,
            contract=contract,
            previous=previous,
        )

        self._mark_applied(
            employee,
            contract=contract,
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

        employee = self.employee_id.sudo()

        contract = (
            self._historical_contract_at_date(
                employee,
                self.effective_date,
            )
        )

        if not contract:
            raise ValidationError(
                _(
                    "Для історичного звільнення "
                    "не знайдено трудовий період "
                    "працівника %s на дату %s."
                )
                % (
                    employee.name,
                    self.effective_date,
                )
            )

        previous = self._actual_state(
            employee,
            contract=contract,
        )

        contract.write(
            {
                "date_end":
                    self.effective_date,
                "state": "close",
                "l10n_ua_personnel_order_line_id":
                    self.id,
                "l10n_ua_end_date_inferred":
                    False,
                "l10n_ua_end_date_unresolved":
                    False,
            }
        )

        # Do not write active/departure_date/current position
        # to hr.employee in historical mode. The current
        # employee card represents today's operational state.
        # Historical dismissal facts live in the contract and
        # immutable personnel event.

        self._finalize_event(
            event,
            employee,
            contract=contract,
            previous=previous,
        )

        self._mark_applied(
            employee,
            contract=contract,
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
                    "application_error": False,
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
                # Base leave implementation is safe:
                # _current_contract, _actual_state and
                # _finalize_event are temporal-aware here.
                line._apply_leave(event)

            elif action_type == "termination":
                line._apply_termination(event)

            else:
                line._apply_generic_event(
                    event
                )

        return True


class HrPersonnelEventHistorical(models.Model):
    _inherit = "hr.personnel.event"

    event_type = fields.Selection(
        ORDER_TYPE_SELECTION,
        related="order_line_id.action_type",
        store=True,
        string="Тип події",
        index=True,
    )
