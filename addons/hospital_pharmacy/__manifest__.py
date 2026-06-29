# -*- coding: utf-8 -*-
{
    "name": "Hospital Pharmacy",
    "summary": "Prescription fulfillment, dispensing safety checks, and "
               "stock move integration for the Hospital Management System.",
    "description": """
Hospital Pharmacy
==================
Sixth addon of the Hospital Management System suite. Bridges
``hospital_doctor`` (which owns the prescription model/line fields) and
``hospital_inventory`` (which owns the Pharmacy stock location and the
medicine product catalog) to implement the full dispensing flow per
Phase 3 §5.

Key capabilities:
- ``hospital.prescription.line.dispense()`` -- single entry point for all
  dispensing: allergy conflict check (blocks without override), stock
  availability check, real ``stock.move`` creation/validation, qty/state
  update, prescription aggregate state recomputation, visit-level branch-
  completion routing.
- Allergy-override flow: override_allergy=True + mandatory override_reason;
  persisted on the line and separately audit-logged via hospital.audit.log.
- Billing-hook stub: ``_create_billing_line()`` is called at the correct
  point in the dispense flow but is a deliberate no-op until the future
  billing/invoicing module (not yet in the build order) overrides it via
  _inherit.
- Pharmacy Dashboard OWL component (split view: queue/detail with stock
  badges, D/A keyboard shortcuts).
- Batch-dispense wizard (per-line qty, override flags, per-line allergy
  banners).
- Backorder list for lines in partial/backordered state.
- Dispensing Receipt QWeb report.

Depends on ``hospital_doctor`` + ``hospital_inventory`` only -- the
integration point for both.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_doctor",
        "hospital_inventory",
    ],
    "data": [
        # security (must load before models that reference the group)
        "security/hospital_pharmacy_security.xml",
        "security/ir.model.access.csv",
        # data (locations must load before demo data references them)
        "data/hospital_pharmacy_data.xml",
        # wizard views
        "views/hospital_dispense_wizard_views.xml",
        # model views + actions
        "views/hospital_prescription_views.xml",
        # dashboard action (references client action tag)
        "views/hospital_pharmacy_dashboard_views.xml",
        # menus (last: reference all actions above)
        "views/hospital_pharmacy_menus.xml",
        # reports
        "report/hospital_dispensing_receipt_report.xml",
        "report/hospital_dispensing_receipt_templates.xml",
    ],
    "demo": [
        "demo/hospital_pharmacy_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_pharmacy/static/src/js/**/*",
            "hospital_pharmacy/static/src/xml/**/*",
            "hospital_pharmacy/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
