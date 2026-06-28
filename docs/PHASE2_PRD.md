# Phase 2 — Product Requirements Document (PRD)

**Product:** MediCore HMS for Odoo 19
**Status:** Approved baseline (per Phase 1)

---

## 1. Problem Statement

Hospitals — especially small-to-mid-size private hospitals and clinics — run patient operations across disconnected tools: paper registers, spreadsheets, standalone billing software, and legacy desktop HMS products with no real ERP backbone. This causes:

- Patients re-stating the same information at reception, nursing, doctor, pharmacy, and billing.
- No single timeline of a patient's visit — vitals, consultation notes, prescriptions, lab orders, and bills live in separate systems or paper trails.
- Manual, error-prone routing between departments (a nurse walks a paper chart to the doctor; pharmacy re-types a handwritten prescription).
- No real-time visibility into bed occupancy, queue length, or stock levels for hospital administrators.
- Existing Odoo-based HMS add-ons in the market are typically thin, duplicate patient data per module, and use generic unstyled Odoo forms that feel like back-office software, not clinical tools.

**Core problem to solve:** give hospitals one connected system, built on a real ERP (Odoo), where a patient is represented once and every department's work attaches to that single record automatically, with a UI fast and pleasant enough that clinical staff actually prefer it over paper.

---

## 2. Objectives

| # | Objective | Measurable target |
|---|---|---|
| O1 | Single unified patient record across all departments | 0 duplicate patient masters; 1 `hospital.patient` per individual, enforced by identity matching at registration |
| O2 | Automated workflow handoff between departments | Reception → Nurse → Doctor → Pharmacy/Lab/Radiology → IPD → Discharge transitions require zero manual "send to next department" data re-entry |
| O3 | Premium, fast, modern UX | Core screens (registration, queue, consultation, prescription) load and respond in <300ms on standard hardware; UI usability validated against Phase 7/8 design system |
| O4 will| Production-grade security & auditability | Full RBAC, record rules, and audit logging on all clinical models (Phase 9) |
| O5 | Commercial packaging | Modules installable independently in tiers (Clinic / Hospital / Enterprise) per Phase 1 |
| O6 | Scale to enterprise hospital size | 1M+ patient records, 100+ concurrent users, sub-second search (Phase 5/12 performance work) |

---

## 3. Functional Requirements

### 3.1 Patient & Registration
- FR-1: Register a new patient with demographic, contact, identity (national ID/passport), and emergency contact data.
- FR-2: Search existing patients by name, phone, ID number, or patient code with fuzzy/partial match, returning results in <1s at 1M-record scale.
- FR-3: Prevent duplicate patient masters via identity-matching warning (same ID number / same name+DOB+phone) at registration time — non-blocking but visible.
- FR-4: Every patient interaction (OPD visit or IPD admission) creates a `hospital.visit` linked to the one `hospital.patient`.
- FR-5: Patient profile shows complete chronological history: visits, vitals, consultations, prescriptions, lab/radiology orders, admissions, invoices.

### 3.2 Reception / Front Desk
- FR-6: Create a new visit (walk-in or scheduled appointment) and assign it to a doctor/department queue.
- FR-7: View and manage a live waiting queue per doctor/department.
- FR-8: Capture/verify billing-relevant info (payer type: cash/insurance) at registration.
- FR-9: Print/generate a visit token / queue ticket.

### 3.3 Nurse Station
- FR-10: Record vitals (BP, temperature, pulse, SpO2, height, weight, BMI auto-computed, respiratory rate) against the active visit.
- FR-11: Vitals submission automatically advances the visit to the doctor's queue — no manual "send to doctor" step beyond a deliberate confirm action.
- FR-12: Nurse can flag a visit urgent (triage priority), which reorders the doctor's queue.
- FR-13 (IPD): Nurses log ward rounds, administer-medication confirmations, and task checklists against admitted patients.

### 3.4 Doctor Workspace
- FR-14: Doctor sees prioritized queue of waiting patients (with triage flag, wait time, latest vitals visible inline).
- FR-15: Consultation screen shows full patient history (previous visits, prescriptions, allergies, lab/radiology results) on one screen — no tab-hopping required for the common case.
- FR-16: Doctor records diagnosis (ICD-10 optional code + free text), clinical notes, and the consultation outcome (discharge / prescribe / order lab / order radiology / admit).
- FR-17: Prescription builder: add medicines with dosage, frequency, duration, and route; supports searching `hospital.medicine` master with stock-on-hand visibility.
- FR-18: Doctor can order one or more lab tests and/or radiology studies directly from the consultation screen; orders are timestamped and linked to the visit.
- FR-19: Doctor can trigger IPD admission directly from consultation, carrying over diagnosis and initial orders.
- FR-20: Completing a consultation automatically routes the visit to the next relevant queue (pharmacy if prescribed, lab if ordered, IPD if admitted, or closed if discharged) — automatically, without manual status flips by staff.

### 3.5 Pharmacy
- FR-21: Pharmacy queue shows all visits with pending prescriptions.
- FR-22: Pharmacist dispenses medicine against a prescription line, decrementing stock via Odoo inventory (`stock.move`) automatically.
- FR-23: System blocks/warns dispensing if stock is insufficient, expired, or a recorded drug allergy/interaction conflict exists for the patient.
- FR-24: Partial dispensing supported (e.g., out-of-stock item dispensed later) with full line-level status tracking.
- FR-25: Dispensing automatically generates/updates the billing line for that visit.

### 3.6 Laboratory
- FR-26: Lab queue shows pending orders grouped by test type/priority.
- FR-27: Lab technician records sample collection (timestamp, sample type, barcode/ID).
- FR-28: Result entry against structured test parameters (normal range, flag out-of-range automatically) or free-text/attached report (PDF/image).
- FR-29: Completed results are immediately visible on the patient's record and notify the ordering doctor.

### 3.7 Radiology
- FR-30: Radiology queue shows pending imaging orders.
- FR-31: Technician records study performed and attaches images/report (DICOM viewer integration is future roadmap; v1 supports PDF/image attachment + structured findings text).
- FR-32: Completed studies visible on patient record, notify ordering doctor.

### 3.8 IPD (Inpatient) — Admission, Ward, Bed, Discharge
- FR-33: Admit a patient to a ward/bed from a doctor's order; bed must be unoccupied (enforced by constraint).
- FR-34: Real-time bed occupancy dashboard per ward (occupied/vacant/reserved/cleaning).
- FR-35: Support patient transfer between beds/wards with full audit trail.
- FR-36: Nurse charting: vitals, medication administration record (MAR), and care notes during the stay.
- FR-37: Doctor generates a discharge summary (diagnosis, treatment given, discharge medication, follow-up instructions) which closes the admission and frees the bed.
- FR-38: Discharge automatically finalizes all pending billing lines for the stay (room charges computed from length-of-stay × ward rate, consumed medicines, lab/radiology charges, doctor fees).

### 3.9 Billing & Inventory Integration
- FR-39: Every billable clinical event (consultation, prescription dispensing, lab/radiology order, bed-day) generates a draft invoice line tied to the visit/admission, consolidated into one invoice per visit (or per admission for IPD), using Odoo's native `account.move`.
- FR-40: Medicine and consumable stock is tracked via Odoo's native inventory (`stock.quant`/`stock.move`), with low-stock and expiry alerts.

### 3.10 Dashboards & Reporting
- FR-41: Role-specific dashboards: Reception (queue/today's visits), Doctor (my queue, my patients today), Pharmacy (pending prescriptions, low stock), Lab/Radiology (pending orders), Ward (bed occupancy), Admin (cross-department KPIs: patient volume, revenue, occupancy rate, average wait time).
- FR-42: Standard printable reports: prescription, lab report, radiology report, discharge summary, invoice — all as QWeb reports.

### 3.11 Administration
- FR-43: Configure departments, doctors, doctor schedules/availability, wards, beds, medicines, lab test catalog, radiology study catalog.
- FR-44: Manage users and role assignments (mapped to Odoo security groups, Phase 9).
- FR-45: View audit logs of sensitive actions (who viewed/edited a patient record, when).

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **NFR-1 Performance** | Core list/search views return in <1s at 1M patient records; dashboards in <2s; see Phase 5/12 for indexing/SQL approach. |
| **NFR-2 Availability** | Designed for standard Odoo.sh / on-prem HA deployment patterns (multi-worker, load-balanced); no architectural blocker to HA. |
| **NFR-3 Usability** | New reception staff productive within 30 minutes of training (driven by UX simplicity, Phase 7/8). |
| **NFR-4 Maintainability** | 100% custom addons, no core overrides; each module independently upgradable; full test coverage on business-critical flows (Phase 11). |
| **NFR-5 Compatibility** | Targets Odoo 19 Community + Enterprise; modules degrade gracefully without Enterprise-only features where reasonably possible. |
| **NFR-6 Internationalization** | All user-facing strings translatable (`_()`), multi-language and multi-timezone support via Odoo's native i18n. |
| **NFR-7 Auditability** | All create/write/unlink on clinical models logged with user, timestamp, and (for sensitive fields) before/after values. |
| **NFR-8 Data Integrity** | Database-level constraints (SQL `CHECK`, unique, foreign key) backing every business rule that must never be violated (e.g., one active bed occupant). |

---

## 5. Security Requirements

(Full design in Phase 9; PRD-level requirements below.)

- SR-1: Role-based access control mapped to real hospital roles (Reception, Nurse, Doctor, Pharmacist, Lab Tech, Radiology Tech, Ward Manager, Admin, IT Admin).
- SR-2: Record rules ensure, e.g., a doctor only edits consultations they authored or are assigned to; multi-company record rules isolate branches in hospital groups.
- SR-3: Sensitive patient fields (national ID, diagnosis, full history) restricted from roles that don't need them (e.g., pharmacy sees prescriptions, not full diagnosis notes, unless granted).
- SR-4: All authentication goes through Odoo's native auth (with 2FA support where available); no custom auth bypass.
- SR-5: CSRF, XSS, SQL injection prevention follow Odoo framework defaults — no raw SQL string interpolation, no `t-raw` on unsanitized user input.
- SR-6: Full audit trail (`mail.thread`/custom audit log) on patient, consultation, prescription, and admission models.
- SR-7: Password policy and brute-force protection via Odoo's built-in mechanisms (lockout, complexity) configured, not reimplemented.

---

## 6. Performance Requirements

- PR-1: Patient search (name/phone/ID) <1s at 1M records via proper btree/GIN trigram indexes.
- PR-2: Dashboard aggregate queries (queue counts, bed occupancy, revenue) use SQL views or `read_group`, not Python loops over recordsets.
- PR-3: List views default to limited initial load with server-side pagination; no unbounded `search()` without limit in hot paths.
- PR-4: Support 100 concurrent users on a standard multi-worker Odoo deployment (e.g., 4–8 workers) without queue screen lag.
- PR-5: Heavy computed fields (e.g., patient history aggregates) are `store=True` with explicit `compute`/`depends`, not recomputed on every view render.

---

## 7. Accessibility

- AC-1: All interactive elements reachable via keyboard (tab order, focus states) — supports keyboard-first power users (reception, pharmacy).
- AC-2: Color is never the sole signal for status (status chips carry icon + text + color, for color-blind users).
- AC-3: Minimum WCAG AA contrast ratios in the design system (Phase 7 palette).
- AC-4: Font sizes and touch targets sized for tablet use by nurses/doctors (≥44px touch targets on tablet views).
- AC-5: Form error messages are explicit and field-associated, not just color changes.

---

## 8. Scalability

(Detailed in Phase 1 §7 and Phase 5/12.) PRD-level commitment: the data model and indexing strategy must be designed up front for 1M+ patients and 100+ concurrent users — not retrofitted after a pilot. Multi-company architecture supports hospital chains without a data model rewrite.

---

## 9. User Personas

1. **Asha — Reception Executive.** Handles 150+ walk-ins/day. Needs: fastest possible registration and queue assignment, keyboard shortcuts, minimal screens.
2. **Nurse Imani — OPD/Ward Nurse.** Uses a tablet at bedside. Needs: large touch targets, quick vitals entry, ward task list.
3. **Dr. Castillo — General Physician.** Sees 40+ patients/day in OPD. Needs: full patient history at a glance, fast prescription building, minimal typing.
4. **Pharmacist Wei.** Dispenses 200+ prescriptions/day. Needs: clear pending queue, stock visibility, safety alerts that don't create alert fatigue.
5. **Lab Tech Fatima.** Processes 80+ samples/day. Needs: clear order queue, fast structured result entry.
6. **Ward Manager Tomás.** Oversees 60 beds across 3 wards. Needs: real-time occupancy grid, fast admission/transfer/discharge actions.
7. **Hospital Administrator Mrs. Okafor.** Owns the P&L. Needs: cross-department KPI dashboard, revenue/occupancy/wait-time trends.
8. **IT Admin Raj.** Maintains the system. Needs: clear security/audit tooling, manageable upgrade path, no core hacks to maintain.

---

## 10. User Stories (representative sample)

- As a **receptionist**, I want to search a patient by phone number and see if they already exist, so I never create a duplicate record.
- As a **nurse**, I want vitals entry to automatically push the patient into the doctor's queue, so I don't have to notify the doctor manually.
- As a **doctor**, I want to see the patient's last 3 visits and any flagged allergies on the same screen as the consultation form, so I don't miss critical history.
- As a **doctor**, I want to order a lab test and have it appear instantly in the lab queue, so there's no delay or paper handoff.
- As a **pharmacist**, I want to be warned if a prescribed medicine conflicts with a recorded allergy before I dispense it.
- As a **ward manager**, I want a live grid of all beds color-coded by status, so I can find an available bed in seconds.
- As a **hospital administrator**, I want a single dashboard showing today's patient volume, revenue, and bed occupancy, so I don't have to ask each department for numbers.
- As an **IT admin**, I want an audit log of who accessed a specific patient's record, so I can respond to a privacy inquiry.

---

## 11. Acceptance Criteria (representative sample, tied to FRs)

- **FR-3 (duplicate prevention):** Given a patient with the same national ID already exists, registering a new patient with that ID shows a non-blocking warning with a link to the existing record, and requires explicit confirmation to proceed.
- **FR-11 (auto-queue to doctor):** Given a nurse submits vitals for a visit in "Nurse" stage, the visit's stage automatically becomes "Doctor Queue" with no additional user action, and it appears in the assigned doctor's queue view within the same transaction.
- **FR-20 (auto-routing post-consultation):** Given a doctor marks a consultation outcome as "Prescribe + Lab," the visit simultaneously appears in both the Pharmacy queue and the Lab queue, and the doctor's own queue no longer shows it as pending.
- **FR-22/FR-23 (dispensing stock check):** Given a prescription line for a medicine with 0 stock-on-hand, the pharmacist cannot mark it "Dispensed" without an explicit override action that is itself audit-logged.
- **FR-33 (bed admission constraint):** Given Bed A is occupied, attempting to admit a second patient to Bed A is rejected at the database constraint level, not just UI validation.
- **FR-38 (discharge billing):** Given a discharge summary is confirmed, an invoice is generated containing room charges (computed from admission/discharge timestamps × ward daily rate), all dispensed medicines, and all ordered lab/radiology services for that admission.

---

## 12. Success Metrics

| Metric | Target |
|---|---|
| Average OPD patient cycle time (registration → discharge from doctor) | Reduced vs. paper baseline by measurable %, tracked via timestamps already captured by the workflow (no extra instrumentation needed) |
| Duplicate patient record rate | <1% of new registrations flagged as likely duplicates and not merged |
| Staff time-to-productivity (new hire) | <30 minutes guided onboarding to perform their core role's primary task |
| Dashboard load time | <2s at target scale (1M patients, 100 concurrent users) |
| Module install success rate | 100% — every module installs cleanly in a fresh Odoo 19 instance with demo data, no manual SQL fixes |
| Audit coverage | 100% of patient/consultation/prescription/admission writes captured in audit log |

---

## 13. Future Roadmap (explicitly out of v1, tracked for later)

- `hospital_api` — REST/JSON-RPC API layer for third-party and mobile integration.
- `hospital_portal` — patient self-service portal (appointments, bills, reports, history) on Odoo's portal framework.
- `hospital_mobile` — native mobile app for doctors/nurses consuming `hospital_api`.
- Telemedicine module (video consultation scheduling + integration with a video provider).
- DICOM image viewer integration for radiology (v1 ships PDF/image attachment only).
- National health registry / HL7-FHIR interoperability (market-specific, not generalizable to v1).
- Insurance claims/TPA integration workflows beyond basic payer-type tagging.
- Medical device direct data ingestion (vitals monitors, etc.).

---

## 14. Out of Scope (v1, explicit)

- Formal HIPAA/GDPR legal certification (we build HIPAA-inspired/GDPR-ready practices; certification is an organizational/legal process, not a software deliverable).
- Multi-language clinical terminology databases (ICD-10 code field is supported and optional; we do not ship a full bundled ICD-10/SNOMED dataset in v1 — integration point left open).
- Offline-first/disconnected operation (assumes reasonably reliable network to the Odoo server; rural offline-tolerant mode is future roadmap per Phase 1).
- Native mobile app, patient portal, API layer, telemedicine (see §13).

---

## Status

Approved per instruction. Proceeding to Phase 3 — Hospital Workflow Analysis.
