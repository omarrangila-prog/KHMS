# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHospitalPatient(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]

    def test_patient_code_sequence_generated(self):
        patient = self.Patient.create(
            {
                "name": "Test Patient One",
                "date_of_birth": "1990-01-01",
                "phone": "+10000000001",
                "identity_number": "SEQ-TEST-1",
            }
        )
        self.assertTrue(patient.patient_code)
        self.assertTrue(patient.patient_code.startswith("PT/"))

    def test_age_computation(self):
        today = fields.Date.context_today(self.Patient)
        dob = today - relativedelta(years=30, days=1)
        patient = self.Patient.create(
            {
                "name": "Age Test Patient",
                "date_of_birth": fields.Date.to_string(dob),
                "phone": "+10000000002",
            }
        )
        self.assertEqual(patient.age, 30)

    def test_date_of_birth_in_future_raises(self):
        future_date = fields.Date.context_today(self.Patient) + relativedelta(days=5)
        with self.assertRaises(ValidationError):
            self.Patient.create(
                {
                    "name": "Future DOB Patient",
                    "date_of_birth": fields.Date.to_string(future_date),
                    "phone": "+10000000003",
                }
            )

    def test_duplicate_detection_by_identity_number(self):
        first = self.Patient.create(
            {
                "name": "Duplicate Source",
                "date_of_birth": "1985-06-15",
                "phone": "+10000000004",
                "identity_number": "DUP-0001",
            }
        )
        second = self.Patient.create(
            {
                "name": "Duplicate Source Look-Alike",
                "date_of_birth": "1985-06-15",
                "phone": "+10000000005",
                "identity_number": "DUP-0001",
            }
        )
        matches = first.check_duplicate()
        self.assertIn(second, matches[first.id])

        no_match_patient = self.Patient.create(
            {
                "name": "Unique Patient",
                "date_of_birth": "1985-06-15",
                "phone": "+10000000006",
                "identity_number": "DUP-9999",
            }
        )
        matches_for_unique = no_match_patient.check_duplicate()
        self.assertFalse(matches_for_unique[no_match_patient.id])

    def test_duplicate_detection_is_non_blocking(self):
        """Creating a second patient with the same identity_number must
        NOT raise -- duplicate detection is informational only."""
        self.Patient.create(
            {
                "name": "Non Blocking One",
                "date_of_birth": "1980-01-01",
                "phone": "+10000000007",
                "identity_number": "NB-0001",
            }
        )
        try:
            self.Patient.create(
                {
                    "name": "Non Blocking Two",
                    "date_of_birth": "1980-01-01",
                    "phone": "+10000000008",
                    "identity_number": "NB-0001",
                }
            )
        except ValidationError:
            self.fail(
                "Duplicate identity_number must not raise a ValidationError "
                "on create (non-blocking by design)."
            )
