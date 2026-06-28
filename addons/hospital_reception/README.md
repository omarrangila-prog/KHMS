# Hospital Reception

## Purpose

`hospital_reception` is the front-desk addon of the Hospital Management
System suite for Odoo 19. It builds directly on `hospital_base` to give
reception staff a fast registration flow, appointment booking and
check-in, a live reception dashboard, and a printable queue ticket.

This module is **module 2 of 12** in the build order defined by the
project's Phase 12 implementation plan.

## Dependencies

- `hospital_base`

## Key Models

| Model | Purpose |
|---|---|
| `hospital.appointment` | Pre-booked OPD appointment. Pre-fills doctor/department for a future visit; converges into the same `waiting_nurse` queue as a walk-in once checked in. |
| `hospital.patient.registration.wizard` | Combined search-existing-or-register-new flow; creates/reuses the patient, creates a visit, and confirms it in one action. |
| `hospital.visit.cancel.wizard` | Mandatory-reason visit cancellation, writes `cancel_reason` then calls `hospital.visit.action_cancel()`. |
| `hospital.visit` (extended) | Adds a non-stored `queue_position` computed field for the reception dashboard/queue ticket. |

## Workflow Notes (Phase 3 §2)

- **Walk-in registration:** Reception -> Dashboard -> "New Registration" opens `hospital.patient.registration.wizard`. Confirming creates/reuses the patient, creates a `hospital.visit` in `draft`, and immediately calls `action_confirm()` to move it to `waiting_nurse`.
- **Appointment check-in:** `hospital.appointment.action_check_in()` creates a `hospital.visit` and calls its `action_confirm()`, so both paths land on the exact same `waiting_nurse` state -- per the Phase 3 §2 contract that walk-ins and pre-booked appointments converge.
- **Cancellation:** Always requires a reason. The visit form's "Cancel" button opens `hospital.visit.cancel.wizard` rather than calling `hospital.visit.action_cancel()` directly, so reception staff are always prompted for the reason that `hospital_base`'s model-level constraint already enforces.

## Security

- **Hospital Reception** (`group_hospital_reception`): implied by `hospital_base.group_hospital_user`; full CRUD on `hospital.appointment` and the reception wizards, plus create/write (no delete) on `hospital.patient` and `hospital.visit` so front-desk staff can register patients and open visits.
- Multi-company record rule on `hospital.appointment`, consistent with `hospital_base`'s `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]` pattern.

## Views & Menus

`Hospital -> Reception` (visible to `group_hospital_reception` and `group_hospital_admin`):

- **Dashboard** -- OWL client action: KPI strip (waiting / in-consult / completed today via `read_group`), live queue grouped by doctor, today's appointments with inline check-in.
- **Patients** -- reuses `hospital_base.hospital_patient_action`.
- **Appointments** -- list, calendar, and form views.
- **Queue** -- `hospital.visit` kanban/list scoped to the active pre-billing states, grouped by doctor.

## Reports

- **Queue Ticket** (`hospital.queue.ticket.report`) -- small, thermal-printer-friendly QWeb report printable from a visit's form (bound action), showing visit code, patient, doctor, priority, and queue position.

## Install / Configuration

1. Install `hospital_base` first.
2. Install `hospital_reception` from the Apps menu.
3. Assign the **Hospital Reception** group to front-desk users.
4. Go to **Hospital -> Reception -> Dashboard** to start registering patients and managing the queue.

Demo data (15 appointments, 10 visits parked in `waiting_nurse`) is loaded
automatically when demo data is enabled, reusing `hospital_base`'s demo
patients, doctors and departments.
