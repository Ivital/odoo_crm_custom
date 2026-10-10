# HR Personnel Orders Ukraine

Structured personnel orders for Odoo 18.

## Foundation scope — 18.0.1.0.0

This first commit intentionally implements only:

- `hr.personnel.order`
- `hr.personnel.order.line`
- immutable `hr.personnel.event` ledger model
- personnel-order workflow
- company security
- Employees menu entries
- Employee smart buttons
- tests for state transitions, locking, and foundation contracts

`action_post()` does **not** yet mutate `hr.employee`, `hr.contract`, or
`hr.leave`. Posted lines remain in `pending` application state.

The next development step adds the application engine for P-1 hiring,
transfers/condition changes, P-3 leave, and P-4 termination.
