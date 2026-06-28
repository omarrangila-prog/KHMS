# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHospitalVisit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Visit = cls.env["hospital.visit"]
        cls.patient = cls.Patient.create(
            {
                "name": "Visit Test Patient",
                "date_of_birth": "1990-01-01",
                "phone": "+10000001001",
                "identity_number": "VIS-TEST-0001",
            }
        )

    def test_visit_code_sequence_generated(self):
        visit = self.Visit.create(
            {
                "patient_id": self.patient.id,
                "visit_type": "opd",
            }
        )
        self.assertTrue(visit.visit_code)
        self.assertTrue(visit.visit_code.startswith("VS/"))
        self.assertEqual(visit.state, "draft")

    def test_visit_code_sequence_increments(self):
        visit_one = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        visit_two = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        self.assertNotEqual(visit_one.visit_code, visit_two.visit_code)

    def test_cancel_requires_reason_via_action(self):
        visit = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        with self.assertRaises(UserError):
            visit.action_cancel()

    def test_cancel_with_reason_succeeds(self):
        visit = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        visit.cancel_reason = "Patient requested cancellation."
        visit.action_cancel()
        self.assertEqual(visit.state, "cancelled")

    def test_cancel_state_without_reason_blocked_by_constraint(self):
        visit = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        with self.assertRaises(ValidationError):
            visit.write({"state": "cancelled"})

    def test_state_transition_flow(self):
        visit = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        visit.action_confirm()
        self.assertEqual(visit.state, "waiting_nurse")
        visit.action_send_to_doctor()
        self.assertEqual(visit.state, "waiting_doctor")
        visit.action_to_billing()
        self.assertEqual(visit.state, "billing")
        visit.action_done()
        self.assertEqual(visit.state, "done")

    def test_confirm_requires_draft_state(self):
        visit = self.Visit.create(
            {"patient_id": self.patient.id, "visit_type": "opd"}
        )
        visit.action_confirm()
        with self.assertRaises(UserError):
            visit.action_confirm()
