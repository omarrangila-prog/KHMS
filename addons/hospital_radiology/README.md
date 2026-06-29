# Hospital Radiology (`hospital_radiology`)

Module 8 of 12 in the Hospital Management System suite.

## Purpose

Full radiology order and result management for imaging studies. Structurally mirrors
`hospital_lab` with adaptations for imaging modalities (X-Ray, CT, MRI, Ultrasound,
Mammography).

## Dependencies

- `hospital_doctor` (which transitively depends on `hospital_nurse`, `hospital_reception`, `hospital_base`)

## Key Models

| Model | Purpose |
|---|---|
| `hospital.radiology.study` | Study catalog with modality classification |
| `hospital.radiology.order` | Radiology order (state: ordered → scheduled → in_progress → completed/cancelled) |
| `hospital.radiology.result` | Findings + impression text + image/PDF attachments |
| `hospital.visit` (_inherit_) | Adds `radiology_order_ids`; extends `_compute_pending_branches()` for real radiology completion |

## Order State Machine

```
ordered → scheduled → in_progress → completed
    ↓          ↓
cancelled  cancelled (with reason)
```

## Installation

```bash
./odoo-bin -d mydb -i hospital_radiology
```

## Default Catalog

Installs 5 standard imaging studies in all environments:
- Chest X-Ray (PA View) — modality: xray
- CT Head (Non-Contrast) — modality: ct
- MRI Spine (Lumbar) — modality: mri
- Ultrasound Abdomen — modality: ultrasound
- Mammography (Bilateral) — modality: mammography

## Visit Branch Integration

Extends `hospital.visit._compute_pending_branches()` using the identical pattern to
`hospital_lab`, replacing the intent-only "radiology" placeholder set by `hospital_doctor`.
A visit's "radiology" branch is pending if any `hospital.radiology.order` for that visit
is not in `completed` or `cancelled` state.

## Security Groups

- `hospital_radiology.group_hospital_radiology_tech` — radiology technicians/radiologists
- `hospital_base.group_hospital_admin` — full access

## Reports

- Radiology Report (QWeb PDF): patient, study name, findings, impression, attachments list, signed by radiologist and ordering doctor.

## Tests

```bash
./odoo-bin -d mydb --test-enable -i hospital_radiology
```
