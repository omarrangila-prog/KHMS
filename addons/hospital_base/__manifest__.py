# -*- coding: utf-8 -*-
{
    "name": "Hospital Base",
    "summary": "Foundational layer for the Hospital Management System: "
               "patients, visits, doctors, departments, audit log.",
    "description": """
Hospital Base
==============
Foundational addon for the Hospital Management System suite. Provides the
core master data and the patient/visit spine that every other hospital_*
module builds on:

- Patient registry with allergy/chronic-condition tracking and duplicate
  detection.
- Visit (the spine record that downstream clinical modules extend).
- Department and Doctor master data with weekly schedules.
- A tamper-resistant, append-only audit log and a reusable audit mixin.
- Base security groups (Hospital User / Hospital Administrator) and
  multi-company record rules.
- A printable Patient ID Card report.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        # security
        "security/hospital_base_security.xml",
        "security/ir.model.access.csv",
        # data
        "data/hospital_sequence_data.xml",
        # views
        "views/hospital_patient_views.xml",
        "views/hospital_visit_views.xml",
        "views/hospital_department_views.xml",
        "views/hospital_doctor_views.xml",
        "views/hospital_audit_log_views.xml",
        "views/hospital_menus.xml",
        # wizards
        "wizards/hospital_patient_merge_wizard_views.xml",
        # report
        "report/hospital_patient_id_card_report.xml",
        "report/hospital_patient_id_card_templates.xml",
    ],
    "demo": [
        "demo/hospital_department_demo.xml",
        "demo/hospital_doctor_demo.xml",
        "demo/hospital_patient_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_base/static/src/scss/_variables.scss",
            "hospital_base/static/src/scss/hospital_shell.scss",
            "hospital_base/static/src/scss/hospital_views.scss",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
