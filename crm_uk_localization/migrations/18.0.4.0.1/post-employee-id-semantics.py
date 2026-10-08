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

    for employee in Employee.search([], order="id"):
        employee_id = (employee.identification_id or "").strip()

        # In 18.0.4.0.0 identification_id was temporarily redefined as a
        # non-stored related field to the canonical partner RNOKPP. The
        # physical hr_employee.identification_id column therefore retained
        # its pre-18.0.4 values as stale legacy data.
        #
        # The successful 18.0.4.0.0 migration had already validated every
        # non-empty legacy identification_id as an exact 10-digit RNOKPP
        # before copying it to res.partner.id_number. Later edits of the
        # canonical RNOKPP do not update that stale SQL column, so equality
        # with the *current* RNOKPP must not be required here.
        if employee_id:
            if len(employee_id) != 10 or not employee_id.isdigit():
                raise RuntimeError(
                    "Unexpected legacy hr.employee identification_id while "
                    "restoring Employee ID semantics: "
                    f"employee={employee.id} length={len(employee_id)}"
                )
            employee.write({"identification_id": False})
            cleared_legacy_rnokpp += 1

        if not hasattr(employee, "_generate_identification_id"):
            raise RuntimeError(
                "hr_employee_id generator is unavailable for "
                f"employee={employee.id}"
            )

        generated = employee._generate_identification_id()
        if not generated:
            raise RuntimeError(
                "Employee ID generator returned no value for "
                f"employee={employee.id}"
            )

        employee.write({"identification_id": generated})
        generated_employee_ids += 1

    # Canonical RNOKPP records are not rewritten by this migration.
    # Their format remains protected by the existing model constraint.

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
        "%s legacy RNOKPP values cleared from Employee IDs, "
        "%s Employee IDs generated",
        cleared_legacy_rnokpp,
        generated_employee_ids,
    )
