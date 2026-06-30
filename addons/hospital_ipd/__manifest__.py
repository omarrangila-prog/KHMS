# -*- coding: utf-8 -*-
{
    "name": "Hospital In-Patient Department",
    "summary": "Ward/bed management, admissions, transfers, and discharge "
               "for the Hospital Management System.",
    "description": """
Hospital In-Patient Department (IPD)
=====================================
Full inpatient lifecycle for the Hospital Management System suite:

- ``hospital.ward`` / ``hospital.bed``: ward and bed master data with a
  real-time occupancy dashboard.
- ``hospital.ipd.admission``: admission request -> bed assignment ->
  in-stay state machine, backed by a DB-level partial unique index
  guaranteeing at most one active admission per bed.
- ``hospital.bed.transfer``: mid-stay ward/bed transfer, recorded as a
  child row of the same admission (never a new admission record).
- ``hospital.discharge``: discharge summary, blocked at the model level
  while any lab/radiology/pharmacy order tied to the visit remains open,
  with length-of-stay billing on confirmation.
- Extends ``hospital.visit`` via ``_inherit`` to add ``admission_id`` and
  make the visit's aggregate-state routing ("billing" gate) aware of real
  admission completion, replacing the intent-only flag that
  ``hospital_doctor`` left as a placeholder.
- Extends ``hospital.nurse.task`` via ``_inherit`` to add ``admission_id``
  for ward-round/MAR checklist items, per the extension point
  ``hospital_nurse`` documented on that model.
- A Ward Dashboard (OWL): bed occupancy grid, color-coded by status,
  grouped by ward.

Depends on ``hospital_doctor`` and ``hospital_nurse`` (which transitively
bring in ``hospital_reception`` and ``hospital_base``) -- deliberately NOT
on ``hospital_lab``/``hospital_radiology``/``hospital_pharmacy``, to avoid a
dependency cycle. The discharge-blocking check instead queries
``hospital.visit._compute_pending_branches()``, the extension contract
``hospital_doctor`` built for exactly this purpose.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_doctor",
        "hospital_nurse",
    ],
    "data": [
        # security — load order: groups first, then ACLs, then record rules
        "security/hospital_ipd_security.xml",
        "security/ir.model.access.csv",
        # sequences
        "data/hospital_ipd_sequence.xml",
        # wizards
        "wizards/hospital_admission_wizard_views.xml",
        "wizards/hospital_transfer_wizard_views.xml",
        "wizards/hospital_discharge_wizard_views.xml",
        # reports
        "report/hospital_discharge_summary_report.xml",
        "report/hospital_discharge_summary_templates.xml",
        # views
        "views/hospital_ward_views.xml",
        "views/hospital_bed_views.xml",
        "views/hospital_ipd_admission_views.xml",
        "views/hospital_discharge_views.xml",
        "views/hospital_ward_dashboard_views.xml",
        "views/hospital_ipd_menus.xml",
    ],
    "demo": [
        "demo/hospital_ipd_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_ipd/static/src/js/**/*",
            "hospital_ipd/static/src/xml/**/*",
            "hospital_ipd/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
