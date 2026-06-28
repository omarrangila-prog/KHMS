# -*- coding: utf-8 -*-
{
    "name": "Hospital Reception",
    "summary": "Front-desk operations: patient registration, appointment "
               "booking, visit check-in, and the reception queue dashboard.",
    "description": """
Hospital Reception
===================
Front-desk addon for the Hospital Management System suite, built on top of
``hospital_base``. Gives reception staff:

- A Reception Dashboard (OWL) with live KPIs, a doctor-grouped queue kanban,
  and today's appointment list.
- A combined "search existing or register new" Patient Registration wizard
  with non-blocking duplicate-match warnings (reuses
  ``hospital.patient.check_duplicate()`` from ``hospital_base``).
- Appointment booking and check-in (creates and confirms a ``hospital.visit``
  in one action).
- A searchable Patients quick-lookup list view.
- A printable queue ticket / token slip report.
- A visit cancellation wizard enforcing a mandatory reason.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_base",
    ],
    "data": [
        # security
        "security/hospital_reception_security.xml",
        "security/ir.model.access.csv",
        # data
        "data/hospital_reception_sequence_data.xml",
        # views
        "views/hospital_appointment_views.xml",
        "views/hospital_visit_views.xml",
        "views/hospital_reception_dashboard_views.xml",
        "views/hospital_reception_menus.xml",
        # wizards
        "wizards/hospital_patient_registration_wizard_views.xml",
        "wizards/hospital_visit_cancel_wizard_views.xml",
        # report
        "report/hospital_queue_ticket_report.xml",
        "report/hospital_queue_ticket_templates.xml",
    ],
    "demo": [
        "demo/hospital_visit_demo.xml",
        "demo/hospital_appointment_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_reception/static/src/js/**/*",
            "hospital_reception/static/src/xml/**/*",
            "hospital_reception/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
