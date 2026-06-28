# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHospitalMedicine(TransactionCase):
    """product.template clinical-field extension (Phase 5 §3.3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]

    def test_medicine_fields_save_correctly(self):
        medicine = self.Product.create({
            "name": "Test Paracetamol 500mg",
            "is_hospital_medicine": True,
            "generic_name": "Paracetamol",
            "dosage_form": "tablet",
            "strength": "500mg",
            "requires_prescription": False,
            "controlled_substance": False,
            "reorder_threshold": 25.0,
            "type": "consu",
            "is_storable": True,
        })
        self.assertTrue(medicine.is_hospital_medicine)
        self.assertEqual(medicine.generic_name, "Paracetamol")
        self.assertEqual(medicine.dosage_form, "tablet")
        self.assertEqual(medicine.strength, "500mg")
        self.assertFalse(medicine.requires_prescription)
        self.assertFalse(medicine.controlled_substance)
        self.assertEqual(medicine.reorder_threshold, 25.0)

    def test_requires_prescription_defaults_true(self):
        medicine = self.Product.create({
            "name": "Test Default Medicine",
            "is_hospital_medicine": True,
            "type": "consu",
        })
        self.assertTrue(medicine.requires_prescription)
        self.assertFalse(medicine.controlled_substance)
        self.assertEqual(medicine.reorder_threshold, 0.0)

    def test_non_medicine_product_unaffected(self):
        """Plain (non-medicine) products keep the new fields off/empty by
        default so the clinical extension never leaks into unrelated
        catalog items (e.g. consumables, services)."""
        product = self.Product.create({"name": "Generic Office Supply"})
        self.assertFalse(product.is_hospital_medicine)
        self.assertFalse(product.generic_name)
        self.assertFalse(product.dosage_form)

    def test_dosage_form_selection_values(self):
        for value in (
            "tablet", "capsule", "syrup", "injection",
            "cream", "drops", "inhaler", "other",
        ):
            medicine = self.Product.create({
                "name": f"Test Medicine {value}",
                "is_hospital_medicine": True,
                "dosage_form": value,
                "type": "consu",
            })
            self.assertEqual(medicine.dosage_form, value)
