# Hospital Laboratory (`hospital_lab`)

Module 7 of 12 in the Hospital Management System suite.

## Purpose

Full laboratory order and result management, covering the complete workflow from
doctor ordering through sample collection, analysis, and structured result delivery.

## Dependencies

- `hospital_doctor` (which transitively depends on `hospital_nurse`, `hospital_reception`, `hospital_base`)

## Key Models

| Model | Purpose |
|---|---|
| `hospital.lab.test` | Lab test catalog with normal reference ranges and sample type |
| `hospital.lab.order` | Lab order (state machine: ordered → sample_collected → processing → completed/cancelled) |
| `hospital.lab.result` | Structured result rows: parameter, value, unit, normal range, is_abnormal flag |
| `hospital.visit` (_inherit_) | Adds `lab_order_ids`; extends `_compute_pending_branches()` to check real order completion |

## Order State Machine

```
ordered → sample_collected → processing → completed
                ↓                ↓
            cancelled        cancelled (with reason)
```

## Installation

Install via Odoo app manager or:

```bash
./odoo-bin -d mydb -i hospital_lab
```

## Default Catalog

Installs 6 standard lab tests in all environments (not demo-only):
- CBC (Complete Blood Count) — normal range: Hb 12.0–17.5 g/dL
- Blood Glucose Fasting — 3.9–5.5 mmol/L
- Lipid Panel — Total Cholesterol < 5.2 mmol/L
- Urine Routine Examination
- Liver Function Tests (LFT) — ALT 7–56 U/L
- Kidney Function Tests (KFT) — Serum Creatinine 62–115 µmol/L

## Visit Branch Integration

This module extends `hospital.visit._compute_pending_branches()` to replace the
intent-only "lab" placeholder (set by `hospital_doctor` when `outcome_lab_requested=True`)
with a real check against `hospital.lab.order` records. A visit's "lab" branch is
pending if any order for that visit is NOT in `completed` or `cancelled` state.
The visit only advances to `billing` once all branches (prescription, lab, radiology, etc.)
are resolved.

## Security Groups

- `hospital_lab.group_hospital_lab_tech` — lab technicians (can receive orders, collect samples, enter results)
- `hospital_base.group_hospital_admin` — full access

## Reports

- Lab Report (QWeb PDF): patient, test name, results table with normal range + abnormal flag, signed by tech and doctor.

## Tests

Run with:
```bash
./odoo-bin -d mydb --test-enable -i hospital_lab
```
