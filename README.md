# Odoo CRM Custom

Custom Odoo 18 Community modules for the CRM platform.

## Modules

### crm_security

Corporate RBAC layer built on top of standard Odoo and OCA security groups.

The module does not replace upstream security. It composes business roles from
existing Odoo/OCA groups and adds narrowly scoped ACLs where upstream modules
tie permissions to unrelated functional roles.
