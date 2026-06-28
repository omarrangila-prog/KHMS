# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRegistrationWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Wizard = cls.env["hospital.patient.registration.wizard"]
        cls.Visit = cls.env["hospital.visit"]

    def test_duplicate_warning_surfaces_for_matching_identity_number(self):
        self.Patient.create(
            {
                "name": "Existing Duplicate",
                "date_of_birth": "1988-01-01",
                "phone": "+10000003001",
                "identity_number": "WIZ-DUP-0001",
            }
        )
        wizard = self.Wizard.create(
            {
                "name": "New Arrival Same ID",
                "date_of_birth": "1988-01-01",
                "phone": "+10000003002",
                "identity_number": "WIZ-DUP-0001",
            }
        )
        self.assertTrue(wizard.has_duplicate_warning)
        self.assertEqual(len(wizard.duplicate_patient_ids), 1)

    def test_no_duplicate_warning_for_unique_identity_number(self):
        wizard = self.Wizard.create(
            {
                "name": "Unique Arrival",
                "date_of_birth": "1991-02-02",
                "phone": "+10000003003",
                "identity_number": "WIZ-UNIQUE-0001",
            }
        )
        self.assertFalse(wizard.has_duplicate_warning)
        self.assertFalse(wizard.duplicate_patient_ids)

    def test_duplicate_warning_suppressed_when_existing_patient_selected(self):
        existing = self.Patient.create(
            {
                "name": "Existing Selected",
                "date_of_birth": "1979-09-09",
                "phone": "+10000003004",
                "identity_number": "WIZ-DUP-0002",
            }
        )
        self.Patient.create(
            {
                "name": "Another With Same ID",
                "date_of_birth": "1979-09-09",
                "phone": "+10000003005",
                "identity_number": "WIZ-DUP-0002",
            }
        )
        wizard = self.Wizard.create({"patient_id": existing.id})
        self.assertFalse(wizard.has_duplicate_warning)

    def test_confirm_creates_new_patient_and_confirmed_visit(self):
        wizard = self.Wizard.create(
            {
                "name": "Brand New Patient",
                "date_of_birth": "1995-05-05",
                "phone": "+10000003006",
                "identity_number": "WIZ-NEW-0001",
                "payer_type": "cash",
            }
        )
        result = wizard.action_confirm()
        new_patient = self.Patient.search(
            [("identity_number", "=", "WIZ-NEW-0001")]
        )
        self.assertEqual(len(new_patient), 1)
        visit = self.Visit.search([("patient_id", "=", new_patient.id)])
        self.assertEqual(len(visit), 1)
        self.assertEqual(visit.state, "waiting_nurse")
        self.assertEqual(result["res_model"], "hospital.visit")
        self.assertEqual(result["res_id"], visit.id)

    def test_confirm_reuses_existing_patient(self):
        existing = self.Patient.create(
            {
                "name": "Reused Patient",
                "date_of_birth": "1983-03-03",
                "phone": "+10000003007",
                "identity_number": "WIZ-REUSE-0001",
            }
        )
        wizard = self.Wizard.create({"patient_id": existing.id})
        wizard.action_confirm()
        visits = self.Visit.search([("patient_id", "=", existing.id)])
        self.assertEqual(len(visits), 1)
        self.assertEqual(visits.state, "waiting_nurse")
        # No second patient record should have been created.
        self.assertEqual(
            self.Patient.search_count(
                [("identity_number", "=", "WIZ-REUSE-0001")]
            ),
            1,
        )

    def test_confirm_without_name_or_existing_patient_raises(self):
        from odoo.exceptions import UserError

        wizard = self.Wizard.create({})
        with self.assertRaises(UserError):
            wizard.action_confirm()
