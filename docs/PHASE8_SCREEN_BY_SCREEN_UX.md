# Phase 8 — Screen-by-Screen UX

Every screen below follows the same template: Purpose, Wireframe, Layout, Components, Actions, Keyboard shortcuts, Empty/Loading/Error states, Permissions.

---

## 1. Reception Dashboard

**Purpose:** Reception's home screen — see today's queue at a glance, jump into registration or check-in.

```
┌─────────────────────────────────────────────────────────────┐
│ [Hospital Logo]   Reception Dashboard          [🔍 Search] [+New]│
├─────────────────────────────────────────────────────────────┤
│  KPI: Waiting 12 │ In Consult 4 │ Completed Today 38         │
├───────────────────────────────┬───────────────────────────────┤
│ Live Queue (kanban by doctor) │  Today's Appointments (list)  │
│ ┌─────┐ ┌─────┐ ┌─────┐       │  09:00 J. Smith → Dr. Castillo│
│ │Dr. A│ │Dr. B│ │Dr. C│       │  09:30 M. Lee   → Dr. Patel   │
│ │ 3 ⏳│ │ 1 ⏳│ │ 5 ⏳│       │  ...                          │
│ └─────┘ └─────┘ └─────┘       │                               │
└───────────────────────────────┴───────────────────────────────┘
```

- **Layout:** Top KPI strip + two-column split (queue kanban left, appointment list right).
- **Components:** KPI cards, doctor-queue kanban columns, appointment list, global search bar, primary "+New Registration" button.
- **Actions:** New registration, search patient, click a queue card to open visit detail, check in an appointment.
- **Shortcuts:** `N` new registration, `/` focus search.
- **Empty state:** "No patients waiting — queue is clear" illustration, still shows appointment list.
- **Loading state:** Skeleton KPI cards + skeleton kanban columns (no spinner-only blank screen).
- **Error state:** Inline banner "Couldn't load queue — retry" with retry button; cached last-known KPI numbers shown grayed out rather than blank.
- **Permissions:** `group_hospital_reception`, `group_hospital_admin`.

---

## 2. Patient Registration

**Purpose:** Register a new patient or start a visit for an existing one, fast.

```
┌───────────────────────────────────────┐
│ Register Patient                  [X] │
├───────────────────────────────────────┤
│ Search existing: [____________] 🔍     │
│ ⚠ Possible match found: John Smith... │
├───────────────────────────────────────┤
│ Name*        [____________]           │
│ DOB*         [__/__/____]   Gender [▾]│
│ Phone*       [____________]           │
│ ID Type [▾]  ID Number [________]     │
│ Emergency Contact [____________]      │
├───────────────────────────────────────┤
│ Assign Doctor [▾]   Department [▾]    │
│ Payer: ⦿ Cash  ○ Insurance            │
├───────────────────────────────────────┤
│              [Cancel]  [Register & Queue] │
└───────────────────────────────────────┘
```

- **Layout:** Single-column modal/drawer form, search-first.
- **Components:** Live duplicate-match warning banner (non-blocking), required-field markers, doctor/department selectors, payer radio.
- **Actions:** Search-as-you-type, confirm despite duplicate warning, register & immediately enqueue.
- **Shortcuts:** `Tab` order follows visual flow top-to-bottom; `Ctrl+Enter` submits.
- **Empty state:** N/A (form always has content).
- **Loading state:** Submit button shows inline spinner, fields disabled during save (prevents double-submit).
- **Error state:** Field-level inline errors (AC-5); top-level banner for server errors (e.g., sequence generation failure).
- **Permissions:** `group_hospital_reception`, `group_hospital_admin`.

---

## 3. Search Patient

**Purpose:** Find an existing patient from anywhere in the system in under a second.

- **Layout:** Command-palette style overlay (`Ctrl+K`), or dedicated search page with filters (name/phone/ID/code).
- **Components:** Search input with debounce, result list showing name + age/gender + last visit date + patient code, "Register new" fallback action if no match.
- **Actions:** Click result → Patient Profile; keyboard arrow+Enter to select.
- **Shortcuts:** `Ctrl+K` open globally, `Esc` close, `↑↓` navigate, `Enter` select.
- **Empty state:** "No patients found for '...' — Register new patient?" with direct CTA.
- **Loading state:** Inline skeleton rows under the search box (not a full-page spinner).
- **Error state:** "Search temporarily unavailable" inline message, doesn't block manual navigation elsewhere.
- **Permissions:** Any hospital staff group (search is broadly needed; field-level visibility restricts what's shown — Phase 9).

---

## 4. Patient Profile

**Purpose:** The single, complete view of a patient — identity, history timeline, allergies, all departments' data in one place.

```
┌─────────────────────────────────────────────────────────┐
│ John Smith (PT/00042)  Age 45 • Male • O+  [Edit]        │
│ ⚠ Allergy: Penicillin                                    │
├─────────────────────────────────────────────────────────┤
│ Timeline                                                  │
│ ● 2026-06-28 Visit VS/01122 — Dr. Castillo — Completed    │
│   ├ Vitals: BP 120/80, Temp 36.8°C                        │
│   ├ Consultation: Diagnosis — Acute pharyngitis           │
│   ├ Prescription: Amoxicillin 500mg — Dispensed           │
│   └ Invoice: $42.00 — Paid                                │
│ ● 2026-03-12 Visit VS/00981 — Dr. Patel — Completed       │
│   └ ...                                                   │
└─────────────────────────────────────────────────────────┘
```

- **Layout:** Header identity bar (sticky) + vertical expandable timeline below.
- **Components:** Allergy/condition banner (always visible, never collapsed), timeline entries grouped by visit, expandable sub-entries, quick-action "New Visit" button.
- **Actions:** Expand/collapse timeline entries, jump to any sub-record's full form, start a new visit directly from profile.
- **Shortcuts:** `E` edit profile, `V` new visit.
- **Empty state:** New patient with no visits yet — shows "No visit history yet" + prominent "Start First Visit" CTA.
- **Loading state:** Skeleton timeline entries.
- **Error state:** If a sub-record fails to load, that single timeline entry shows "Couldn't load details" without breaking the rest of the timeline.
- **Permissions:** All clinical roles can view (field-level restrictions apply per Phase 9, e.g., pharmacist doesn't see full diagnosis notes by default).

---

## 5. Waiting Queue (Doctor/Department view)

**Purpose:** Ordered, live-updating queue for a specific doctor or department.

- **Layout:** Single-column priority-sorted list (emergency → urgent → normal, then check-in time).
- **Components:** Queue row = patient name, wait time, priority chip, latest vitals snippet, "Call" button.
- **Actions:** Call next patient (opens consultation), reassign to another doctor, mark no-show.
- **Shortcuts:** `↑↓` navigate, `Enter` call selected.
- **Empty state:** "Queue is clear" calm illustration.
- **Loading state:** Skeleton rows.
- **Error state:** Stale-data banner if live bus connection drops ("Reconnecting...") rather than silently going stale.
- **Permissions:** Doctor sees own queue; reception/admin see all.

---

## 6. Nurse Dashboard

**Purpose:** Tablet-first home for nurse station — who's next for vitals, ward tasks if IPD installed.

- **Layout:** Tablet mode: single column, large cards, bottom action bar.
- **Components:** "Next Patient" big card (name, age, priority), quick vitals-entry shortcut, ward task list (if `hospital_ipd` installed) below.
- **Actions:** Tap to open vitals quick-entry, mark task complete with single tap.
- **Shortcuts:** N/A (touch-first; physical keyboard shortcuts not primary here).
- **Empty state:** "No patients waiting for vitals."
- **Loading state:** Skeleton "next patient" card.
- **Error state:** Inline retry banner; never blocks already-loaded ward task list.
- **Permissions:** `group_hospital_nurse`.

---

## 7. Vitals Quick-Entry

**Purpose:** Fast structured vitals capture, optimized for tablet.

```
┌───────────────────────────────────┐
│ Vitals — John Smith               │
├───────────────────────────────────┤
│ BP   [120] / [80]   mmHg          │
│ Pulse [72]          bpm           │
│ Temp  [36.8]        °C            │
│ SpO2  [98]          %             │
│ Height [170] cm   Weight [70] kg  │
│ BMI: 24.2 (Normal)                │
├───────────────────────────────────┤
│        [Cancel]   [Save & Send to Doctor] │
└───────────────────────────────────┘
```

- **Components:** Numeric steppers (tablet-friendly, not tiny text inputs alone), auto-computed BMI with color flag, abnormal-value inline highlight as typed.
- **Actions:** Save & auto-transition visit to doctor queue (Phase 3 §2) — single button, no separate "send" step.
- **Empty/Loading/Error:** Standard form patterns; error shows which field failed range validation inline.
- **Permissions:** `group_hospital_nurse`.

---

## 8. Doctor Dashboard

**Purpose:** Doctor's home — queue + today's completed patients.

- **Layout:** 3-pane (per Phase 7 §5): queue (left, narrow), main content (center), collapsible patient context (right) — collapses to tabs on tablet.
- **Components:** Queue list with priority/wait-time, KPI strip (seen today, avg consult time), "Call Next" primary button.
- **Actions:** Call next, jump directly to any queued patient out of order (with confirmation if skipping priority).
- **Shortcuts:** `Space` call next.
- **Empty state:** "Your queue is empty" with today's summary stats still visible.
- **Loading/Error:** Standard skeleton/retry patterns as above.
- **Permissions:** `group_hospital_doctor`.

---

## 9. Prescription Builder

**Purpose:** Fast, safe prescription creation inside the consultation screen.

```
┌─────────────────────────────────────────────┐
│ Prescription                                  │
├─────────────────────────────────────────────┤
│ [Search medicine...]  🔍   Stock: ✓ In stock │
│ ┌───────────────────────────────────────────┐│
│ │ Amoxicillin 500mg │ TID │ 7 days │ Oral │✕││
│ │ Paracetamol 500mg │ QID │ 5 days │ Oral │✕││
│ └───────────────────────────────────────────┘│
│ [+ Add Medicine]                              │
│ ⚠ Patient allergy: Penicillin conflicts with  │
│   Amoxicillin — Override required             │
├─────────────────────────────────────────────┤
│                    [Save Prescription]        │
└─────────────────────────────────────────────┘
```

- **Components:** Medicine autocomplete with live stock badge, editable line grid (dosage/frequency/duration/route), inline allergy-conflict warning (Phase 3 §5) blocking save until acknowledged.
- **Actions:** Add/remove line, override conflict with reason, save (creates `hospital.prescription`, routes to pharmacy queue automatically).
- **Shortcuts:** `Ctrl+P` open builder from consultation, `Enter` adds focused medicine search result as a new line.
- **Empty state:** "No medicines added yet."
- **Error state:** Save blocked with clear explanation if a line is incomplete (e.g., missing dosage).
- **Permissions:** `group_hospital_doctor`.

---

## 10. Lab Dashboard

**Purpose:** Lab tech's queue, grouped by priority/test type.

- **Layout:** Grouped list (by priority then test type), detail panel on selection.
- **Components:** Order row (patient, test, priority, ordered time), sample-collection action, result entry grid matching printed report layout (Phase 7 §5).
- **Actions:** Mark sample collected, enter structured results, attach report file, complete order (notifies doctor automatically).
- **Shortcuts:** `C` mark collected on focused row, `Ctrl+S` save results.
- **Empty state:** "No pending lab orders."
- **Loading/Error:** Standard patterns.
- **Permissions:** `group_hospital_lab_tech`.

---

## 11. Radiology Dashboard

**Purpose:** Mirrors Lab Dashboard structurally for imaging orders.

- **Components:** Order queue, scheduling action, findings text + image/PDF attachment uploader.
- **Actions/Shortcuts/States:** Same pattern as Lab Dashboard (§10), substituting "scheduled" for "sample collected."
- **Permissions:** `group_hospital_radiology_tech`.

---

## 12. Pharmacy Dashboard

**Purpose:** Pending prescriptions queue + backorder visibility.

- **Layout:** Split view — queue list (left), dispense detail (right).
- **Components:** Queue row (patient, prescribing doctor, line count, oldest-pending-time), dispense detail panel with per-line stock badges and dispense/partial/backorder actions.
- **Actions:** Dispense line, dispense all, override allergy/stock warning with reason, view backorder report.
- **Shortcuts:** `D` dispense focused line, `A` dispense all eligible lines.
- **Empty state:** "No pending prescriptions."
- **Error state:** Out-of-stock lines clearly marked, link to Inventory Dashboard.
- **Permissions:** `group_hospital_pharmacist`.

---

## 13. Inventory Dashboard

**Purpose:** Stock levels, expiry, reorder visibility for medicines/consumables.

- **Components:** Stock level table (current qty, reorder threshold, status chip), expiry alert list (sorted soonest-first), low-stock alert list.
- **Actions:** Trigger purchase (links to Odoo's native Purchase app — not reinvented), adjust stock (native Inventory adjustment flow).
- **Empty state:** "All stock levels healthy."
- **Permissions:** `group_hospital_inventory_manager`.

---

## 14. Ward Dashboard / Bed Occupancy

**Purpose:** Real-time visual grid of every bed's status.

```
┌──────────────────────────────────────────────┐
│ Ward: General A          Occupancy: 18/20     │
├──────────────────────────────────────────────┤
│ [B01🟢][B02🔴][B03🔴][B04🟡][B05🔴] ...        │
│  Vacant Occupied Occupied Cleaning Occupied   │
└──────────────────────────────────────────────┘
```

- **Layout:** Grid of bed tiles, color-coded (vacant/occupied/reserved/cleaning), grouped by ward (tabs or accordion).
- **Components:** Bed tile (number + status + patient name if occupied), ward-level occupancy % KPI.
- **Actions:** Click vacant bed → admit waiting patient; click occupied bed → view admission/transfer/discharge actions.
- **Shortcuts:** Number-key ward switching (1–9 for first 9 wards).
- **Empty state:** N/A (always shows configured beds, even if all vacant — that's a valid/expected state, not "empty").
- **Loading/Error:** Skeleton grid; stale-data reconnect banner same as queue views.
- **Permissions:** `group_hospital_ward_manager`, `group_hospital_admin`.

---

## 15. Admission

**Purpose:** Convert a doctor's admission order into a bed assignment.

- **Components:** Waiting-for-bed list, ward/bed selector filtered to vacant beds only, admission confirm action.
- **Actions:** Assign bed (enforces one-active-admission-per-bed constraint from Phase 5), confirm admission.
- **Empty state:** "No pending admission requests."
- **Permissions:** `group_hospital_ward_manager`.

---

## 16. Discharge

**Purpose:** Doctor/ward completes discharge summary and closes the stay.

- **Components:** Discharge summary form (diagnosis, treatment, discharge meds, follow-up instructions), discharge-type selector (normal/AMA/deceased/referred), **blocking-items panel** listing any unresolved orders preventing confirmation (Phase 3 §4).
- **Actions:** Confirm discharge (blocked until blocking-items panel is empty), print discharge summary.
- **Error state:** Confirm button disabled with explicit list of what's blocking — never a vague "cannot discharge" message.
- **Permissions:** `group_hospital_doctor`, `group_hospital_ward_manager`.

---

## 17. Reports (cross-module report center)

**Purpose:** Central place to find/print/export prescription, lab, radiology, discharge, and invoice reports without hunting through each module.

- **Components:** Filterable report list (by type/date/patient), preview pane, export/print actions.
- **Permissions:** Role-scoped — each role sees only the report types relevant to them; admin sees all.

---

## 18. Admin Panel

**Purpose:** Configuration hub — departments, doctors, wards/beds, medicine catalog, lab/radiology catalogs, users/roles, audit logs, report branding.

- **Layout:** Standard Odoo Settings-style sectioned list (acceptable here per Phase 7 principle — low-frequency admin screens don't need bespoke UI investment).
- **Components:** Section cards linking to each config area; audit log viewer (read-only, filterable).
- **Permissions:** `group_hospital_admin` only.

---

## Status

Screen-by-screen UX complete. Proceeding to Phase 9 — Security Design.
