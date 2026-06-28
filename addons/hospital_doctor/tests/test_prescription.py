# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPrescription(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Visit = cls.env["hospital.visit"]
        cls.Doctor = cls.env["hospital.doctor"]
        cls.Prescription = cls.env["hospital.prescription"]
        cls.PrescriptionLine = cls.env["hospital.prescription.line"]
        cls.Product = cls.env["product.product"]

        cls.doctor_user = cls.env["res.users"].create(
            {
                "name": "Dr. Test Prescription",
                "login": "dr.test.prescription@example.com",
                "email": "dr.test.prescription@example.com",
            }
        )
        cls.doctor = cls.Doctor.create({"user_id": cls.doctor_user.id})
        cls.patient = cls.Patient.create(
            {
                "name": "Prescription Test Patient",
                "date_of_birth": "1992-02-02",
                "phone": "+10000004101",
                "identity_number": "PRESC-TEST-0001",
            }
        )
        cls.visit = cls.Visit.create(
            {
                "patient_id": cls.patient.id,
                "visit_type": "opd",
                "doctor_id": cls.doctor.id,
            }
        )
        cls.medicine = cls.Product.create(
            {"name": "Test Medicine Line", "type": "consu"}
        )

    def _new_prescription(self, **line_vals):
        vals = {
            "medicine_id": self.medicine.id,
            "dosage": "500mg",
            "frequency": "BID",
            "duration_days": 5,
            "route": "oral",
            "qty_prescribed": 10,
        }
        vals.update(line_vals)
        return self.Prescription.create(
            {
                "visit_id": self.visit.id,
                "doctor_id": self.doctor.id,
                "line_ids": [(0, 0, vals)],
            }
        )

    # -- Creation ------------------------------------------------------------

    def test_prescription_line_creation(self):
        prescription = self._new_prescription()
        self.assertEqual(len(prescription.line_ids), 1)
        line = prescription.line_ids[0]
        self.assertEqual(line.state, "pending")
        self.assertEqual(line.qty_dispensed, 0.0)
        self.assertEqual(line.prescription_id, prescription)
        self.assertEqual(line.visit_id, self.visit)

    def test_prescription_default_state_is_draft(self):
        prescription = self._new_prescription()
        self.assertEqual(prescription.state, "draft")

    # -- qty_dispensed <= qty_prescribed constraint ---------------------------

    def test_qty_dispensed_exceeding_prescribed_raises(self):
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        with self.assertRaises(ValidationError):
            line.write({"qty_dispensed": 6})

    def test_qty_dispensed_equal_to_prescribed_allowed(self):
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        line.write({"qty_dispensed": 5})
        self.assertEqual(line.qty_dispensed, 5)

    def test_qty_dispensed_below_prescribed_allowed(self):
        prescription = self._new_prescription(qty_prescribed=10)
        line = prescription.line_ids[0]
        line.write({"qty_dispensed": 4})
        self.assertEqual(line.qty_dispensed, 4)

    def test_qty_prescribed_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._new_prescription(qty_prescribed=0)

    def test_qty_dispensed_exceeding_prescribed_on_create_raises(self):
        with self.assertRaises(ValidationError):
            self._new_prescription(qty_prescribed=5, qty_dispensed=10)

    # -- Cancellation ----------------------------------------------------------

    def test_action_cancel_cancels_open_lines(self):
        prescription = self._new_prescription()
        prescription.action_cancel()
        self.assertEqual(prescription.state, "cancelled")
        self.assertTrue(
            all(line.state == "cancelled" for line in prescription.line_ids)
        )

    def test_action_cancel_blocked_when_dispensed(self):
        prescription = self._new_prescription()
        prescription.state = "dispensed"
        with self.assertRaises(UserError):
            prescription.action_cancel()
