# -*- coding: utf-8 -*-
{
    "name": "Hospital Doctor",
    "summary": "Doctor consultation workspace: diagnosis, multi-branch "
               "outcome routing, and the prescription builder.",
    "description": """
Hospital Doctor
=================
Clinical-core addon of the Hospital Management System suite, built on top
of ``hospital_nurse`` (which transitively pulls in ``hospital_base`` and
``hospital_reception``). Gives doctors:

- A single-screen Consultation workspace (``hospital.consultation``):
  patient history, vitals, and allergy banner alongside diagnosis entry
  and multi-select outcome routing (prescribe / lab / radiology / admit /
  discharge -- any combination at once, per Phase 3 §3).
- ``hospital.prescription`` / ``hospital.prescription.line``: the
  prescription model and its lines, referencing ``product.product``
  directly for the medicine catalog (see README "Product/Stock dependency
  decision").
- The extensible aggregate-visit-state routing contract
  (``hospital.visit._compute_pending_branches()`` /
  ``action_route_from_consultation()``) that ``hospital_lab``,
  ``hospital_radiology``, and ``hospital_ipd`` will extend via
  ``_inherit`` once those modules exist, so a visit can sit in the
  pharmacy queue and the (future) lab queue simultaneously and only
  reaches ``billing`` once every branch is done or cancelled.
- A same-day consultation amendment wizard (audit-logged), per the Phase
  3 §3 edge case.
- A tablet/desktop Doctor Dashboard (OWL, 3-pane layout): queue, active
  consultation, collapsible patient-history panel.
- A Prescription Builder editable list (medicine autocomplete + dosage/
  frequency/duration/route) inline on the consultation/prescription form.
- A Prescription printout QWeb report.

**Important documented limitation:** the lab/radiology/admission outcome
flags on ``hospital.consultation`` are intent-only in this module --
``hospital.lab.order``, ``hospital.radiology.order``, and
``hospital.ipd.admission`` do not exist yet (they belong to
``hospital_lab``, ``hospital_radiology``, ``hospital_ipd``, none of which
are built yet). See the README for the full extension contract those
modules must implement.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_nurse",
        "product",
    ],
    "data": [
        # security
        "security/hospital_doctor_security.xml",
        "security/ir.model.access.csv",
        # views
        "views/hospital_consultation_views.xml",
        "views/hospital_prescription_views.xml",
        "views/hospital_visit_views.xml",
        "views/hospital_doctor_dashboard_views.xml",
        "views/hospital_doctor_menus.xml",
        # wizards
        "wizards/hospital_consultation_amend_wizard_views.xml",
        # report
        "report/hospital_prescription_report.xml",
        "report/hospital_prescription_templates.xml",
    ],
    "demo": [
        "demo/hospital_consultation_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_doctor/static/src/js/**/*",
            "hospital_doctor/static/src/xml/**/*",
            "hospital_doctor/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
