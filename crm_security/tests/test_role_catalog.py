from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCorporateRoleCatalog(TransactionCase):
    ROLE_MAP = {
        "crm_security.role_crm_manager":
            "crm_security.group_crm_manager",
        "crm_security.role_contract_viewer":
            "crm_security.group_contract_viewer",
        "crm_security.role_contract_user":
            "crm_security.group_contract_user",
        "crm_security.role_contract_manager":
            "crm_security.group_contract_manager",
        "crm_security.role_helpdesk_agent":
            "crm_security.group_helpdesk_agent",
        "crm_security.role_helpdesk_manager":
            "crm_security.group_helpdesk_manager",
        "crm_security.role_technician":
            "crm_security.group_technician",
        "crm_security.role_dispatcher":
            "crm_security.group_dispatcher",
        "crm_security.role_field_service_manager":
            "crm_security.group_field_service_manager",
        "crm_security.role_maintenance_manager":
            "crm_security.group_maintenance_manager",
        "crm_security.role_project_manager":
            "crm_security.group_project_manager",
        "crm_security.role_warehouse_manager":
            "crm_security.group_warehouse_manager",
        "crm_security.role_purchasing_manager":
            "crm_security.group_purchasing_manager",
        "crm_security.role_accountant":
            "crm_security.group_accountant",
        "crm_security.role_audit_manager":
            "crm_security.group_audit_manager",
        "crm_security.role_auditor":
            "crm_security.group_auditor",
    }

    def test_role_catalog_contains_exactly_expected_mapping(self):
        self.assertEqual(len(self.ROLE_MAP), 16)

        for role_xmlid, group_xmlid in self.ROLE_MAP.items():
            role = self.env.ref(role_xmlid)
            business_group = self.env.ref(group_xmlid)

            self.assertEqual(
                role._name,
                "res.users.role",
                role_xmlid,
            )
            self.assertEqual(
                role.implied_ids,
                business_group,
                role_xmlid,
            )

    def test_business_roles_do_not_grant_system_administration(self):
        forbidden_groups = (
            self.env.ref("base.group_system")
            | self.env.ref("base.group_erp_manager")
        )

        for role_xmlid in self.ROLE_MAP:
            role = self.env.ref(role_xmlid)

            effective_groups = (
                role.group_id
                | role.implied_ids
                | role.trans_implied_ids
            )

            leaked = effective_groups & forbidden_groups

            self.assertFalse(
                leaked,
                "%s unexpectedly grants administrative groups: %s"
                % (
                    role_xmlid,
                    ", ".join(
                        leaked.get_external_id().values()
                    ),
                ),
            )

    def test_auditor_all_domain_rules_are_read_only(self):
        rule_xmlids = (
            "crm_security.rule_auditor_helpdesk_all",
            "crm_security.rule_auditor_maintenance_all",
            "crm_security.rule_auditor_maintenance_equipment_all",
        )

        for rule_xmlid in rule_xmlids:
            rule = self.env.ref(rule_xmlid)

            self.assertTrue(rule.perm_read, rule_xmlid)
            self.assertFalse(rule.perm_write, rule_xmlid)
            self.assertFalse(rule.perm_create, rule_xmlid)
            self.assertFalse(rule.perm_unlink, rule_xmlid)
            self.assertEqual(
                rule.domain_force,
                "[(1, '=', 1)]",
                rule_xmlid,
            )
