# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDispense(TransactionCase):
    """Dispense logic tests (Phase 6 §5 test scope):

    - Allergy conflict blocks dispense without override.
    - Override + reason allows dispense and is audit-logged.
    - Full dispense (adequate stock) decrements stock and sets
      line.state = dispensed, prescription.state = dispensed.
    - Partial dispense (insufficient stock) sets line.state = partial
      and prescription.state = partially_dispensed.
    - Backordered dispense (zero stock) sets line.state = backordered.
    - Prescription aggregate state correctly reflects all-lines-dispensed
      vs. mixed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Allergy = cls.env["hospital.patient.allergy"]
        cls.Visit = cls.env["hospital.visit"]
        cls.Doctor = cls.env["hospital.doctor"]
        cls.Prescription = cls.env["hospital.prescription"]
        cls.PrescriptionLine = cls.env["hospital.prescription.line"]
        cls.Product = cls.env["product.product"]
        cls.StockQuant = cls.env["stock.quant"]

        cls.doctor_user = cls.env["res.users"].create(
            {
                "name": "Pharm Test Doctor",
                "login": "pharm.test.doctor@example.com",
                "email": "pharm.test.doctor@example.com",
            }
        )
        cls.doctor = cls.Doctor.create({"user_id": cls.doctor_user.id})

        cls.patient = cls.Patient.create(
            {
                "name": "Pharmacy Test Patient",
                "date_of_birth": "1985-06-15",
                "phone": "+99000000001",
                "identity_number": "PHARM-TEST-0001",
            }
        )
        cls.patient_with_allergy = cls.Patient.create(
            {
                "name": "Allergy Test Patient",
                "date_of_birth": "1990-03-20",
                "phone": "+99000000002",
                "identity_number": "PHARM-TEST-0002",
            }
        )

        cls.visit = cls.Visit.create(
            {
                "patient_id": cls.patient.id,
                "visit_type": "opd",
                "doctor_id": cls.doctor.id,
            }
        )
        cls.visit_allergy = cls.Visit.create(
            {
                "patient_id": cls.patient_with_allergy.id,
                "visit_type": "opd",
                "doctor_id": cls.doctor.id,
            }
        )

        # A storable product so qty_available is meaningful
        cls.medicine = cls.Product.create(
            {
                "name": "Test Paracetamol",
                "type": "consu",
                "is_storable": True,
            }
        )

        # Get pharmacy location (may not exist without hospital_inventory
        # installed; use a fallback company location for unit tests)
        cls.pharmacy_location = cls.env.ref(
            "hospital_inventory.stock_location_pharmacy_store",
            raise_if_not_found=False,
        )
        cls.consumption_location = cls.env.ref(
            "hospital_pharmacy.stock_location_patient_consumption",
            raise_if_not_found=False,
        )
        if not cls.pharmacy_location:
            # Fallback for environments where hospital_inventory is not
            # installed alongside hospital_pharmacy (e.g. unit-test
            # isolation with only direct dependencies loaded). Create a
            # minimal internal location.
            parent_loc = cls.env.ref("stock.stock_location_locations")
            cls.pharmacy_location = cls.env["stock.location"].create(
                {
                    "name": "Test Pharmacy Store",
                    "location_id": parent_loc.id,
                    "usage": "internal",
                }
            )
        if not cls.consumption_location:
            virtual_loc = cls.env.ref("stock.stock_location_locations_virtual")
            cls.consumption_location = cls.env["stock.location"].create(
                {
                    "name": "Test Patient Consumption",
                    "location_id": virtual_loc.id,
                    "usage": "inventory",
                }
            )

    def _seed_stock(self, qty):
        """Seed on-hand stock at the pharmacy location for cls.medicine."""
        quant = self.StockQuant.search(
            [
                ("product_id", "=", self.medicine.id),
                ("location_id", "=", self.pharmacy_location.id),
            ],
            limit=1,
        )
        if quant:
            quant.inventory_quantity = qty
        else:
            quant = self.StockQuant.create(
                {
                    "product_id": self.medicine.id,
                    "location_id": self.pharmacy_location.id,
                    "inventory_quantity": qty,
                }
            )
        quant.action_apply_inventory()

    def _new_prescription(self, patient_visit=None, qty_prescribed=10, **line_vals):
        visit = patient_visit or self.visit
        vals = {
            "medicine_id": self.medicine.id,
            "qty_prescribed": qty_prescribed,
            "route": "oral",
        }
        vals.update(line_vals)
        return self.Prescription.create(
            {
                "visit_id": visit.id,
                "doctor_id": self.doctor.id,
                "line_ids": [(0, 0, vals)],
            }
        )

    def _add_allergy(self, patient, allergy_name, severity="mild"):
        return self.Allergy.create(
            {
                "patient_id": patient.id,
                "name": allergy_name,
                "severity": severity,
            }
        )

    # -------------------------------------------------------------------------
    # Allergy conflict tests
    # -------------------------------------------------------------------------

    def test_allergy_conflict_blocks_dispense_without_override(self):
        """A medicine matching the patient's allergy raises UserError unless
        override_allergy=True is passed."""
        self._seed_stock(20)
        self._add_allergy(
            self.patient_with_allergy, "Paracetamol", severity="severe"
        )
        prescription = self._new_prescription(patient_visit=self.visit_allergy)
        line = prescription.line_ids[0]
        with self.assertRaises(UserError):
            line.dispense(qty=5, override_allergy=False)

    def test_allergy_conflict_blocked_even_with_plenty_of_stock(self):
        """Stock is not checked before the allergy gate -- allergy blocks
        first, regardless of stock level."""
        self._seed_stock(100)
        self._add_allergy(self.patient_with_allergy, "paracetamol")
        prescription = self._new_prescription(patient_visit=self.visit_allergy)
        line = prescription.line_ids[0]
        with self.assertRaises(UserError):
            line.dispense()

    def test_allergy_override_with_reason_succeeds(self):
        """override_allergy=True + non-empty override_reason bypasses the
        allergy block and completes the dispense."""
        self._seed_stock(15)
        self._add_allergy(self.patient_with_allergy, "Test Paracetamol")
        prescription = self._new_prescription(
            patient_visit=self.visit_allergy, qty_prescribed=5
        )
        line = prescription.line_ids[0]
        line.dispense(
            qty=5,
            override_allergy=True,
            override_reason="Doctor confirmed: benefit > risk for this case.",
        )
        self.assertEqual(line.state, "dispensed")
        self.assertIsNotNone(line.override_reason)
        self.assertIn("Doctor confirmed", line.override_reason)

    def test_allergy_override_without_reason_raises(self):
        """override_allergy=True with no/empty reason must raise UserError."""
        self._seed_stock(15)
        self._add_allergy(self.patient_with_allergy, "Test Paracetamol")
        prescription = self._new_prescription(
            patient_visit=self.visit_allergy, qty_prescribed=5
        )
        line = prescription.line_ids[0]
        with self.assertRaises(UserError):
            line.dispense(qty=5, override_allergy=True, override_reason="")

    def test_allergy_override_is_audit_logged(self):
        """After an override dispense, hospital.audit.log contains a row
        with action='write' and the allergy_override event marker."""
        self._seed_stock(15)
        self._add_allergy(self.patient_with_allergy, "Test Paracetamol")
        prescription = self._new_prescription(
            patient_visit=self.visit_allergy, qty_prescribed=3
        )
        line = prescription.line_ids[0]
        reason = "Test override reason"
        line.dispense(
            qty=3,
            override_allergy=True,
            override_reason=reason,
        )
        logs = self.env["hospital.audit.log"].search(
            [
                ("res_model", "=", "hospital.prescription.line"),
                ("res_id", "=", line.id),
                ("action", "=", "write"),
            ]
        )
        # At least one log entry should contain the allergy_override event
        override_logs = logs.filtered(
            lambda l: "allergy_override" in (l.field_changes or "")
        )
        self.assertTrue(
            override_logs,
            "Expected an audit log row for the allergy override, found none.",
        )

    def test_no_allergy_no_block(self):
        """When the patient has no allergies the dispense proceeds normally."""
        self._seed_stock(10)
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        line.dispense(qty=5)
        self.assertEqual(line.state, "dispensed")

    def test_allergy_for_different_medicine_does_not_block(self):
        """An allergy that does not match the dispensed medicine should not
        block."""
        self._seed_stock(10)
        self._add_allergy(
            self.patient_with_allergy, "Penicillin", severity="severe"
        )
        prescription = self._new_prescription(patient_visit=self.visit_allergy)
        line = prescription.line_ids[0]
        line.dispense(qty=5)
        self.assertEqual(line.state, "partial" if line.qty_on_hand_at_pharmacy < line.qty_prescribed else "dispensed")

    # -------------------------------------------------------------------------
    # Full dispense / stock decrement
    # -------------------------------------------------------------------------

    def test_full_dispense_sets_state_dispensed(self):
        """With sufficient stock, dispensing the full qty_prescribed sets
        line.state = dispensed."""
        self._seed_stock(20)
        prescription = self._new_prescription(qty_prescribed=10)
        line = prescription.line_ids[0]
        line.dispense(qty=10)
        self.assertEqual(line.state, "dispensed")
        self.assertEqual(line.qty_dispensed, 10.0)

    def test_full_dispense_creates_stock_move(self):
        """A successful dispense creates a stock.move in state=done."""
        self._seed_stock(20)
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        line.dispense(qty=5)
        self.assertIsNotNone(line.stock_move_id)
        self.assertEqual(line.stock_move_id.state, "done")

    def test_full_dispense_decrements_stock(self):
        """After a full dispense the on-hand quantity at the pharmacy
        location is reduced by the dispensed qty."""
        initial_qty = 20.0
        self._seed_stock(initial_qty)
        qty_to_dispense = 7.0
        prescription = self._new_prescription(qty_prescribed=qty_to_dispense)
        line = prescription.line_ids[0]
        line.dispense(qty=qty_to_dispense)
        remaining = line.medicine_id.with_context(
            location=self.pharmacy_location.id
        ).qty_available
        self.assertAlmostEqual(
            remaining,
            initial_qty - qty_to_dispense,
            places=2,
            msg="Stock should decrease by the dispensed quantity.",
        )

    def test_full_dispense_updates_prescription_state_to_dispensed(self):
        """When all non-cancelled lines are dispensed the prescription's
        own state flips to dispensed."""
        self._seed_stock(20)
        prescription = self._new_prescription(qty_prescribed=10)
        line = prescription.line_ids[0]
        line.dispense(qty=10)
        self.assertEqual(prescription.state, "dispensed")

    # -------------------------------------------------------------------------
    # Partial dispense (insufficient stock)
    # -------------------------------------------------------------------------

    def test_partial_dispense_when_stock_insufficient(self):
        """With less stock than prescribed, dispensing the full prescribed
        qty only moves the available quantity; line.state = partial."""
        self._seed_stock(3)
        prescription = self._new_prescription(qty_prescribed=10)
        line = prescription.line_ids[0]
        line.dispense(qty=10)
        self.assertEqual(line.state, "partial")
        self.assertEqual(line.qty_dispensed, 3.0)

    def test_partial_dispense_prescription_state_is_partially_dispensed(self):
        """Prescription with a partially-dispensed line gets state =
        partially_dispensed."""
        self._seed_stock(3)
        prescription = self._new_prescription(qty_prescribed=10)
        line = prescription.line_ids[0]
        line.dispense(qty=10)
        self.assertEqual(prescription.state, "partially_dispensed")

    def test_backordered_when_zero_stock(self):
        """When no stock is available at all, line.state = backordered
        and qty_dispensed stays at 0."""
        self._seed_stock(0)
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        line.dispense(qty=5)
        self.assertEqual(line.state, "backordered")
        self.assertEqual(line.qty_dispensed, 0.0)

    def test_partial_dispense_accumulates(self):
        """Calling dispense twice (once with partial stock, once after
        restocking) correctly accumulates qty_dispensed."""
        self._seed_stock(3)
        prescription = self._new_prescription(qty_prescribed=10)
        line = prescription.line_ids[0]
        line.dispense(qty=10)  # partial: 3 dispensed
        self.assertEqual(line.qty_dispensed, 3.0)
        # Restock and dispense remaining 7
        self._seed_stock(7)
        line.dispense(qty=7)  # remaining 7 dispensed
        self.assertEqual(line.qty_dispensed, 10.0)
        self.assertEqual(line.state, "dispensed")

    # -------------------------------------------------------------------------
    # Prescription aggregate state (multi-line)
    # -------------------------------------------------------------------------

    def test_prescription_stays_partially_dispensed_with_mixed_lines(self):
        """A prescription with one dispensed line and one pending line
        is partially_dispensed, not dispensed."""
        self._seed_stock(50)
        prescription = self.Prescription.create(
            {
                "visit_id": self.visit.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {"medicine_id": self.medicine.id, "qty_prescribed": 5}),
                    (0, 0, {"medicine_id": self.medicine.id, "qty_prescribed": 5}),
                ],
            }
        )
        lines = prescription.line_ids
        lines[0].dispense(qty=5)  # fully dispense first line
        # Second line still pending
        self.assertEqual(prescription.state, "partially_dispensed")

    def test_prescription_dispensed_when_all_lines_done(self):
        """All non-cancelled lines dispensed -> prescription.state =
        dispensed."""
        self._seed_stock(50)
        prescription = self.Prescription.create(
            {
                "visit_id": self.visit.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {"medicine_id": self.medicine.id, "qty_prescribed": 5}),
                    (0, 0, {"medicine_id": self.medicine.id, "qty_prescribed": 5}),
                ],
            }
        )
        for line in prescription.line_ids:
            line.dispense(qty=5)
        self.assertEqual(prescription.state, "dispensed")

    def test_cancelled_lines_excluded_from_aggregate(self):
        """A cancelled line does not prevent a prescription from reaching
        dispensed when the remaining line is dispensed."""
        self._seed_stock(50)
        prescription = self.Prescription.create(
            {
                "visit_id": self.visit.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {"medicine_id": self.medicine.id, "qty_prescribed": 5}),
                    (0, 0, {"medicine_id": self.medicine.id, "qty_prescribed": 5}),
                ],
            }
        )
        lines = prescription.line_ids
        lines[0].write({"state": "cancelled"})
        lines[1].dispense(qty=5)
        self.assertEqual(prescription.state, "dispensed")

    # -------------------------------------------------------------------------
    # Guard tests
    # -------------------------------------------------------------------------

    def test_dispense_already_dispensed_line_raises(self):
        """Calling dispense() on a fully-dispensed line raises UserError."""
        self._seed_stock(20)
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        line.dispense(qty=5)
        with self.assertRaises(UserError):
            line.dispense(qty=1)

    def test_dispense_cancelled_line_raises(self):
        """Calling dispense() on a cancelled line raises UserError."""
        prescription = self._new_prescription(qty_prescribed=5)
        line = prescription.line_ids[0]
        line.write({"state": "cancelled"})
        with self.assertRaises(UserError):
            line.dispense(qty=1)
