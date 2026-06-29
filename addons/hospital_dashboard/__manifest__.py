# -*- coding: utf-8 -*-
{
    "name": "Hospital Executive Dashboard",
    "summary": "Cross-department admin/executive KPI dashboard for the "
               "Hospital Management System.",
    "description": """
Hospital Executive Dashboard
=============================
Tenth addon of the Hospital Management System suite. Per-department
dashboards (reception, nurse, doctor, pharmacy, lab, radiology, ward) each
ship in their own module; this module adds the admin/executive
cross-cutting rollup on top of all of them:

- ``hospital.dashboard.kpi``: a SQL-view-backed (``_auto = False``)
  aggregate model, one row per company, computing patient volume (today/
  this week), bed occupancy %, average doctor wait time, and ward-charge
  revenue (length-of-stay billing, the only real billing-shaped number
  that exists anywhere in the suite today) - all computed in PostgreSQL,
  not pulled into Python and looped (Phase 5 §10).
- Executive Dashboard (OWL): KPI card grid, refreshable on demand.

Depends on every clinical module so it can aggregate across all of them -
the SQL view only ever queries tables owned by modules in the declared
dependency list, all of which are guaranteed installed before this
module loads.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_base",
        "hospital_reception",
        "hospital_doctor",
        "hospital_pharmacy",
        "hospital_lab",
        "hospital_radiology",
        "hospital_ipd",
    ],
    "data": [
        "security/hospital_dashboard_security.xml",
        "security/ir.model.access.csv",
        "views/hospital_dashboard_kpi_views.xml",
        "views/hospital_dashboard_menus.xml",
    ],
    "demo": [
        "demo/hospital_dashboard_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_dashboard/static/src/js/**/*",
            "hospital_dashboard/static/src/xml/**/*",
            "hospital_dashboard/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
