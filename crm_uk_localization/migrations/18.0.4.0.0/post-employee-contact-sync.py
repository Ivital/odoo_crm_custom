import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)
SYNC_CONTEXT_KEY = "l10n_ua_skip_employee_partner_sync"
SNAPSHOT_TABLE = "crm_uk_localization_employee_1804_snapshot"

PARTNER_FIELDS = {
    "private_street": "l10n_ua_private_street",
    "private_street2": "l10n_ua_private_street2",
    "private_city": "l10n_ua_private_city",
    "private_state_id": "l10n_ua_private_state_id",
    "private_zip": "l10n_ua_private_zip",
    "private_country_id": "l10n_ua_private_country_id",
    "private_phone": "l10n_ua_private_phone",
    "private_email": "l10n_ua_private_email",
    "country_id": "nationality_id",
    "gender": "gender",
    "birthday": "birthdate_date",
    "place_of_birth": "birth_city",
    "country_of_birth": "birth_country_id",
}


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    return bool(cr.fetchone()[0])


def _normalize(value):
    return value or False


def _get_category(env, code, name):
    category = env["res.partner.id_category"].search(
        [("code", "=", code)], limit=1
    )
    if not category:
        category = env["res.partner.id_category"].create(
            {"code": code, "name": name}
        )
    return category


def _set_identifier(env, partner, category, value):
    value = (value or "").strip()
    if not value:
        return
    existing = env["res.partner.id_number"].search(
        [
            ("partner_id", "=", partner.id),
            ("category_id", "=", category.id),
            ("active", "=", True),
            ("status", "!=", "close"),
        ],
        limit=1,
    )
    if existing:
        if existing.name != value:
            raise RuntimeError(
                "Employee/contact identifier conflict: "
                f"partner={partner.id} category={category.code}"
            )
        return
    env["res.partner.id_number"].create(
        {
            "partner_id": partner.id,
            "category_id": category.id,
            "name": value,
            "status": "open",
        }
    )


def _get_plot_uom(env):
    """Resolve geospatial_plot default without creating res.config.settings."""
    Parameter = env["ir.config_parameter"].sudo()
    Uom = env["uom.uom"].sudo()

    configured = Parameter.get_param("geospatial_plot.plot_uom_id")
    if configured:
        try:
            record = Uom.browse(int(configured)).exists()
        except (TypeError, ValueError):
            record = Uom.browse()
        if record:
            return record

    record = env.ref(
        "geospatial_plot.uom_surface_acre",
        raise_if_not_found=False,
    )
    if record:
        return record

    return env.ref(
        "uom.uom_square_meter",
        raise_if_not_found=False,
    )


def _create_work_contact(employee):
    """Mirror Odoo hr._create_work_contacts without broken settings default_get."""
    Partner = employee.env["res.partner"].sudo().with_context(
        **{SYNC_CONTEXT_KEY: True}
    )

    values = {
        "email": employee.work_email,
        "mobile": employee.mobile_phone,
        "name": employee.name,
        "image_1920": employee.image_1920,
        "company_id": employee.company_id.id,
    }

    # OCA geospatial_plot computes the default through
    # res.config.settings.create({}), which can fail when another settings
    # field has a NOT NULL constraint. Supplying plot_uom_id keeps partner
    # creation inside the normal ORM while avoiding that unrelated path.
    if "plot_uom_id" in Partner._fields:
        plot_uom = _get_plot_uom(employee.env)
        if not plot_uom:
            raise RuntimeError(
                "Cannot resolve plot_uom_id required for work contact creation"
            )
        values["plot_uom_id"] = plot_uom.id

    partner = Partner.create(values)

    employee.with_context(
        **{SYNC_CONTEXT_KEY: True}
    ).write(
        {"work_contact_id": partner.id}
    )

    return partner


def migrate(cr, version):
    if not version:
        return
    if not _table_exists(cr, SNAPSHOT_TABLE):
        raise RuntimeError(f"Missing migration snapshot table: {SNAPSHOT_TABLE}")

    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].with_context(active_test=False).sudo()

    rnokpp_category = _get_category(
        env,
        "ua_rnokpp",
        "РНОКПП (реєстраційний номер облікової картки платника податків)",
    )
    passport_category = _get_category(
        env,
        "ua_passport",
        "Паспорт / документ, що посвідчує особу (Україна)",
    )

    cr.execute(f"SELECT * FROM {SNAPSHOT_TABLE} ORDER BY employee_id")
    columns = [description[0] for description in cr.description]
    rows = [dict(zip(columns, row)) for row in cr.fetchall()]

    migrated = 0
    created_contacts = 0

    for snapshot in rows:
        employee = Employee.browse(snapshot["employee_id"]).exists()
        if not employee:
            continue

        if employee.user_id and employee.work_contact_id:
            if employee.user_id.partner_id != employee.work_contact_id:
                raise RuntimeError(
                    "Employee user/contact mismatch: "
                    f"employee={employee.id} user_partner={employee.user_id.partner_id.id} "
                    f"work_contact={employee.work_contact_id.id}"
                )

        if not employee.work_contact_id:
            if employee.user_id:
                employee.with_context(**{SYNC_CONTEXT_KEY: True}).write(
                    {"work_contact_id": employee.user_id.partner_id.id}
                )
            else:
                _create_work_contact(employee)
            created_contacts += 1

        partner = employee.work_contact_id.sudo()
        partner_values = {}
        for old_field, partner_field in PARTNER_FIELDS.items():
            old_value = _normalize(snapshot.get(old_field))
            current_value = partner[partner_field]
            if hasattr(current_value, "id"):
                current_value = current_value.id or False
            else:
                current_value = _normalize(current_value)

            if old_value and current_value and old_value != current_value:
                raise RuntimeError(
                    "Employee/contact data conflict: "
                    f"employee={employee.id} old_field={old_field} "
                    f"partner={partner.id} partner_field={partner_field}"
                )
            if old_value and not current_value:
                partner_values[partner_field] = old_value

        if partner_values:
            partner.with_context(**{SYNC_CONTEXT_KEY: True}).write(partner_values)

        rnokpp = (snapshot.get("identification_id") or "").strip()
        if rnokpp and (len(rnokpp) != 10 or not rnokpp.isdigit()):
            raise RuntimeError(
                f"Employee {employee.id} identification_id is not a 10-digit RNOKPP"
            )
        _set_identifier(env, partner, rnokpp_category, rnokpp)
        _set_identifier(
            env,
            partner,
            passport_category,
            snapshot.get("passport_id"),
        )
        migrated += 1

    # 18.0.3 had a default 'active' legal status on all partners. Ordinary
    # physical persons must not keep an invisible legal-entity status.
    env["res.partner"].sudo().search(
        [
            ("is_company", "=", False),
            ("l10n_ua_is_fop", "=", False),
            ("l10n_ua_legal_status", "!=", False),
        ]
    ).with_context(**{SYNC_CONTEXT_KEY: True}).write(
        {"l10n_ua_legal_status": False}
    )

    cr.execute(f"DROP TABLE {SNAPSHOT_TABLE}")
    _logger.info(
        "crm_uk_localization 18.0.4 employee/contact migration complete: "
        "%s employees, %s contacts created",
        migrated,
        created_contacts,
    )
