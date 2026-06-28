# Phase 4 — System Architecture

**Principle:** zero Odoo core modification. Every capability below is delivered as installable addons under a shared `hospital_*` namespace, depending on Odoo 19 core/Enterprise modules (`base`, `mail`, `stock`, `account`, `web`, `portal`, etc.) the normal way — via `depends` in `__manifest__.py` — never by editing core files.

---

## 1. Layered Architecture Overview

```mermaid
flowchart TB
    subgraph Presentation["Presentation Layer"]
        UI1[OWL Components - custom widgets]
        UI2[Odoo Views - Form/List/Kanban, custom templates]
        UI3[QWeb Reports - PDF]
        UI4[Dashboards - OWL + SQL views]
    end

    subgraph BizLogic["Business Logic Layer"]
        BL1[Model methods - state transitions]
        BL2[Workflow automation - compute/onchange/triggers]
        BL3[Wizards - transient models]
        BL4[Validation - constrains/SQL constraints]
    end

    subgraph ORM["ORM Layer"]
        O1[Odoo ORM - models.Model]
        O2[Mixins - mail.thread, audit mixin]
        O3[Sequences - ir.sequence]
    end

    subgraph DB["Database Layer"]
        D1[(PostgreSQL 16+)]
        D2[Indexes - btree, GIN trigram]
        D3[Constraints - CHECK, UNIQUE, FK]
        D4[SQL Views - dashboard aggregates]
    end

    subgraph Security["Security Layer"]
        S1[Security Groups - res.groups]
        S2[Record Rules - ir.rule]
        S3[Field-level ACL]
        S4[Audit Log - custom model]
    end

    subgraph Cross["Cross-Cutting Services"]
        C1[Notifications - mail.activity / bus]
        C2[Attachments - ir.attachment]
        C3[Printing - QWeb / wkhtmltopdf]
        C4[Sequences/Numbering]
    end

    subgraph Future["Future Extension Points (not v1)"]
        F1[hospital_api - REST/JSON-RPC]
        F2[hospital_portal - patient self-service]
        F3[hospital_mobile - native app]
        F4[Telemedicine integration]
    end

    UI1 --> BL1
    UI2 --> BL1
    UI4 --> D4
    BL1 --> O1
    BL2 --> O1
    BL3 --> O1
    O1 --> D1
    O2 --> O1
    Security --> O1
    Security --> UI2
    Cross --> BL1
    O1 -.exposed via.-> Future
```

---

## 2. Module Dependency Graph

```mermaid
flowchart LR
    base[hospital_base] --> reception[hospital_reception]
    base --> nurse[hospital_nurse]
    base --> doctor[hospital_doctor]
    base --> pharmacy[hospital_pharmacy]
    base --> inventory[hospital_inventory]
    base --> lab[hospital_lab]
    base --> radiology[hospital_radiology]
    base --> ipd[hospital_ipd]
    base --> security[hospital_security]

    reception --> nurse
    nurse --> doctor
    doctor --> pharmacy
    doctor --> lab
    doctor --> radiology
    doctor --> ipd
    pharmacy --> inventory
    ipd --> nurse

    base --> dashboard[hospital_dashboard]
    reception --> dashboard
    doctor --> dashboard
    pharmacy --> dashboard
    lab --> dashboard
    radiology --> dashboard
    ipd --> dashboard

    base --> reports[hospital_reports]
    doctor --> reports
    pharmacy --> reports
    lab --> reports
    radiology --> reports
    ipd --> reports

    dashboard -.future.-> api[hospital_api]
    reports -.future.-> portal[hospital_portal]
    api -.future.-> mobile[hospital_mobile]

    style api stroke-dasharray: 5 5
    style portal stroke-dasharray: 5 5
    style mobile stroke-dasharray: 5 5
```

**Odoo core/Enterprise dependencies used (not modified):** `base`, `mail`, `web`, `stock`, `account`, `hr` (optional, for doctor=employee linkage), `portal` (future), `web_tour` (onboarding), `auth_signup` (future portal).

---

## 3. Runtime Request Flow (example: Nurse submits vitals → Doctor queue updates)

```mermaid
sequenceDiagram
    participant Tablet as Nurse Tablet (OWL UI)
    participant Ctrl as Controller/Action
    participant ORM as hospital.vitals (ORM)
    participant Visit as hospital.visit
    participant Bus as Odoo Bus (longpolling)
    participant DocUI as Doctor Dashboard (OWL)

    Tablet->>Ctrl: Save Vitals (form submit)
    Ctrl->>ORM: create(vitals_vals)
    ORM->>ORM: @api.constrains validate ranges
    ORM->>Visit: write({state: 'waiting_doctor'})
    Visit->>Visit: _check_priority_escalation()
    Visit-->>Bus: notify(channel='hospital_queue_doctor_X')
    Bus-->>DocUI: push queue update
    DocUI->>DocUI: re-render queue (no manual refresh)
    Ctrl-->>Tablet: success toast
```

This illustrates the core architectural commitment from Phase 3: **automated transitions happen inside model methods in the same transaction**, and **live UI updates use Odoo's bus/longpolling**, not manual refresh-button workflows.

---

## 4. Reporting & Notification Architecture

```mermaid
flowchart TB
    subgraph Sources
        P1[hospital.visit]
        P2[hospital.consultation]
        P3[hospital.prescription]
        P4[hospital.lab.order]
        P5[hospital.ipd.admission]
    end

    subgraph Reporting
        R1[SQL Views - dashboard_*]
        R2[QWeb PDF Templates]
        R3[OWL Dashboard Widgets]
    end

    subgraph Notifications
        N1[mail.activity - todo for ordering doctor]
        N2[Odoo Bus - live queue push]
        N3[Email/SMS future via mail templates]
    end

    Sources --> R1 --> R3
    Sources --> R2
    Sources --> N1
    Sources --> N2
```

---

## 5. Attachment & Printing Architecture

- All clinical attachments (lab PDFs, radiology images, discharge summaries) stored via Odoo's native `ir.attachment`, linked via `res_model`/`res_id` to the owning record (e.g., `hospital.lab.result`) — never a custom file-storage table.
- Printing uses standard QWeb report actions (`ir.actions.report`), rendered server-side to PDF via Odoo's existing wkhtmltopdf pipeline. Custom report templates live in each module's `report/` folder.
- Large attachments (radiology images) rely on Odoo's attachment storage backend configuration (filesystem or S3-compatible, as already supported by Odoo) — no custom storage layer built.

---

## 6. Security Architecture (overview — full detail in Phase 9)

```mermaid
flowchart TB
    U[User] --> G[res.groups: Reception/Nurse/Doctor/Pharmacist/LabTech/RadTech/WardManager/Admin]
    G --> ACL[ir.model.access.csv - model-level CRUD]
    G --> RR[ir.rule - record-level: company, own-records, role-scoped fields]
    ACL --> M[Models]
    RR --> M
    M --> AUDIT[hospital.audit.log - mixin on sensitive models]
    AUDIT --> DB[(audit table, append-only)]
```

---

## 7. Future Extension Points (designed for now, built later)

| Future capability | How today's architecture enables it without rework |
|---|---|
| **Mobile App** (`hospital_mobile`) | Business logic lives in model methods, not view-bound JS — any future API layer calls the same methods the web UI calls. |
| **Patient Portal** (`hospital_portal`) | Security model (Phase 9) already separates "own visible records" via record rules keyed on `partner_id`, the same mechanism Odoo's native portal uses. |
| **Telemedicine** | `hospital.consultation` model is channel-agnostic (doesn't assume in-person) — a future `consultation_type = 'video'` field and a video-provider integration module can extend it without schema change. |
| **REST/JSON-RPC API** (`hospital_api`) | Odoo's existing external API (XML-RPC/JSON-RPC) already exposes any model with proper ACLs; a dedicated `hospital_api` module would add curated, versioned endpoints/serializers on top, not invent a new transport. |

---

## Status

Architecture defined. Proceeding to Phase 5 — Database Design.
