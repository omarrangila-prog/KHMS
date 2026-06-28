# Hospital Doctor

## Purpose

`hospital_doctor` is the clinical-core addon of the Hospital Management
System suite for Odoo 19. It builds on `hospital_nurse` (which
transitively pulls in `hospital_base` and `hospital_reception`) to give
doctors a single-screen Consultation workspace, multi-branch outcome
routing, and a prescription builder.

This module is **module 4 of 12** in the build order defined by the
project's Phase 12 implementation plan. It is the most architecturally
important module built so far: it owns the consultation workflow and the
aggregate-visit-state routing logic that `hospital_pharmacy`,
`hospital_lab`, `hospital_radiology`, and `hospital_ipd` (none of which
exist yet) will need to hook into once they are built.

## Dependencies

- `hospital_nurse` (transitively: `hospital_base`, `hospital_reception`)
- `product` (Odoo's lightweight product catalog app)

**Why `product` and not `hospital_inventory` or `stock`:** Phase 5 §3.3
defines `hospital.medicine` as a `product.template` extension with
clinical fields (`generic_name`, `dosage_form`, `strength`, etc.), but
Phase 6 §6 assigns ownership of that extension to `hospital_inventory`,
which is not built yet. Per Phase 4 §2's dependency graph,
`hospital_inventory` depends on `hospital_base` + `stock` -- **not** on
`hospital_doctor` -- while `hospital_pharmacy` depends on **both**
`hospital_doctor` and `hospital_inventory`. If this module depended on
`hospital_inventory` just to get the clinical medicine fields, it would
invert that graph and create a dependency cycle once `hospital_pharmacy`
is added.

The decision: `hospital_doctor` depends on bare `product` (a lightweight
Odoo base app, not the full `stock` app) and references `product.product`
directly on `hospital.prescription.line.medicine_id`. No
`hospital.medicine` extension fields are defined in this module --
`hospital_inventory` will add them to `product.template` later via
`_inherit`. Because this module does not depend on `stock`,
`product.product.qty_available` would not be a meaningful figure even if
read, so the Prescription Builder intentionally has **no live stock
display** -- `hospital_pharmacy`/`hospital_inventory` will add a stock
badge column to the prescription line view via view inheritance once
`stock` is actually in the dependency graph.

## Key Models

| Model | Purpose |
|---|---|
| `hospital.consultation` | The doctor's consultation record: diagnosis, clinical notes, and five independent outcome-intent booleans (`outcome_prescribe`, `outcome_lab_requested`, `outcome_radiology_requested`, `outcome_admit_requested`, `outcome_discharge`) that can be combined freely, per Phase 3 §3. `amended_from_id` tracks same-day amendments. |
| `hospital.prescription` | Prescription header, linked to the visit (and optionally the consultation that created it). `admission_id` (Phase 5 §3.4) is intentionally omitted -- see "Documented Limitations" below. |
| `hospital.prescription.line` | One line per medicine: dosage/frequency/duration/route, `qty_prescribed`/`qty_dispensed` (constrained `qty_dispensed <= qty_prescribed`), and the `state` field `hospital_pharmacy` will drive via dispense methods added later. |
| `hospital.consultation.amend.wizard` | Same-day amendment wizard (Phase 3 §3 edge case): creates a new consultation with `amended_from_id` set, reopens the visit from `billing` back to `in_progress_multi`. |
| `hospital.visit` (extended) | Adds `consultation_ids`, `prescription_ids`, and the extensible aggregate-state routing contract described below. |

## The Aggregate-State Routing Contract (read this before building hospital_lab/hospital_radiology/hospital_ipd)

Per Phase 3 §3, a visit can be in **several** department queues at once
(e.g. pharmacy AND lab simultaneously) -- `Visit.state = in_progress_multi`
is a computed/aggregate state; the real per-branch status lives on each
sub-record. The visit only flips to `billing` once **every** branch the
doctor opened reports done/cancelled.

At the time this module is built, only the **prescription** branch is a
real sub-record (`hospital.prescription`, owned by this module). Lab,
radiology, and admission are **intent-only flags** on
`hospital.consultation` (`outcome_lab_requested`,
`outcome_radiology_requested`, `outcome_admit_requested`) because
`hospital.lab.order`, `hospital.radiology.order`, and
`hospital.ipd.admission` do not exist until `hospital_lab`,
`hospital_radiology`, and `hospital_ipd` are built later in the Phase 12
order.

### The extension point

`hospital.visit._compute_pending_branches(self)` returns a `dict` mapping
`visit.id -> list[str]` of pending branch labels (e.g. `"prescription"`,
`"lab"`, `"radiology"`, `"admission"`). An empty list means every branch
is resolved and the visit is eligible for `billing`.

This module's implementation knows about:

1. **`prescription`** -- pending if any `hospital.prescription` linked to
   the visit is `draft` or `partially_dispensed`.
2. **`lab` / `radiology` / `admission`** -- pending **unconditionally**
   whenever the visit's **latest** consultation has the corresponding
   intent flag set, because there is no real order/admission model to
   check completion against yet. Only the latest consultation is
   consulted (not the union of every consultation ever logged against
   the visit) -- a same-day amendment is expected to restate every
   outcome that is still relevant, so the latest consultation is always
   the authoritative statement of what's still open. This is
   intentional: it prevents `action_route_from_consultation()` from
   incorrectly fast-forwarding a visit to `billing` just because the
   tracking module isn't installed, while also not permanently pinning a
   visit in `in_progress_multi` because of a stale flag on an old,
   already-amended consultation.

`hospital_lab`, `hospital_radiology`, and `hospital_ipd` **must** extend
this method via `_inherit`, calling `super()` and replacing the
permanently-pending placeholder for their own branch with a real
completion check against their own order/admission model's `state` field.
See the full illustrative code example in the docstring of
`hospital.visit._compute_pending_branches()` in
`models/hospital_visit.py` -- the method signature and return shape are
the binding contract; do not change them when extending.

`hospital.visit.action_route_from_consultation()` is the routing method
that calls `_compute_pending_branches()` and applies the actual state
transition: no pending branches -> `billing`; any pending branch ->
`in_progress_multi`. It is called by `hospital.consultation.action_done()`
right after a consultation is completed.

`hospital_pharmacy` does **not** need to extend `_compute_pending_branches()`
-- it only adds dispense methods to `hospital.prescription.line` (the
prescription-branch check already lives here since `hospital.prescription`
itself is owned by this module).

## Documented Limitations

- **Lab / radiology / admission outcomes are intent-only.** Selecting
  "Lab Tests Requested", "Radiology Requested", or "Admission Requested"
  on a consultation in this module does **not** create a
  `hospital.lab.order`, `hospital.radiology.order`, or
  `hospital.ipd.admission` record -- those models don't exist yet. The
  flag is recorded and surfaces a banner on the consultation form
  explaining this. A visit with any of these flags set will stay in
  `in_progress_multi` indefinitely until `hospital_lab`/
  `hospital_radiology`/`hospital_ipd` are installed and extend
  `_compute_pending_branches()` as described above.
- **`hospital.prescription.admission_id` is omitted.** Phase 5 §3.4 lists
  this field for IPD linkage; `hospital_ipd` will add it back via
  `_inherit` once `hospital.ipd.admission` exists.
- **No live stock display in the Prescription Builder.** See the
  product/stock dependency decision above.
- **`hospital.medicine` clinical fields are not defined here.**
  `hospital_inventory` owns that `product.template` extension.

## Security

- **Hospital Doctor** (`group_hospital_doctor`): implied by
  `hospital_base.group_hospital_user`.
- **Read/write asymmetry** on `hospital.consultation` (Phase 9 §3):
  doctors can **read** every consultation tied to a visit where they are
  the visit's assigned doctor (`visit_id.doctor_id.user_id = uid`) --
  broader history visibility -- but can only **write**/**create**
  consultations they themselves authored (`doctor_id.user_id = uid`).
  Implemented as two separate `ir.rule` records scoped to
  `perm_read`/`perm_write` respectively, since Odoo ORs together multiple
  rules for the same group/model per operation.
- `hospital.prescription` is scoped to the doctor's own authored
  prescriptions for read/write/create.
- `hospital_base.group_hospital_admin` retains full CRUD on every model.
- `hospital_base.group_hospital_user` gets read-only fallback access,
  consistent with the established pattern.
- Multi-company record rules on `hospital.consultation`/
  `hospital.prescription`, consistent with `hospital_base`'s
  `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`
  pattern -- both carry `company_id` as a related, stored field off
  `visit_id`.

## Views & Menus

`Hospital -> Doctor Workspace` (visible to `group_hospital_doctor` and
`group_hospital_admin`):

- **Dashboard** -- OWL client action, 3-pane layout (queue / consultation
  context / collapsible patient-history panel), collapsing to a tab
  switcher on tablet widths.
- **My Queue** -- the doctor's own `waiting_doctor`/`in_progress_multi`
  visits.
- **My Patients** -- patients with at least one visit assigned to this
  doctor.
- **Consultations** / **Prescriptions** -- standard list/form views.

The consultation form shows the patient's vitals history (via the
visit's `vitals_ids`, read-only), an allergy banner computed from
`hospital.patient.allergy_ids`, previous consultations for the same
patient (cross-visit history), diagnosis/notes fields, the five outcome
checkboxes, and an inline editable Prescription Builder list (medicine
autocomplete + dosage/frequency/duration/route) when "Prescribe
Medication" is checked.

The visit form (`hospital_base.hospital_visit_view_form`) gains a "New
Consultation" button (visible while `waiting_doctor`/`in_progress_multi`)
and two read-only notebook pages: Consultations and Prescriptions.

## Install / Configuration

1. Install `hospital_base`, `hospital_reception`, and `hospital_nurse`
   first.
2. Install `hospital_doctor` from the Apps menu.
3. Assign the **Hospital Doctor** group to physicians. Each doctor user
   must have a linked `hospital.doctor` record (created in
   `hospital_base`) for the read/write record rules and the consultation
   form's default doctor to work correctly.
4. Go to **Hospital -> Doctor Workspace -> Dashboard** to start
   consulting.

Demo data adds vitals (via the real `hospital.vitals.create()` codepath)
for 4 more of `hospital_reception`'s demo visits, then 10 demo
consultations spanning every outcome combination called out in Phase 3
§3 (discharge-only, prescribe-only, prescribe+lab, admit-alone,
radiology-alone, lab+radiology, prescribe+admit, discharge+prescribe, an
all-five-outcomes case, and a same-day-amendment pair) -- each completed
via the real `action_done()` codepath so the aggregate-state routing
runs exactly as it would for a real doctor.
