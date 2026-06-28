# Phase 1 — Executive Product Vision

**Product codename:** MediCore HMS (working name — open to change)
**Platform:** Odoo 19, 100% custom addons, zero core modification
**Document status:** Draft for approval

---

## 1. Product Vision

MediCore HMS is a commercial-grade Hospital Management System built natively on Odoo 19, designed to feel like a premium vertical SaaS product (in the spirit of Linear, Notion, or a modern EMR) rather than a generic ERP form-painted with a hospital label.

The product unifies the entire patient journey — Reception → Nurse → Doctor → Pharmacy → Lab/Radiology → IPD Admission → Discharge → History — around a **single patient record**. Every department reads from and writes to that one record. There is no duplicated entry, no department-siloed data, and no manual re-keying of information that already exists in the system.

The long-term vision is a multi-tenant-ready, modular hospital platform that a small 20-bed clinic can install with three modules, and a 500-bed multi-specialty hospital can scale into a full suite — including future mobile apps, a patient portal, and telemedicine — without ever touching Odoo core.

**Vision statement:**
> Give every hospital, regardless of size, an Odoo-native HMS that is as fast and pleasant to use as the best consumer software, while meeting the data integrity, auditability, and workflow rigor that clinical operations demand.

---

## 2. Business Goals

| Goal | Description |
|---|---|
| **Commercial viability** | Package as licensable Odoo Apps (Odoo Apps Store + direct enterprise sales) with tiered editions (Clinic / Hospital / Enterprise). |
| **Fast time-to-value** | A new clinic should be able to install `hospital_base` + `hospital_reception` + `hospital_doctor` and run real patient flow within a day. |
| **Low implementation cost** | Minimize the need for expensive consultants by shipping sane defaults, demo data, and guided setup wizards. |
| **Recurring revenue** | Support a subscription-style model (per-bed or per-active-user pricing) layered on top of Odoo's standard licensing, plus paid support/maintenance contracts. |
| **Defensibility** | Build a UX and workflow-automation moat that generic HMS-on-Odoo competitors (most of which are thin CRUD wrappers) cannot easily replicate. |
| **Compliance-readiness** | Be credibly positionable in markets with GDPR and HIPAA-inspired expectations without claiming formal certification we haven't earned. |

---

## 3. Target Hospitals

**Primary segments:**

1. **Small & mid-size private hospitals (50–300 beds)** — currently running on paper, spreadsheets, or legacy desktop HMS software with no real ERP integration (no inventory-to-billing-to-clinical linkage).
2. **Multi-specialty clinics and polyclinics** — high patient throughput, need fast OPD (outpatient) flow, minimal IPD (inpatient) complexity.
3. **Diagnostic-centric facilities** (lab/radiology heavy) — need tight integration between orders, results, and billing.
4. **Hospital groups / chains** — multiple branches, need centralized reporting and standardized workflows, while each branch operates semi-autonomously.

**Secondary segments (future roadmap):**
- NGOs and rural health clinics needing a low-cost, offline-tolerant deployment.
- Specialty hospitals (maternity, ortho, dialysis) needing vertical-specific modules built on the same base.

**Explicitly out of scope for v1:** large academic/government hospital networks requiring deep national health-system interoperability (e.g., country-specific HL7/FHIR national registries) — flagged as future roadmap, not v1.

---

## 4. Target Users

| Role | Primary need |
|---|---|
| **Reception / Front Desk staff** | Fast patient registration, search, queue management, appointment booking, billing kickoff. |
| **Nurses** | Vitals capture, ward rounds, task lists, tablet-friendly bedside entry. |
| **Doctors (OPD & IPD)** | Consultation workspace, history-at-a-glance, prescription builder, lab/radiology ordering, discharge summaries. |
| **Pharmacists** | Prescription fulfillment, stock-aware dispensing, drug interaction/safety checks. |
| **Lab Technicians** | Order queue, sample tracking, result entry, report generation. |
| **Radiology Technicians** | Imaging order queue, result/report attachment. |
| **Ward/Bed Managers** | Real-time bed occupancy, admission/transfer/discharge workflow. |
| **Pharmacy/Inventory Managers** | Stock levels, expiry tracking, purchase triggers. |
| **Hospital Administrators / Owners** | Cross-department dashboards, financial and operational KPIs. |
| **IT/System Administrators** | User and security management, audit logs, configuration. |
| **(Future) Patients** | Self-service portal: appointments, reports, bills, history. |

---

## 5. Benefits

**For hospitals:**
- Single source of truth per patient — eliminates re-entry errors and lost paperwork.
- Faster patient throughput via automated workflow handoffs (reception → nurse → doctor → pharmacy happens without staff manually routing paper or re-typing).
- Real-time visibility into bed occupancy, queues, and inventory — better operational decisions.
- Built-in billing/invoicing tied directly to clinical actions (consultations, lab orders, dispensed medicine) — fewer billing leaks.
- Lower total cost of ownership than legacy licensed HMS software, by riding on Odoo's existing ecosystem (accounting, inventory, HR already exist and integrate natively).

**For hospital staff:**
- Premium, fast, modern UI that reduces clicks and cognitive load compared to generic ERP screens.
- Tablet-first nurse/doctor workflows for bedside and ward use.
- Keyboard-first power-user flows for high-volume reception/pharmacy staff.

**For the business building this product:**
- Modular architecture allows selling individual modules or full suites.
- Built on Odoo means accounting, HR, purchasing, and multi-company are "free" — we only build the clinical/hospital-specific layer.

---

## 6. Competitive Advantages

| Advantage | Why it matters |
|---|---|
| **True single-patient-record architecture** | Most Odoo-based HMS clones on the market are loosely connected modules with duplicated patient data per department. We design the relational model so every department model FKs back to one `hospital.patient` and one `hospital.visit`. |
| **Premium UX, not default Odoo forms** | Competitors mostly ship stock Odoo form/tree views. We design a dedicated design system (Phase 7) — calm, modern, medical-grade — closer to a vertical SaaS product than a generic backend. |
| **Workflow automation, not manual routing** | Status transitions (e.g., vitals done → doctor queue appears) happen automatically via server-side logic, not by staff manually changing stage fields. |
| **Tablet-first clinical workflows** | Nurse and doctor screens designed for tablet/bedside use from day one, not retrofitted. |
| **Built on Odoo's real ERP backbone** | Inventory, accounting, purchasing, multi-company, and HR are mature Odoo modules we integrate with — not reinvent. This is both a cost and reliability advantage. |
| **No core modification** | 100% installable addons means upgrade-safe across Odoo versions, easier to support, and compatible with Odoo.sh / standard hosting. |
| **API- and portal-ready architecture from day one** | Even though mobile app and patient portal are future phases, the data layer and security model are designed now so those layers bolt on without rearchitecting. |

---

## 7. Scalability Goals

**Technical scalability:**
- Support 100+ concurrent users on standard Odoo.sh / on-prem deployment sizing.
- Support 1,000,000+ patient records with sub-second search (proper indexing, avoid N+1 ORM patterns, use `read_group`/SQL views for dashboards).
- Multi-company support out of the box (hospital groups/chains, branch-level data segregation via record rules).
- Designed for horizontal scaling of Odoo workers (stateless business logic, no in-memory session-dependent hacks).

**Product scalability:**
- Tiered module packaging: **Clinic Edition** (OPD only: reception, doctor, pharmacy) → **Hospital Edition** (+ IPD, lab, radiology, inventory) → **Enterprise Edition** (+ multi-branch reporting, advanced security/audit, API).
- Each module independently installable and licensable, so the product can grow with the customer instead of forcing an all-or-nothing purchase.

**Roadmap scalability (future, not v1):**
- REST/JSON-RPC API layer (`hospital_api`) for third-party integrations and the future mobile app.
- Patient self-service portal (`hospital_portal`) built on Odoo's portal framework.
- Telemedicine module (video consultation scheduling/integration).
- Native mobile app (`hospital_mobile`) for doctors/nurses, consuming `hospital_api`.

---

## 8. What This Product Is *Not*

To keep scope honest and prevent feature creep before we've shipped a solid core:

- Not a national health information exchange / government registry integration platform (v1).
- Not a medical device integration platform (e.g., direct ICU monitor ingestion) in v1 — flagged as future roadmap.
- Not claiming formal HIPAA or GDPR *certification* — we build with HIPAA-inspired and GDPR-ready practices (Phase 9), but certification is a legal/organizational process outside the software itself.
- Not a replacement for Odoo's accounting/HR modules — we integrate with them, not duplicate them.

---

## Approval Checkpoint

This document defines the product's reason for existing, who it's for, and why it would win commercially. Everything in Phases 2–12 (PRD, workflows, architecture, database, modules, UX, security, sprints, coding standards, build order) will be derived from the decisions made here.

**Please review and confirm, or request changes, before I proceed to Phase 2 (Complete PRD).**

Specifically worth confirming:
1. Is "MediCore HMS" an acceptable placeholder name, or do you have a product name already?
2. Do the target hospital segments (Section 3) match who you actually intend to sell to?
3. Any must-have competitive differentiator missing from Section 6 that you already know you want?
