# -*- coding: utf-8 -*-
{
    "name": "Hospital Radiology",
    "summary": "Radiology order and result management for the Hospital Management System.",
    "description": """
Hospital Radiology
==================
Manages the full radiology order-to-result lifecycle (mirrors hospital_lab
for imaging modalities):

- ``hospital.radiology.study``: catalog of imaging studies (X-Ray, CT, MRI, etc.).
- ``hospital.radiology.order``: orders from doctors through scheduling,
  in-progress, and completion.
- ``hospital.radiology.result``: findings and impression text with image/
  PDF attachment upload.
- Extends ``hospital.visit`` via ``_inherit`` to add ``radiology_order_ids``
  and make the visit's aggregate-state routing aware of real radiology
  completion, replacing the intent-only flag left by ``hospital_doctor``.

Depends on ``hospital_doctor`` (which brings in hospital_nurse,
hospital_reception, and hospital_base).
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
        # security — groups first, then ACLs, then record rules
        "security/hospital_radiology_security.xml",
        "security/ir.model.access.csv",
        # sequences
        "data/hospital_radiology_sequence.xml",
        # default catalog (non-demo: installs in every environment)
        "data/hospital_radiology_study_data.xml",
        # views
        "views/hospital_radiology_study_views.xml",
        "views/hospital_radiology_order_views.xml",
        "views/hospital_radiology_result_views.xml",
        "views/hospital_radiology_menus.xml",
        # wizards
        "wizards/hospital_radiology_order_cancel_wizard_views.xml",
        # reports
        "report/hospital_radiology_report.xml",
        "report/hospital_radiology_report_templates.xml",
    ],
    "demo": [
        "demo/hospital_radiology_demo.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
