# Hospital Base

## Purpose

`hospital_base` is the foundational addon of the Hospital Management System
suite for Odoo 19. It provides the core master data and the patient/visit
"spine" record that every other `hospital_*` module (Reception, Nurse
Station, Doctor Workspace, Pharmacy, Laboratory, Radiology, IPD, Dashboard,
Reports, Security) depends on and extends.

This module is **module 1 of 12** in the build order defined by the project's
Phase 12 implementation plan.

## Dependencies

- `base`
- `mail`

No dependency on `hr` or `stock` is introduced here, by design: `hospital_base`
sits underneath every other addon in the suite, so a heavyweight transitive
dependency at this layer would force unrelated Odoo apps onto installs that
don't need them (e.g. a small clinic that doesn't use Odoo's HR or
Inventory apps at all). Optional integrations (employee linkage, stock
moves) are added by the specific downstream modules that actually need
them.

## Key Models

| Model | Purpose |
|---|---|
| `hospital.patient` | Patient registry: identity, contact info, allergies, chronic conditions, visit history, duplicate detection. |
| `hospital.patient.allergy` | Allergy line, cascades with its patient. |
| `hospital.patient.condition` | Chronic condition line, cascades with its patient. |
| `hospital.visit` | The spine record of the system: tracks a single OPD/IPD encounter through its full lifecycle. |
| `hospital.department` | Hospital department master data. |
| `hospital.doctor` | Doctor master data, linked to a `res.users` login identity. |
| `hospital.doctor.schedule` | A doctor's weekly availability slots. |
| `hospital.audit.log` | Append-only audit trail. No group -- including the administrator -- has `unlink` access. |
| `hospital.audit.mixin` | Abstract mixin providing `create`/`write` overrides that emit `hospital.audit.log` rows. |
| `hospital.patient.merge.wizard` | Admin-only tool to merge duplicate patient records. |

## Security

Two groups are defined:

- **Hospital User** (`group_hospital_user`): read-only access to patients and
  visits. Base group that every other hospital role (defined in later
  modules) builds on top of.
- **Hospital Administrator** (`group_hospital_admin`): full CRUD on all
  `hospital_base` models, plus read-only access to the audit log.

The audit log (`hospital.audit.log`) grants **zero** `unlink` permission to
any group, by design -- it is an append-only, tamper-resistant compliance
log.

Multi-company record rules are applied to `hospital.patient`,
`hospital.visit`, `hospital.department`, and `hospital.doctor`, following
Odoo's standard `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`
pattern, so a hospital chain with multiple branches keeps each branch's
records isolated.

## Install / Configuration

1. Copy (or symlink) this addon into your Odoo 19 `addons-path`.
2. Update the apps list and install **Hospital Base** from the Apps menu
   (or `odoo-bin -i hospital_base -d <your_database>`).
3. As an administrator, go to **Hospital -> Configuration -> Departments**
   and create your hospital's departments.
4. Go to **Hospital -> Configuration -> Doctors** and create doctor records,
   linking each one to an existing `res.users` login.
5. Begin registering patients from **Hospital -> Patients**, and create
   visits from **Hospital -> Visits**.
6. Print a Patient ID Card from any patient form via **Print -> Patient ID
   Card**.

Demo data (5 departments, 5 doctors with demo users and weekly schedules, 20
patients) is loaded automatically when demo data is enabled on the database.

## Notes on Scope

- `hospital.visit` intentionally does **not** define `prescription_ids`,
  `lab_order_ids`, `radiology_order_ids`, `admission_id`, or `invoice_id` in
  this module. Those fields are added by the modules that own the target
  models (`hospital_doctor`, `hospital_pharmacy`, `hospital_lab`,
  `hospital_radiology`, `hospital_ipd`) via standard Odoo `_inherit`, once
  those models exist.
- `hospital.doctor` does not link to `hr.employee` in this module, to avoid
  a hard dependency on the `hr` app at the foundation layer. A future
  module that already depends on `hr` may add an optional `employee_id`
  field via inheritance if needed.
