# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHospitalReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    # ------------------------------------------------------------------ config

    def test_get_config_creates_default_if_missing(self):
        """get_config() must auto-create a row for a brand-new company."""
        other_company = self.env["res.company"].create({"name": "Test Reports Co"})
        self.env["hospital.report.config"].search(
            [("company_id", "=", other_company.id)]
        ).unlink()
        config = self.env["hospital.report.config"].get_config(other_company.id)
        self.assertEqual(config.company_id, other_company)

    def test_get_config_returns_existing(self):
        """get_config() must return the existing row, not create a duplicate."""
        config1 = self.env["hospital.report.config"].get_config(self.company.id)
        config2 = self.env["hospital.report.config"].get_config(self.company.id)
        self.assertEqual(config1.id, config2.id)

    def test_config_defaults(self):
        other_company = self.env["res.company"].create({"name": "Test Reports Co Defaults"})
        self.env["hospital.report.config"].search(
            [("company_id", "=", other_company.id)]
        ).unlink()
        config = self.env["hospital.report.config"].get_config(other_company.id)
        self.assertTrue(config.header_text)
        self.assertTrue(config.footer_text)
        self.assertTrue(config.primary_color.startswith("#"))

    def test_company_uniqueness_constraint(self):
        """Creating a second config for the same company must raise."""
        from odoo.exceptions import ValidationError
        from psycopg2 import errors as pg_errors

        other_company = self.env["res.company"].create({"name": "Test Reports Unique Co"})
        self.env["hospital.report.config"].create({"company_id": other_company.id})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env["hospital.report.config"].create(
                    {"company_id": other_company.id}
                )

    # ------------------------------------------------------------------ census wizard

    def test_census_wizard_date_validation(self):
        """Wizard must reject date_from > date_to."""
        from odoo.exceptions import ValidationError
        from odoo import fields

        wizard = self.env["hospital.census.wizard"].create({
            "date_from": "2025-06-10",
            "date_to": "2025-06-09",
            "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError):
            wizard._check_dates()

    def test_census_wizard_date_valid(self):
        """Wizard must accept date_from == date_to without raising."""
        wizard = self.env["hospital.census.wizard"].create({
            "date_from": "2025-06-10",
            "date_to": "2025-06-10",
            "company_id": self.company.id,
        })
        wizard._check_dates()  # must not raise

    # ------------------------------------------------------------------ patient visit history

    def test_patient_visit_history_report_action_exists(self):
        """The ir.actions.report record must be loadable by xmlid."""
        action = self.env.ref(
            "hospital_reports.action_hospital_patient_visit_history_report",
            raise_if_not_found=False,
        )
        self.assertIsNotNone(action)
        self.assertEqual(action.model, "hospital.patient")

    def test_daily_census_report_action_exists(self):
        action = self.env.ref(
            "hospital_reports.action_hospital_daily_census_report",
            raise_if_not_found=False,
        )
        self.assertIsNotNone(action)
        self.assertEqual(action.model, "hospital.visit")

    def test_ward_occupancy_report_action_exists(self):
        action = self.env.ref(
            "hospital_reports.action_hospital_ward_occupancy_report",
            raise_if_not_found=False,
        )
        self.assertIsNotNone(action)
        self.assertEqual(action.model, "hospital.ward")
