import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].with_context(active_test=False).sudo()
    IdNumber = env["res.partner.id_number"].sudo()
    Category = env["res.partner.id_category"].sudo()

    rnokpp_category = Category.search(
        [("code", "=", "ua_rnokpp")],
        limit=1,
    )
    if not rnokpp_category:
        raise RuntimeError("UA RNOKPP identifier category is missing")

    cleared_legacy_rnokpp = 0
    generated_employee_ids = 0
    preserved_employee_ids = 0

    for employee in Employee.search([], order="id"):
        rnokpp_records = (
            IdNumber.search(
                [
                    ("partner_id", "=", employee.work_contact_id.id),
                    ("category_id", "=", rnokpp_category.id),
                    ("active", "=", True),
                    ("status", "!=", "close"),
                ]
            )
            if employee.work_contact_id
            else IdNumber.browse()
        )

        if len(rnokpp_records) > 1:
            raise RuntimeError(
                "Multiple active RNOKPP identifiers for "
                f"employee={employee.id}"
            )

        rnokpp = rnokpp_records.name.strip() if rnokpp_records else ""
        employee_id = (employee.identification_id or "").strip()

        # 18.0.4.0.0 temporarily reused identification_id as RNOKPP.
        # Clear only values proven equal to the canonical partner RNOKPP.
        if employee_id and rnokpp and employee_id == rnokpp:
            employee.write({"identification_id": False})
            employee_id = ""
            cleared_legacy_rnokpp += 1
        elif employee_id:
            preserved_employee_ids += 1

        # OCA hr_employee_id supplies this generator. Existing employees
        # created while identification_id was overridden never received
        # their normal Employee ID, so restore that invariant.
        if not employee_id and hasattr(employee, "_generate_identification_id"):
            generated = employee._generate_identification_id()
            if not generated:
                raise RuntimeError(
                    "Employee ID generator returned no value for "
                    f"employee={employee.id}"
                )
            employee.write({"identification_id": generated})
            generated_employee_ids += 1

    conflicts = 0
    for employee in Employee.search([], order="id"):
        if not employee.work_contact_id or not employee.identification_id:
            continue
        if IdNumber.search_count(
            [
                ("partner_id", "=", employee.work_contact_id.id),
                ("category_id", "=", rnokpp_category.id),
                ("active", "=", True),
                ("status", "!=", "close"),
                ("name", "=", employee.identification_id),
            ],
            limit=1,
        ):
            conflicts += 1

    if conflicts:
        raise RuntimeError(
            "Employee ID / RNOKPP semantic separation failed: "
            f"{conflicts} conflicts remain"
        )

    _logger.info(
        "crm_uk_localization 18.0.4.0.1 employee ID semantics restored: "
        "%s legacy RNOKPP values cleared from employee IDs, "
        "%s Employee IDs generated, %s existing Employee IDs preserved",
        cleared_legacy_rnokpp,
        generated_employee_ids,
        preserved_employee_ids,
    )
