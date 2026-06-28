# Phase 12 — Implementation Order

All planning (Phases 1–11) is complete and approved. This document is the literal build order for the code that follows, restating the per-module completion bar and sequencing it precisely.

---

## 1. Per-Module Completion Bar

Every module, before being considered done, must:

1. **Install successfully** in a clean Odoo 19 instance with no manual SQL fixes.
2. **Pass tests** — unit + integration tests defined per Phase 10/11.
3. **Respect Odoo conventions** — Phase 11 coding standards, no core modification.
4. **Contain documentation** — `README.md` per Phase 11 §11.
5. **Contain demo data** — realistic seed data per Phase 6's per-module demo data spec.
6. **Contain security** — groups/ACLs/record rules per Phase 9, scoped to that module's models.
7. **Contain reports** — QWeb reports per Phase 6's per-module report list, themed via `hospital_reports`.
8. **Contain icons** — `static/description/icon.png` per Phase 11 folder structure.
9. **Contain README** — (restated for emphasis from the master prompt) — yes, explicitly required, not optional polish.

No module is generated "unfinished" — if a module's full scope is too large for one pass, it is still delivered as a complete, installable, working subset with the remainder clearly tracked as a follow-up, never half-wired code that fails to install.

---

## 2. Build Order (matches Phase 6 dependency graph and Phase 10 sprints)

| Order | Module | Depends on | Why this position |
|---|---|---|---|
| 1 | `hospital_base` | — | Everything else FKs into `hospital.patient`/`hospital.visit`. |
| 2 | `hospital_reception` | hospital_base | First point of patient entry into the system. |
| 3 | `hospital_nurse` | hospital_base, hospital_reception | Needed before doctor queue logic can be demonstrated end-to-end. |
| 4 | `hospital_doctor` | hospital_nurse | Core clinical decision point; everything downstream branches from here. |
| 5 | `hospital_inventory` | hospital_base, stock | Pharmacy depends on it; built first so dispensing has real stock to check against. |
| 6 | `hospital_pharmacy` | hospital_doctor, hospital_inventory | Consumes prescriptions from doctor module. |
| 7 | `hospital_lab` | hospital_doctor | Consumes lab orders from doctor module. |
| 8 | `hospital_radiology` | hospital_doctor | Mirrors lab; built right after for shared pattern reuse. |
| 9 | `hospital_ipd` | hospital_doctor, hospital_nurse | Most complex state machine; needs doctor (admission trigger) and nurse (ward rounds) already in place. |
| 10 | `hospital_dashboard` | all clinical modules | Aggregates data that must already exist. |
| 11 | `hospital_reports` | all clinical modules | Unifies reports that must already exist to be themed. |
| 12 | `hospital_security` | hospital_base | Hardening pass naturally comes after all models/views exist to audit. |

This order is now fixed. Implementation proceeds module-by-module in exactly this sequence.

---

## 3. What Happens Next

With Phases 1–12 complete, the next action is generating the actual addon code, starting with `hospital_base`, following:
- Phase 5 for exact model/field/constraint definitions,
- Phase 6 for exact view/menu/security/report scope per module,
- Phase 7/8 for UI implementation detail,
- Phase 9 for security implementation,
- Phase 11 for code style and folder structure,
- This document for sequencing and the completion bar.

No further planning documents are needed before code begins — per explicit instruction, proceeding directly into implementation now.

---

## Status

All 12 planning phases complete. Beginning code generation with `hospital_base`.
