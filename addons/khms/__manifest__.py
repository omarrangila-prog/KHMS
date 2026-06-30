# -*- coding: utf-8 -*-
{
    "name": "KHMS - Hospital Management System",
    "summary": "Complete Hospital Management System: patients, visits, reception, "
               "nursing, doctors, IPD, pharmacy, inventory, lab, radiology, "
               "reports and security in a single installable app.",
    "description": """
KHMS - Hospital Management System
==================================
Single-click installer for the full Hospital Management System suite.

Installing this app pulls in every KHMS module:

- Hospital Base       - patients, visits, doctors, departments, audit log
- Hospital Reception  - appointment scheduling and front-desk check-in
- Hospital Nurse      - vitals, nursing tasks, triage
- Hospital Doctor     - consultations, prescriptions
- Hospital IPD        - wards, beds, admissions, discharges
- Hospital Inventory  - pharmacy warehouse and stock locations
- Hospital Pharmacy   - dispensing and medicine batches
- Hospital Lab        - lab orders and results
- Hospital Radiology  - radiology orders and results
- Hospital Dashboard  - executive OWL dashboards
- Hospital Reports    - cross-module printable reports and branding
- Hospital Security   - cross-module access rules and audit enforcement

This module has no models or views of its own - it exists only as the
top-level app entry so the whole suite can be installed and upgraded as
one unit from Apps.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_security",
    ],
    "data": [],
    "demo": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
}
