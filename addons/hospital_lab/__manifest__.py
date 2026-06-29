# -*- coding: utf-8 -*-
{
    "name": "Hospital Laboratory",
    "summary": "Laboratory order and result management for the Hospital Management System.",
    "description": """
Hospital Laboratory
===================
Manages the full lab order-to-result lifecycle:

- ``hospital.lab.test``: catalog of lab tests with normal ranges.
- ``hospital.lab.order``: orders from doctors, state-machine from ordered
  through sample collection, processing and completion.
- ``hospital.lab.result``: structured result entry with abnormal-value
  auto-flagging and attachment support.
- Extends ``hospital.visit`` via ``_inherit`` to add ``lab_order_ids``
  and make the visit's aggregate-state routing ("billing" gate) aware
  of real lab completion, replacing the intent-only flag that
  ``hospital_doctor`` left as a placeholder.

Depends on ``hospital_doctor`` (which brings in ``hospital_nurse``,
``hospital_reception``, and ``hospital_base``).
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_doctor",
    ],
    "data": [
        # security — load order: groups first, then ACLs, then record rules
        "security/hospital_lab_security.xml",
        "security/ir.model.access.csv",
        # sequences
        "data/hospital_lab_sequence.xml",
        # default catalog (non-demo: installs in every environment)
        "data/hospital_lab_test_data.xml",
        # views
        "views/hospital_lab_test_views.xml",
        "views/hospital_lab_order_views.xml",
        "views/hospital_lab_result_views.xml",
        "views/hospital_lab_menus.xml",
        # wizards
        "wizards/hospital_lab_order_cancel_wizard_views.xml",
        # reports
        "report/hospital_lab_report.xml",
        "report/hospital_lab_report_templates.xml",
    ],
    "demo": [
        "demo/hospital_lab_demo.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
