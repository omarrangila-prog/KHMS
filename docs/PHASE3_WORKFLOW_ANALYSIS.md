# Phase 3 — Hospital Workflow Analysis

This phase defines every workflow state, transition, edge case, and exception across the patient journey. These diagrams are the contract that Phase 5 (database design — `state` fields, constraints) and Phase 6 (module automation logic) must implement exactly.

---

## 1. Master End-to-End Patient Journey (OPD happy path)

```mermaid
flowchart TD
    A[Patient Arrives] --> B{Existing Patient?}
    B -->|Search by phone/ID/name| C[Found: Select Existing hospital.patient]
    B -->|Not found| D[Register New hospital.patient]
    C --> E[Create hospital.visit - OPD]
    D --> E
    E --> F[Assign Doctor/Department + Queue Token]
    F --> G[Stage: Waiting - Reception]
    G --> H[Nurse Calls Patient]
    H --> I[Record Vitals - hospital.vitals]
    I --> J[Stage: Waiting - Doctor auto-transition]
    J --> K[Doctor Calls Patient]
    K --> L[Consultation - hospital.consultation]
    L --> M{Doctor Decision}
    M -->|Discharge, no meds| N[Stage: Billing]
    M -->|Prescribe| O[Create hospital.prescription]
    M -->|Order Lab| P[Create hospital.lab.order]
    M -->|Order Radiology| Q[Create hospital.radiology.order]
    M -->|Admit| R[Create hospital.ipd.admission]
    O --> S[Stage: Pharmacy Queue]
    P --> T[Stage: Lab Queue]
    Q --> U[Stage: Radiology Queue]
    S --> V[Pharmacist Dispenses]
    T --> W[Lab Result Entered]
    U --> X[Radiology Result Entered]
    V --> N
    W --> N
    X --> N
    R --> Y[IPD Workflow - see Section 4]
    N --> Z[Invoice Generated - account.move]
    Z --> AA[Visit Closed - Stage: Done]
    AA --> AB[Patient History Updated - hospital.patient timeline]
```

**Key rule:** every box after "Create hospital.visit" reads/writes the *same* `patient_id` and `visit_id` foreign keys. No department creates its own patient or visit record.

---

## 2. Reception → Nurse → Doctor (detailed, with edge cases)

```mermaid
flowchart TD
    A[Reception: New Visit] --> B[Visit.state = draft]
    B --> C[Reception confirms visit]
    C --> D[Visit.state = waiting_nurse]
    D --> E{Triage urgent?}
    E -->|Yes| F[Visit.priority = urgent, reorders nurse queue]
    E -->|No| G[Visit.priority = normal]
    F --> H[Nurse Queue]
    G --> H
    H --> I[Nurse opens visit, records hospital.vitals]
    I --> J{Vitals within safe range?}
    J -->|Abnormal e.g. very high BP/temp| K[Auto-flag Visit.priority = urgent]
    J -->|Normal| L[Visit.priority unchanged]
    K --> M[Visit.state = waiting_doctor]
    L --> M
    M --> N[Doctor Queue, sorted by priority then check-in time]
    N --> O{Doctor available?}
    O -->|Yes| P[Doctor opens consultation]
    O -->|No doctor on leave/overloaded| Q[Reception reassigns Visit.doctor_id]
    Q --> N
    P --> R[Consultation flow - Section 3]
```

**Edge cases covered:**
- Walk-in with no appointment vs. pre-booked appointment (both converge to the same `waiting_nurse` state; appointment just pre-fills `doctor_id`).
- Patient leaves before being called: Reception can set `Visit.state = cancelled` from any pre-consultation state (cancellation reason required).
- Doctor unavailable mid-day: visit reassignment is a explicit reception action, never silent.
- Abnormal vitals auto-escalate priority — this is the one place nurse data triggers an automatic *business* decision (urgent flag), not just a state transition.

---

## 3. Consultation → Multi-Branch Routing

```mermaid
flowchart TD
    A[Doctor opens Consultation] --> B[Review: history, vitals, allergies on one screen]
    B --> C[Doctor enters diagnosis + notes]
    C --> D{Outcome selection - multi-select}
    D -->|Prescribe| E[hospital.prescription created, state=draft]
    D -->|Lab Order| F[hospital.lab.order created, state=ordered]
    D -->|Radiology Order| G[hospital.radiology.order created, state=ordered]
    D -->|Admit| H[hospital.ipd.admission created, state=requested]
    D -->|Discharge only| I[No sub-record created]
    E --> J[Consultation.state = done]
    F --> J
    G --> J
    H --> J
    I --> J
    J --> K{Any of: prescription/lab/radiology open AND not admitted?}
    K -->|Yes| L[Visit.state = in_progress_multi - visible in relevant queues simultaneously]
    K -->|No, admitted| M[Visit.state = admitted, removed from OPD queues]
    K -->|No, discharge only| N[Visit.state = billing]
    L --> O{All sub-records completed?}
    O -->|No| L
    O -->|Yes| N
    N --> P[Invoice consolidated]
    P --> Q[Visit.state = done]
```

**Edge cases:**
- A visit can be simultaneously in the Pharmacy queue and Lab queue — `Visit.state = in_progress_multi` is a computed/aggregate state; the *real* per-branch status lives on each sub-record (`prescription.state`, `lab.order.state`). The visit only flips to `billing` when **all** branches report `done` or `cancelled`.
- Doctor can re-open a "done" consultation same-day to add a forgotten order (audit-logged amendment), which re-opens the visit from `billing` back to `in_progress_multi`.
- If a lab/radiology order is cancelled by the ordering doctor before being acted on, it's excluded from the "all branches completed" check.

---

## 4. IPD: Admission → Ward → Discharge

```mermaid
flowchart TD
    A[Admission Requested by Doctor] --> B[hospital.ipd.admission state=requested]
    B --> C[Ward Manager selects Ward + Bed]
    C --> D{Bed available?}
    D -->|No free bed| E[Admission stays state=waiting_for_bed, visible on Ward dashboard]
    D -->|Yes| F[Bed.state = occupied, Admission.state = admitted]
    E --> G{Bed freed elsewhere?}
    G -->|Yes| C
    F --> H[Patient in Ward]
    H --> I[Nurse: vitals rounds, MAR, care notes - recurring]
    H --> J{Doctor orders during stay}
    J -->|New prescription| K[hospital.prescription linked to admission_id]
    J -->|New lab/radiology| L[Same as OPD ordering, linked to admission_id]
    J -->|Transfer ward/bed| M[hospital.bed.transfer record, old bed freed, new bed occupied]
    K --> H
    L --> H
    M --> H
    H --> N{Doctor decides discharge}
    N --> O[hospital.discharge created, state=draft]
    O --> P[Discharge summary: diagnosis, treatment, meds, follow-up]
    P --> Q{All pending orders closed?}
    Q -->|No - e.g. lab result pending| R[Block discharge confirm, show blocking items]
    Q -->|Yes| S[Discharge confirmed]
    S --> T[Admission.state = discharged]
    T --> U[Bed.state = cleaning then vacant]
    T --> V[Invoice consolidated: room charge by LOS x ward rate + all meds + all services]
    V --> W[Visit.state = done]
    W --> X[Patient history updated]
```

**Edge cases:**
- No bed available at request time: admission is queued (`waiting_for_bed`), visible to ward managers across all wards (not stuck invisibly).
- Discharge is **blocked at the workflow level** (not just a warning) if there are unresolved lab/radiology orders or undispensed prescriptions tied to the admission — Phase 5 will back this with a model-level constraint/validation, not just UI.
- Death-in-care / against-medical-advice (AMA) discharge are discharge *sub-types* (`discharge.type` field), not separate workflows — they still go through the same bed-release and billing-finalization path, with different printed summary templates.
- Bed transfer mid-stay never creates a new admission record — it's a child `hospital.bed.transfer` row under the same `hospital.ipd.admission`, preserving one continuous stay record.

---

## 5. Pharmacy Dispensing Detail (with safety exceptions)

```mermaid
flowchart TD
    A[Prescription appears in Pharmacy Queue] --> B[Pharmacist opens prescription]
    B --> C{Check patient allergy list}
    C -->|Conflict found| D[Hard warning shown, requires override + reason]
    C -->|No conflict| E[Continue]
    D --> E
    E --> F{Stock available for line?}
    F -->|Yes| G[Dispense line: stock.move created, line.state=dispensed]
    F -->|No| H{Partial stock?}
    H -->|Yes| I[Dispense available qty, line.state=partial]
    H -->|No| J[line.state=backordered, visible on pharmacy backorder report]
    I --> K[Remaining qty stays backordered]
    G --> L[Billing line generated for dispensed qty]
    K --> L
    J --> M[Triggers low/out-of-stock alert to Inventory Manager]
    L --> N{All lines on prescription dispensed or cancelled?}
    N -->|No| O[Prescription.state = partially_dispensed]
    N -->|Yes| P[Prescription.state = dispensed]
    O --> A
    P --> Q[Reported back to Visit aggregate state - Section 3]
```

---

## 6. Lab / Radiology Order-to-Result Detail

```mermaid
flowchart TD
    A[Order created by Doctor] --> B[Lab/Radiology Queue, state=ordered]
    B --> C[Technician accepts: state=sample_collected or scheduled]
    C --> D[Processing]
    D --> E{Result type}
    E -->|Structured numeric| F[Enter values against test parameters]
    E -->|Report/Image| G[Attach PDF/Image + findings text]
    F --> H{Value outside normal range?}
    H -->|Yes| I[Auto-flag result abnormal, highlight on patient record]
    H -->|No| J[Result normal]
    G --> K[state=completed]
    I --> K
    J --> K
    K --> L[Ordering doctor notified - activity/todo created]
    K --> M[Visible immediately on patient timeline]
    M --> N[Counted toward Visit/Admission completion check - Section 3/4]
```

**Exception:** an order can be **cancelled** by the ordering doctor at any point before `sample_collected`/`scheduled`; once collection/scheduling has happened, cancellation requires a reason and is audit-logged (sample already consumed).

---

## 7. Cross-Cutting Exceptions (apply across all workflows)

| Exception | Handling |
|---|---|
| Patient leaves mid-workflow (LWBS — left without being seen) | Any pre-billing state can transition to `cancelled` with mandatory reason; no invoice generated unless billable services were already rendered (e.g., a lab test already run is still billed even if the patient leaves before doctor follow-up). |
| Wrong patient selected at registration | Visit can be voided (`state=void`) before any clinical data is attached; if clinical data exists, must be corrected via an audited "reassign visit to correct patient" admin action, never a silent delete. |
| Duplicate patient merge | Admin-only wizard merges two `hospital.patient` records (Phase 6), re-pointing all visit/vitals/prescription/lab/admission FKs to the surviving record, fully audit-logged. |
| System/network interruption mid-entry | Odoo's transactional ORM ensures partial writes never commit; no "half-created" visit/prescription states are reachable. |
| Emergency walk-in bypassing queue order | Reception/triage can set `priority=emergency`, which always sorts first in every queue regardless of check-in time. |
| Doctor amends a closed consultation | Allowed same-day only, fully audit-logged, reopens the visit aggregate state as described in Section 3. |
| Death in care | Discharge sub-type `deceased`; skips follow-up instructions section on the printed summary, still finalizes billing and frees the bed. |

---

## Status

Workflow contract complete. Proceeding to Phase 4 — System Architecture.
