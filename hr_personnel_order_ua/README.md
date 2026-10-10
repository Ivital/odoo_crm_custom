# HR Personnel Orders Ukraine

Structured Ukrainian personnel orders for Odoo 18.

## 18.0.2.0.0 — application engine

This release activates the personnel-order execution layer:

- P-1 hiring creates/updates `hr.employee` and creates the running `hr.contract`;
- transfers and employment-condition changes update the employee/current contract;
- P-3 creates and approves `hr.leave`, preserving work-period, calendar-day count, and health-assistance data;
- P-4 closes the current contract, records departure data, and archives the employee;
- future-dated non-leave personnel actions create planned immutable events and are applied by an hourly cron when the effective date arrives;
- every applied action produces an immutable `hr.personnel.event` with before/after state and structured source data;
- `hr.contract` and `hr.leave` keep the source personnel-order line;
- the Employee form exposes current personnel/contract terms and order/history smart buttons;
- failed scheduled applications stay pending with a visible error and can be retried.

The order remains the legal source. Current Employee/Contract/Leave records are operational projections, while `hr.personnel.event` is the auditable history ledger.
