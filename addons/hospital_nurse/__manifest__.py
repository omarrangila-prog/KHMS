# -*- coding: utf-8 -*-
{
    "name": "Hospital Nurse",
    "summary": "Nurse station: vitals capture with auto-escalation and "
               "the OPD nurse task checklist.",
    "description": """
Hospital Nurse
===============
Nurse-station addon for the Hospital Management System suite, built on top
of ``hospital_base`` and ``hospital_reception``. Gives nursing staff:

- Structured vitals capture (``hospital.vitals``) with computed BMI and
  clinically-informed range constraints.
- Automatic priority escalation: abnormal vitals (e.g. very high/low blood
  pressure, fever, hypoxia) flag the visit ``urgent`` without ever
  de-escalating an existing ``emergency`` priority.
- Automatic queue transition: recording vitals moves the visit from
  ``waiting_nurse`` to ``waiting_doctor`` in the same action, per the
  Phase 3 §2 nurse workflow contract.
- A tablet-first Nurse Dashboard (OWL): next patient for vitals, a
  quick-vitals-entry shortcut, and the nurse task checklist.
- A quick-vitals-entry form with auto-computed, color-flagged BMI and a
  single "Save & Send to Doctor" action.
- ``hospital.nurse.task``: a simple OPD nurse task checklist, extended by
  ``hospital_ipd`` (not yet built) with ward-round/admission fields.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_base",
        "hospital_reception",
    ],
    "data": [
        # security
        "security/hospital_nurse_security.xml",
        "security/ir.model.access.csv",
        # views
        "views/hospital_vitals_views.xml",
        "views/hospital_nurse_task_views.xml",
        "views/hospital_nurse_dashboard_views.xml",
        "views/hospital_nurse_menus.xml",
    ],
    "demo": [
        "demo/hospital_vitals_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_nurse/static/src/js/**/*",
            "hospital_nurse/static/src/xml/**/*",
            "hospital_nurse/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
