# Phase 10 — Development Plan

Sprints are 2 weeks each, sized for a small focused team (2–3 Odoo developers + 1 QA, with the architect/healthcare-consultant roles advisory throughout). Order matches the module dependency graph (Phase 4 §2, Phase 6 build order).

---

## Sprint 0 — Environment & Foundations (1 week, not a full sprint)

- **Goals:** Odoo 19 dev environment running, repo/CI scaffolding, coding standards enforced from commit 1.
- **Deliverables:** Git repo structure (`addons/`, `docs/`), Odoo 19 + PostgreSQL local/dev setup, pre-commit hooks (lint, format), CI pipeline skeleton (Phase 11/DevOps).
- **Risks:** Environment drift between dev machines — mitigated with a documented `docker-compose` dev setup.
- **Testing:** CI runs a trivial "module list installs" smoke test.
- **Definition of Done:** A developer can clone, run one command, and have Odoo 19 running with an empty `hospital_base` stub installed.

---

## Sprint 1 — `hospital_base` Core

- **Goals:** Patient and Visit spine fully modeled, secured, and demo-able.
- **Deliverables:** `hospital.patient`, `hospital.visit`, `hospital.department`, `hospital.doctor`, audit mixin, sequences, base groups/ACLs, basic form/list views, demo data.
- **Estimated duration:** 2 weeks.
- **Risks:** Getting the `hospital.visit` state machine right early matters most — a late change here ripples into every other module. Mitigation: lock Phase 3/5 contract before coding (already done).
- **Testing:** Unit tests for patient creation, duplicate-warning logic, visit state transitions, SQL constraint tests (sequence uniqueness).
- **Definition of Done:** Module installs cleanly, demo data loads, all unit tests pass, patient/visit CRUD works via UI.

---

## Sprint 2 — `hospital_reception`

- **Goals:** Registration and queue UX functional end-to-end.
- **Deliverables:** Reception Dashboard (OWL), Registration form, Queue kanban, Appointment model+calendar, queue-ticket report.
- **Estimated duration:** 2 weeks.
- **Risks:** OWL dashboard performance with live queue updates — mitigate by prototyping the bus-push pattern early (Phase 4 §3) rather than at the end.
- **Testing:** Registration flow E2E test, duplicate-detection test, queue assignment test.
- **Definition of Done:** A receptionist can register a patient and see them appear correctly prioritized in the right doctor's queue, live, without refresh.

---

## Sprint 3 — `hospital_nurse`

- **Goals:** Vitals capture and auto-routing to doctor.
- **Deliverables:** `hospital.vitals` model, Nurse Dashboard (tablet mode), Vitals quick-entry, abnormal-vitals auto-escalation logic.
- **Estimated duration:** 2 weeks.
- **Risks:** Tablet UX needs real device testing, not just browser resize — schedule actual tablet QA pass this sprint, not deferred.
- **Testing:** BMI computation tests, range-validation constraint tests, auto-transition-to-doctor-queue integration test.
- **Definition of Done:** Vitals entered on a tablet correctly and immediately move the visit into the doctor's queue with correct priority.

---

## Sprint 4 — `hospital_doctor` (Part 1: Consultation)

- **Goals:** Doctor queue + consultation workspace with full patient context on one screen.
- **Deliverables:** Doctor Dashboard, Consultation form, 3-pane workspace layout, history/allergy panel.
- **Estimated duration:** 2 weeks.
- **Risks:** "One screen, full context" (Phase 7 principle) is the hardest UX bar in the product — budget extra design-review time.
- **Testing:** Consultation creation, history panel correctness against demo data with multiple prior visits.
- **Definition of Done:** Doctor can review full history and record a diagnosis without leaving the consultation screen.

---

## Sprint 5 — `hospital_doctor` (Part 2: Prescription + Routing)

- **Goals:** Prescription builder and multi-branch outcome routing (Phase 3 §3).
- **Deliverables:** Prescription builder widget, `ConsultationRoutingService`, `VisitAggregateStateService`, amendment wizard.
- **Estimated duration:** 2 weeks.
- **Risks:** Aggregate state computation across prescription/lab/radiology completion is the trickiest business logic in the whole system — needs thorough integration tests, not just unit tests.
- **Testing:** Every outcome combination from Phase 3 §3 (prescribe-only, lab-only, prescribe+lab+radiology, admit, discharge-only) as integration tests.
- **Definition of Done:** A consultation with multiple outcomes correctly appears in all relevant queues and the visit only reaches "billing" state when all branches are done.

---

## Sprint 6 — `hospital_inventory` + `hospital_pharmacy`

- **Goals:** Medicine catalog on real Odoo Inventory, dispensing with safety checks.
- **Deliverables:** `hospital.medicine` (product extension), stock locations, Pharmacy Dashboard, dispense wizard, allergy/stock safety checks.
- **Estimated duration:** 2 weeks (may split into two 2-week sprints if stock integration proves complex — flagged risk below).
- **Risks:** Integrating cleanly with Odoo's `stock.move`/`stock.picking` without fighting its existing workflow is the main risk — mitigate by prototyping the dispense-to-stock-move path in Sprint 5 spike time if possible.
- **Testing:** Dispense decrements stock correctly, partial dispense math, allergy-conflict override audit trail.
- **Definition of Done:** Pharmacist dispenses a prescription and Odoo's native inventory valuation/stock levels update correctly.

---

## Sprint 7 — `hospital_lab` + `hospital_radiology`

- **Goals:** Order-to-result flow for both diagnostic departments.
- **Deliverables:** Both modules per Phase 6 §7/§8, structured result entry, abnormal flagging, doctor notification on completion.
- **Estimated duration:** 2 weeks (built together since they share the same structural pattern).
- **Risks:** Low — most novel logic (abnormal flagging) is straightforward range comparison.
- **Testing:** Result-entry correctness, abnormal flag triggering, notification firing to the correct ordering doctor.
- **Definition of Done:** Orders placed from consultation appear instantly in the correct queue; completed results appear on the patient timeline and notify the doctor.

---

## Sprint 8 — `hospital_ipd`

- **Goals:** Full admission → ward → discharge lifecycle.
- **Deliverables:** Ward/Bed models, Ward Dashboard (occupancy grid), Admission wizard, Transfer wizard, Discharge wizard with blocking-items validation, LOS billing computation.
- **Estimated duration:** 3 weeks (most complex single module — state machine + billing + the one-bed-one-admission DB constraint).
- **Risks:** The DB-level partial unique index (Phase 5 §5.2) must be tested under concurrent admission attempts, not just sequential — schedule a concurrency test explicitly.
- **Testing:** Concurrent-admission race condition test, discharge-blocked-by-pending-orders test, LOS billing accuracy test, bed-transfer audit trail test.
- **Definition of Done:** Two simultaneous admission attempts to the same bed — only one succeeds, with a clean error for the other; discharge correctly blocks on pending orders and correctly bills on confirm.

---

## Sprint 9 — `hospital_dashboard` + `hospital_reports`

- **Goals:** Executive KPI dashboard and unified report branding/infrastructure.
- **Deliverables:** SQL view models for KPIs, Executive Dashboard OWL widgets, shared QWeb report layout, all module-specific reports re-themed onto it.
- **Estimated duration:** 2 weeks.
- **Risks:** SQL view performance at scale should be load-tested against a 1M-row seeded dataset, not just demo data (Phase 5 §10 commitment).
- **Testing:** KPI accuracy against known seeded dataset, dashboard load time benchmark (<2s target, PRD NFR-1).
- **Definition of Done:** Admin dashboard loads in under 2 seconds against a 1M-patient seeded dataset and all KPI numbers are verifiably correct.

---

## Sprint 10 — `hospital_security` + Hardening Pass

- **Goals:** Audit log viewer, security review, penetration-style review of CSRF/XSS/SQLi surface across all modules built so far.
- **Deliverables:** Audit Log viewer UI, confirmed zero-unlink-on-audit-log enforcement, full security review (Phase 9 checklist) across every module.
- **Estimated duration:** 2 weeks.
- **Risks:** Security review may surface findings requiring rework in earlier modules — budget contingency time here, this sprint is intentionally last-before-launch for that reason.
- **Testing:** Security review checklist (Phase 9 §11) run against every controller/view/report; automated scan for raw SQL string interpolation across the codebase.
- **Definition of Done:** No findings above "low" severity remain open; audit log proven tamper-resistant (no group can unlink).

---

## Sprint 11 — Polish, Performance, Demo Data, Launch Readiness

- **Goals:** Final UX polish pass against Phase 7/8 spec, 1M-record performance validation, full demo dataset, READMEs, packaging per tier (Clinic/Hospital/Enterprise).
- **Estimated duration:** 2 weeks.
- **Risks:** Scope creep from "just one more polish item" — hard cut-off enforced by this being the last sprint before the Phase 12 implementation order is considered complete.
- **Testing:** Full regression pass across all modules, accessibility audit (Phase 2 §7 AC criteria), load test at 100 concurrent simulated users.
- **Definition of Done:** All modules from Phase 6 install cleanly in a fresh Odoo 19 instance, pass tests, meet performance targets, and are packaged per tier with README/demo data/icons — i.e., the Phase 12 "every module must" checklist is satisfied for all twelve v1 modules.

---

## Sprint Summary Table

| Sprint | Module(s) | Duration |
|---|---|---|
| 0 | Environment setup | 1 week |
| 1 | hospital_base | 2 weeks |
| 2 | hospital_reception | 2 weeks |
| 3 | hospital_nurse | 2 weeks |
| 4 | hospital_doctor (consultation) | 2 weeks |
| 5 | hospital_doctor (prescription + routing) | 2 weeks |
| 6 | hospital_inventory + hospital_pharmacy | 2 weeks |
| 7 | hospital_lab + hospital_radiology | 2 weeks |
| 8 | hospital_ipd | 3 weeks |
| 9 | hospital_dashboard + hospital_reports | 2 weeks |
| 10 | hospital_security + hardening | 2 weeks |
| 11 | Polish + performance + launch readiness | 2 weeks |

**Total estimated duration:** ~24 weeks (~6 months) for a small dedicated team to reach a launch-ready v1 covering all twelve modules in Phase 6.

---

## Status

Development plan complete. Proceeding to Phase 11 — Coding Standards.
