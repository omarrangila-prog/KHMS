# -*- coding: utf-8 -*-
{
    "name": "Hospital Security",
    "summary": "Centralised security hardening for the Hospital Management System: "
               "cross-module access rules, audit log enforcement, and security overview.",
    "description": """
Hospital Security
=================
Module 12/12 in the Hospital Management System suite.

Centralised security hardening layer that sits on top of every other
hospital_* module:

- Verifies and reinforces that NO group — including Hospital Administrator —
  can delete ``hospital.audit.log`` rows (append-only guarantee).
- Adds cross-module ``ir.rule`` domain filters ensuring every clinical record
  is scoped to the user's allowed companies (multi-company isolation).
- Security Overview: a read-only admin view summarising active groups, record
  counts, and recent audit activity.
- Settings → Security Overview menu item (admin-only).
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_base",
        "hospital_reception",
        "hospital_nurse",
        "hospital_doctor",
        "hospital_inventory",
        "hospital_pharmacy",
        "hospital_lab",
        "hospital_radiology",
        "hospital_ipd",
        "hospital_dashboard",
        "hospital_reports",
    ],
    "data": [
        # security rules (noupdate=1 to avoid overwriting on upgrade)
        "security/hospital_security_rules.xml",
        # views
        "views/hospital_security_overview_views.xml",
        "views/hospital_security_menus.xml",
    ],
    "demo": [],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
