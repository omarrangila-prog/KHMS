# -*- coding: utf-8 -*-
{
    "name": "Hospital Reports",
    "summary": "Centralised report branding configuration and cross-module "
               "aggregate printable reports for the Hospital Management System.",
    "description": """
Hospital Reports
================
Module 11/12 in the Hospital Management System suite.

- ``hospital.report.config``: per-company report branding singleton
  (logo override, header/footer text, colour scheme).
- Shared QWeb base layout ``hospital_reports.report_layout`` that every
  per-module report can ``t-call`` to inherit consistent branding without
  hard-wiring it into each downstream module.
- Aggregate, admin-only printable reports:
    * Patient Visit History  (all visits for a single patient)
    * Daily Census           (all today's visits for the company)
    * Ward Occupancy         (current bed state across all wards)
- Settings → Report Branding configuration menu (admin-only).
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_base",
        "hospital_doctor",
        "hospital_pharmacy",
        "hospital_lab",
        "hospital_radiology",
        "hospital_ipd",
    ],
    "data": [
        # security
        "security/hospital_reports_security.xml",
        "security/ir.model.access.csv",
        # data
        "data/hospital_reports_data.xml",
        # views / config
        "views/hospital_report_config_views.xml",
        # wizards
        "wizards/hospital_census_wizard_views.xml",
        # reports
        "report/hospital_shared_layout.xml",
        "report/hospital_patient_visit_history_report.xml",
        "report/hospital_patient_visit_history_templates.xml",
        "report/hospital_daily_census_report.xml",
        "report/hospital_daily_census_templates.xml",
        "report/hospital_ward_occupancy_report.xml",
        "report/hospital_ward_occupancy_templates.xml",
        # config menus
        "views/hospital_reports_menus.xml",
    ],
    "demo": [
        "demo/hospital_reports_demo.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
