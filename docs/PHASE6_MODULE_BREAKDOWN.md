# Phase 6 — Module Breakdown

Sixteen installable addons, each independently versioned. Naming follows Odoo convention: lowercase, underscore-separated, `hospital_` prefix. Dependency order matches Phase 4 §2 and is the literal build order for Phase 12.

---

## 1. `hospital_base`

**Purpose:** Foundational layer — core master data, the patient/visit spine, shared mixins, sequences, base security groups. Every other module depends on this.

- **Dependencies:** `base`, `mail`, `web`
- **Models:** `hospital.patient`, `hospital.patient.allergy`, `hospital.patient.condition`, `hospital.visit`, `hospital.department`, `hospital.doctor`, `hospital.doctor.schedule`, `hospital.audit.log`, `hospital.audit.mixin` (abstract)
- **Views:** Patient form/list/kanban/search, Visit form/list/search, Department/Doctor config forms
- **Menus:** Top-level "Hospital" app menu root; Configuration submenu (Departments, Doctors)
- **Reports:** Patient ID card (QWeb)
- **Security:** Base groups (`group_hospital_user`, `group_hospital_admin`); ACLs for all base models; record rule template for company isolation
- **Controllers:** None (pure backend module)
- **Services:** `PatientDuplicateCheckService` (server-side helper used by registration)
- **Wizards:** `hospital.patient.merge.wizard` (admin-only duplicate merge, Phase 3 §7)
- **Data files:** `ir.sequence` records (PT/, VS/ codes), default `hospital.department` demo rows
- **Tests:** Patient creation/duplicate-detection, visit state machine unit tests
- **Demo data:** 20 demo patients, 5 departments, 10 doctors
- **Icon:** Hospital cross / heartbeat motif, primary brand color (Phase 7 palette)

---

## 2. `hospital_reception`

**Purpose:** Front-desk operations — registration UI, queue assignment, appointment booking, visit check-in.

- **Dependencies:** `hospital_base`
- **Models:** `hospital.appointment`
- **Views:** Reception Dashboard (OWL), Registration wizard form, Queue kanban (by doctor/department), Appointment calendar view
- **Menus:** "Reception" menu under Hospital app: Dashboard, Patients, Appointments, Queue
- **Reports:** Queue ticket / token slip (QWeb, small thermal-printer-friendly format)
- **Security:** `group_hospital_reception`; record rules scoping to own company/branch
- **Controllers:** None v1 (kiosk/self-checkin controller is future roadmap)
- **Services:** `QueueAssignmentService` (assigns next available doctor slot)
- **Wizards:** `hospital.visit.cancel.wizard` (requires reason, Phase 3 §7)
- **Data files:** Default queue-ticket sequence
- **Tests:** Registration flow, duplicate-warning surfacing, queue assignment correctness
- **Demo data:** 15 demo appointments, 10 demo visits in `waiting_nurse` state

---

## 3. `hospital_nurse`

**Purpose:** Vitals capture and nurse task workflows (OPD nurse station + IPD ward rounds support).

- **Dependencies:** `hospital_base`, `hospital_reception`
- **Models:** `hospital.vitals`, `hospital.nurse.task` (ward round / MAR checklist item, used standalone in OPD and extended by `hospital_ipd`)
- **Views:** Nurse Dashboard (tablet-optimized OWL), Vitals quick-entry form, Task checklist kanban
- **Menus:** "Nurse Station" menu: Dashboard, Vitals History
- **Reports:** None (vitals appear inline in patient timeline/consultation, not standalone print)
- **Security:** `group_hospital_nurse`
- **Controllers:** None
- **Services:** `VitalsTriageService` (auto-escalates `visit.priority` on abnormal vitals, Phase 3 §2)
- **Wizards:** None
- **Data files:** Vitals normal-range reference data
- **Tests:** BMI computation, abnormal-vitals auto-escalation, auto-transition to `waiting_doctor`
- **Demo data:** Vitals records for demo visits

---

## 4. `hospital_doctor`

**Purpose:** The clinical core — doctor queue, consultation workspace, prescription builder, lab/radiology ordering trigger points, admission trigger.

- **Dependencies:** `hospital_base`, `hospital_nurse`
- **Models:** `hospital.consultation`, `hospital.prescription`, `hospital.prescription.line`
- **Views:** Doctor Dashboard (queue + today's patients, OWL), Consultation workspace (single-screen history+notes+actions), Prescription builder widget
- **Menus:** "Doctor Workspace" menu: My Queue, My Patients, Consultations
- **Reports:** Prescription printout (QWeb)
- **Security:** `group_hospital_doctor`; record rule limiting edit to own consultations (Phase 9)
- **Controllers:** None
- **Services:** `ConsultationRoutingService` (Phase 3 §3 multi-branch routing logic), `VisitAggregateStateService`
- **Wizards:** `hospital.consultation.amend.wizard` (same-day amendment, audit-logged)
- **Data files:** ICD-10 code field config (no bundled dataset, per PRD out-of-scope)
- **Tests:** Outcome routing (prescribe/lab/radiology/admit combinations), aggregate state computation, amendment audit trail
- **Demo data:** 10 demo consultations across various outcomes

---

## 5. `hospital_pharmacy`

**Purpose:** Prescription fulfillment, dispensing, safety checks.

- **Dependencies:** `hospital_base`, `hospital_doctor`, `hospital_inventory`
- **Models:** none new (extends `hospital.prescription.line` with dispense methods)
- **Views:** Pharmacy Dashboard (pending queue, backorders), Dispense wizard
- **Menus:** "Pharmacy" menu: Dispensing Queue, Backorders
- **Reports:** Dispensing receipt (QWeb)
- **Security:** `group_hospital_pharmacist`
- **Controllers:** None
- **Services:** `DispensingSafetyService` (allergy/interaction check, Phase 3 §5), `StockMoveCreationService`
- **Wizards:** `hospital.prescription.dispense.wizard` (with override+reason flow for allergy conflicts/stock shortages)
- **Data files:** Pharmacy stock location defaults
- **Tests:** Allergy conflict blocking+override, partial dispense math, stock decrement correctness
- **Demo data:** Demo medicine stock levels

---

## 6. `hospital_inventory`

**Purpose:** Medicine/consumable catalog and stock management — thin clinical layer over Odoo's native Inventory app.

- **Dependencies:** `hospital_base`, `stock`, `product`
- **Models:** `hospital.medicine` (extension of `product.template`), `hospital.medicine.batch` (expiry/lot tracking, extends `stock.lot`)
- **Views:** Medicine catalog form (extends product form with clinical fields), Expiry/low-stock dashboard
- **Menus:** "Inventory" menu: Medicines, Stock Levels, Expiry Alerts
- **Reports:** Stock valuation (reuses Odoo Inventory reports), Low-stock report (QWeb)
- **Security:** `group_hospital_inventory_manager`
- **Controllers:** None
- **Services:** `ExpiryAlertService`, `LowStockAlertService` (scheduled actions / cron)
- **Wizards:** None v1
- **Data files:** Pharmacy warehouse + locations, medicine product category
- **Tests:** Expiry alert triggering, low-stock threshold logic
- **Demo data:** 50 demo medicines with varied stock/expiry

---

## 7. `hospital_lab`

**Purpose:** Laboratory order and result management.

- **Dependencies:** `hospital_base`, `hospital_doctor`
- **Models:** `hospital.lab.test`, `hospital.lab.order`, `hospital.lab.result`
- **Views:** Lab Dashboard (queue by priority), Sample collection form, Structured result entry grid
- **Menus:** "Laboratory" menu: Order Queue, Test Catalog, Results
- **Reports:** Lab report (QWeb, with abnormal-value highlighting)
- **Security:** `group_hospital_lab_tech`
- **Controllers:** None
- **Services:** `AbnormalResultFlagService`, `OrderCompletionNotifyService` (creates `mail.activity` for ordering doctor)
- **Wizards:** `hospital.lab.order.cancel.wizard`
- **Data files:** Default lab test catalog (CBC, glucose, lipid panel, etc.)
- **Tests:** Abnormal-range flagging, order-to-result state transitions, doctor notification firing
- **Demo data:** 15 demo lab orders across states

---

## 8. `hospital_radiology`

**Purpose:** Radiology order and result management. Structurally mirrors `hospital_lab`.

- **Dependencies:** `hospital_base`, `hospital_doctor`
- **Models:** `hospital.radiology.study`, `hospital.radiology.order`, `hospital.radiology.result`
- **Views:** Radiology Dashboard, Study scheduling form, Findings entry with attachment upload
- **Menus:** "Radiology" menu: Order Queue, Study Catalog, Results
- **Reports:** Radiology report (QWeb)
- **Security:** `group_hospital_radiology_tech`
- **Controllers:** None
- **Services:** `OrderCompletionNotifyService` (shared pattern with lab)
- **Wizards:** `hospital.radiology.order.cancel.wizard`
- **Data files:** Default study catalog (X-Ray Chest, CT Head, MRI Spine, etc.)
- **Tests:** Order-to-result flow, attachment handling
- **Demo data:** 10 demo radiology orders

---

## 9. `hospital_ipd`

**Purpose:** Inpatient admission, ward/bed management, transfers, discharge.

- **Dependencies:** `hospital_base`, `hospital_doctor`, `hospital_nurse`
- **Models:** `hospital.ward`, `hospital.bed`, `hospital.ipd.admission`, `hospital.bed.transfer`, `hospital.discharge`
- **Views:** Ward Dashboard (bed occupancy grid, color-coded), Admission form, Transfer wizard, Discharge summary form
- **Menus:** "IPD" menu: Wards & Beds, Admissions, Discharges
- **Reports:** Discharge summary (QWeb), Admission face-sheet (QWeb)
- **Security:** `group_hospital_ward_manager`
- **Controllers:** None
- **Services:** `BedAssignmentService`, `DischargeBlockingValidationService` (Phase 3 §4, Phase 5 §5.5 constraint), `LengthOfStayBillingService`
- **Wizards:** `hospital.ipd.admit.wizard`, `hospital.bed.transfer.wizard`, `hospital.discharge.wizard`
- **Data files:** Demo wards/beds, daily rate defaults
- **Tests:** One-active-admission-per-bed DB constraint, discharge-blocked-by-pending-orders, LOS billing computation
- **Demo data:** 3 wards, 60 beds, 5 demo admissions

---

## 10. `hospital_dashboard`

**Purpose:** Cross-department, role-specific dashboards and KPIs (admin-level rollups; per-department dashboards ship in their own modules per above — this module adds the **admin/executive cross-cutting view**).

- **Dependencies:** `hospital_base`, `hospital_reception`, `hospital_doctor`, `hospital_pharmacy`, `hospital_lab`, `hospital_radiology`, `hospital_ipd`
- **Models:** SQL view models (`_auto = False`): `hospital.dashboard.kpi` (patient volume, revenue, occupancy %, avg wait time)
- **Views:** Executive Dashboard (OWL, widget grid: KPI cards + trend charts)
- **Menus:** "Dashboard" top-level (admin-visible)
- **Reports:** None (interactive only)
- **Security:** `group_hospital_admin`
- **Controllers:** JSON data endpoint for dashboard widgets (`/hospital/dashboard/kpi_data`)
- **Services:** `KpiAggregationService` (wraps the SQL views)
- **Wizards:** None
- **Data files:** SQL view definitions (`init` hook creating the views)
- **Tests:** KPI numbers match underlying transactional data on seeded demo set
- **Demo data:** Relies on demo data from dependent modules

---

## 11. `hospital_reports`

**Purpose:** Centralizes shared/cross-module printable reports and report infrastructure (paper formats, shared headers/footers with hospital branding) so each clinical module's own reports (prescription, lab, discharge, etc.) share one consistent letterhead system.

- **Dependencies:** `hospital_base`, `hospital_doctor`, `hospital_pharmacy`, `hospital_lab`, `hospital_radiology`, `hospital_ipd`
- **Models:** `hospital.report.config` (letterhead, logo, footer text per company)
- **Views:** Report branding settings form
- **Menus:** Settings → Report Branding
- **Reports:** Shared QWeb base template (`hospital_report_layout`) inherited by all module-specific reports
- **Security:** `group_hospital_admin` for branding config
- **Tests:** Report renders without error across all report types on demo data
- **Demo data:** Default branding placeholder

---

## 12. `hospital_security`

**Purpose:** Hardens and centralizes cross-cutting security beyond per-module ACLs — audit log viewer UI, password/session policy configuration helpers, security group documentation.

- **Dependencies:** `hospital_base`
- **Models:** none new (UI layer over `hospital.audit.log` from `hospital_base`)
- **Views:** Audit Log viewer (admin-only, read-only list/form, filterable by model/user/date)
- **Menus:** Settings → Audit Logs
- **Security:** Enforces `hospital.audit.log` has zero `unlink` permission for any group, including admin (append-only by design, per Phase 5 §7.1)
- **Tests:** Confirm audit rows are created for patient/consultation/prescription/admission writes; confirm no group can delete audit rows
- **Demo data:** None (audit log populates from usage)

---

## 13–16. Future Roadmap Modules (not built in v1, listed only for naming/dependency reservation)

| Module | Purpose | Depends on |
|---|---|---|
| `hospital_api` | Curated REST/JSON-RPC endpoints for mobile/third-party | `hospital_base` + relevant clinical modules |
| `hospital_portal` | Patient self-service portal (appointments, bills, reports) | `portal`, `hospital_base`, `hospital_reception` |
| `hospital_mobile` | Native mobile app backend support | `hospital_api` |
| `hospital_telemedicine` | Video consultation scheduling/integration | `hospital_doctor` |

These are intentionally **not** part of the v1 build order (Phase 12) — listed here only so the dependency graph and naming convention are reserved and consistent if/when built.

---

## Module Summary Table

| # | Module | Tier | Core dependency |
|---|---|---|---|
| 1 | hospital_base | All | — |
| 2 | hospital_reception | Clinic+ | hospital_base |
| 3 | hospital_nurse | Clinic+ | hospital_base, hospital_reception |
| 4 | hospital_doctor | Clinic+ | hospital_nurse |
| 5 | hospital_inventory | Clinic+ | hospital_base, stock |
| 6 | hospital_pharmacy | Clinic+ | hospital_doctor, hospital_inventory |
| 7 | hospital_lab | Hospital+ | hospital_doctor |
| 8 | hospital_radiology | Hospital+ | hospital_doctor |
| 9 | hospital_ipd | Hospital+ | hospital_doctor, hospital_nurse |
| 10 | hospital_dashboard | Hospital+ | all clinical modules |
| 11 | hospital_reports | Hospital+ | all clinical modules |
| 12 | hospital_security | Enterprise | hospital_base |

(Tier mapping recap from Phase 1: **Clinic Edition** = 1–6; **Hospital Edition** = + 7–11; **Enterprise Edition** = + 12 and future API/portal/mobile.)

---

## Status

Module breakdown complete. Proceeding to Phase 7 — UX Design System.
