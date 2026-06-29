# Hospital Pharmacy

## Purpose

`hospital_pharmacy` is the dispensing integration addon of the Hospital
Management System suite for Odoo 19. It is **module 6 of 12** in the
Phase 12 build order.

Its primary job is to implement the full dispensing flow (Phase 3 §5)
as the integration point between two modules that cannot directly depend
on each other:

- `hospital_doctor` -- owns the prescription model and line fields
  (`qty_dispensed`, `state`), deliberately left un-driven ("pharmacy will
  add the dispense methods via _inherit later").
- `hospital_inventory` -- owns the Pharmacy stock location/warehouse and
  the clinical medicine fields on `product.template`, but cannot depend
  on `hospital_doctor` (that would invert the dependency graph defined in
  Phase 4 §2).

`hospital_pharmacy` depends on **both**, which is the only position in
the build order from which it is legal to own the stock-move dispense logic.

## Dependencies

- `hospital_doctor` (transitively: `hospital_nurse`, `hospital_reception`,
  `hospital_base`, `product`)
- `hospital_inventory` (transitively: `hospital_base`, `stock`)

## Key Models

| Model | Role |
|---|---|
| `hospital.prescription.line` (extended) | Adds `dispense()`, `_find_allergy_conflicts()`, `_create_dispense_stock_move()`, `override_reason`, `stock_move_id`, `qty_on_hand_at_pharmacy`, `has_allergy_conflict`. |
| `hospital.prescription` (extended) | Thin shell: documents the visit-level routing contract (no new methods needed -- `_recompute_state_from_lines()` already existed in `hospital_doctor`). |
| `hospital.prescription.dispense.wizard` | Batch-dispense wizard with per-line override flags. |
| `hospital.prescription.dispense.wizard.line` | One row per prescription line in the wizard. |

## The Visit-Level Routing Contract

This is the most architecturally significant thing this module does.

**The exact contract:** after each successful dispense call,
`hospital.prescription.line.dispense()` calls:

1. `self.prescription_id._recompute_state_from_lines()` -- recomputes
   `hospital.prescription.state` from all its line states (this method
   already existed in `hospital_doctor`; no override needed here).
2. `self.visit_id.action_route_from_consultation()` -- re-evaluates all
   pending branches on the visit and transitions it to `billing` if
   every branch is resolved, or keeps it `in_progress_multi` if any
   branch is still open.

**Why this works without extending `_compute_pending_branches()`:**
`hospital_doctor`'s `_compute_pending_branches()` already checks
`hospital.prescription.state` directly:

```python
open_prescriptions = self.env["hospital.prescription"].search(
    [
        ("visit_id", "in", self.ids),
        ("state", "in", ["draft", "partially_dispensed"]),
    ]
)
```

This module does NOT need to extend `_compute_pending_branches()` --
the prescription-branch pending check already lives in `hospital_doctor`.
This is explicitly documented in `hospital_doctor`'s own README and in
the `_compute_pending_branches()` docstring. Simply driving
`hospital.prescription.state` to `"dispensed"` (via `dispense()` ->
`_recompute_state_from_lines()`) removes the prescription from the
pending set, and `action_route_from_consultation()` propagates that to
the visit automatically.

**What `hospital_lab`, `hospital_radiology`, and `hospital_ipd` must do:**
Those modules DO need to extend `_compute_pending_branches()` (calling
`super()` and adding/removing their own branch label). See the full
illustrative contract in `hospital_doctor/models/hospital_visit.py`.

## The Billing Hook Stub

`hospital.prescription.line._create_billing_line(qty)` is called at the
correct point in every successful dispense (after the stock move is
validated, before returning). It is a **deliberate no-op** for these reasons:

1. `hospital.visit.invoice_id` (Many2one -> `account.move`) is explicitly
   documented in `hospital_base` as not yet added ("belongs to later
   modules"). No module in the build order so far has created or
   referenced `account.move` for visit billing.
2. Phase 6's module breakdown does not assign billing/invoicing
   implementation to `hospital_pharmacy` -- the most likely candidate is
   a future `hospital_billing` or `hospital_reports` module.
3. Building an `account.move`/`account.move.line` contract here, before
   the module that defines `visit.invoice_id` exists, would mean guessing
   a foreign-key contract and conflicting with it when that module arrives.

Any future module that takes ownership of billing should override
`_create_billing_line()` via `_inherit` on
`hospital.prescription.line`, calling `super()` first. The stub is
already wired into the dispense flow at the right point so the override
will "just work" without touching any other dispense code.

## Stock Move Pattern

Dispensing creates a `stock.move` from:

- **Source:** `hospital_inventory.stock_location_pharmacy_store` (the
  named sub-location under the Pharmacy warehouse's internal stock
  location, defined in `hospital_inventory/data/hospital_inventory_data.xml`).
- **Destination:** `hospital_pharmacy.stock_location_patient_consumption`
  (a `usage=inventory` virtual location defined in this module's
  `data/hospital_pharmacy_data.xml`, nested under
  `stock.stock_location_locations_virtual`). `usage=inventory` is Odoo's
  convention for locations where stock goes when it leaves trackable
  inventory (matches semantics: patient consumed the medicine, it is gone
  from the warehouse).

Move validation uses: `_action_confirm()` -> `_action_assign()` ->
`move_line_ids.write({"quantity": qty, "picked": True})` ->
`_action_done()`.

## Allergy Safety Check

Matching is **case-insensitive substring**, both directions (allergy name
in medicine name, or medicine name in allergy name). A `"Paracetamol"`
allergy matches `"Paracetamol 500mg"` medicine. No formal drug-allergy
ontology is implemented -- the PRD explicitly scopes this out.

Conflict resolution:

1. No conflict: dispense proceeds.
2. Conflict + no override: `UserError` raised, dispense blocked.
3. Conflict + `override_allergy=True` + non-empty `override_reason`:
   dispense proceeds; `override_reason` is stored on the line; a
   dedicated `hospital.audit.log` row is created with
   `"event": "allergy_override"` alongside the normal field-level
   audit trail that `hospital.audit.mixin` already produces on the
   `override_reason` write.

## Security

- **Hospital Pharmacist** (`group_hospital_pharmacist`): implies
  `hospital_base.group_hospital_user`. Can read+write prescriptions and
  lines (but not create or delete prescriptions). Full CRUD on the
  dispense wizard. Does NOT imply `stock.group_stock_manager` -- the
  dispense stock-move creation is done programmatically (the ORM call is
  made in a context where the system can validate moves), so a pharmacist
  does not need native Inventory manager access.
- Multi-company record rule on `hospital.prescription.line`: scoped by
  `visit_id.company_id`, consistent with `hospital_doctor`'s existing
  rule on `hospital.prescription`.
- Pharmacist read-all rule on prescriptions/lines: no doctor-scope
  restriction (pharmacists need to see all queued prescriptions, not just
  those from one doctor).

## Views and Menus

`Hospital -> Pharmacy` (visible to pharmacists and admins):

- **Dashboard** -- OWL split view, keyboard shortcuts D (Dispense) / A
  (Dispense All).
- **Dispensing Queue** -- open prescriptions list filtered to
  `draft`/`partially_dispensed`.
- **Backorders** -- prescription lines in `partial`/`backordered` state.

Prescription form (inherited from hospital_doctor):

- "Dispense" button in header (visible to pharmacists/admins when not
  yet dispensed/cancelled), opens the batch-dispense wizard.
- `qty_on_hand_at_pharmacy` column added to the lines list, with red
  badge at 0, amber badge when below outstanding qty.

## Install / Configuration

1. Install `hospital_doctor` and `hospital_inventory` first.
2. Install `hospital_pharmacy` from the Apps menu.
3. Assign **Hospital Pharmacist** group to pharmacy staff.
4. Go to **Hospital -> Pharmacy -> Dashboard** to start dispensing.

Demo data creates three prescriptions using properly-stocked
`hospital_inventory` medicines and executes all three dispense scenarios
(full, partial, allergy-override) via the real `dispense()` codepath to
prove the end-to-end flow works.
