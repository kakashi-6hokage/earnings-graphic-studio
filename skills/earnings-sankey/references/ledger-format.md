# Ledger input schema

Input is a JSON object with keys:

- `company` (string), `quarter` (string), `headline` (string), `release_date` (ISO string)
- `currency` (display prefix: `$`, `₸`, `€`, etc), `units` (`B` or `M`, optional), `source_note` (string)
- `revenue` (positive numeric)
- `sources`: nonempty array of `{name, amount, yoy? (numeric percentage), color? (blue|gold), mark? (short label)}`
- `cost_of_revenue` (nonnegative numeric)
- `operating_expenses`: array of `{name, amount, yoy?}` (nonnegative). Can be empty if there are no operating expenses.
- `nonoperating_net` (signed numeric; positive is income, negative is cost), default 0
- `income_tax` (signed numeric; positive expense, negative tax benefit)
- `net_income` (signed numeric)
- optional `gross_profit`, `operating_profit`, `pretax_income` to check against calculations
- optional `revenue_yoy`, `gross_yoy`, `operating_yoy`, `net_yoy`

All values use the SAME currency and units; do not mix millions and billions within one ledger. Current and prior-year comparisons are not automatically verified against filings; research must supply them. The financial validator catches inconsistent arithmetic and geometry, not source truth or reporting-policy compliance.

For sign-changing results (`pretax_income < 0` or `net_income < 0`), renderer displays a clearly tagged red loss terminal; it does not misrepresent a loss as a positive flow. Signed reversals are not part of simple conservation geometry.

Rounding: retain full-precision amounts internally; format visible money with at most two decimals and round-half-up, stripping unnecessary trailing zeros. Published rounded subtotals may differ slightly; validators allow a configurable small display-rounding tolerance, but never introduce hidden unsupported categories to force a visual balance.
