# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestLowStock(TransactionCase):
    """hospital.inventory.dashboard SQL view low-stock flagging and the
    LowStockAlertService cron (Phase 6 §6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Quant = cls.env["stock.quant"]
        cls.Dashboard = cls.env["hospital.inventory.dashboard"]
        cls.warehouse = cls.env.ref("hospital_inventory.stock_warehouse_pharmacy")
        cls.location = cls.env.ref("hospital_inventory.stock_location_pharmacy_store")

    def _make_medicine(self, name, threshold, qty):
        medicine = self.Product.create({
            "name": name,
            "is_hospital_medicine": True,
            "type": "consu",
            "is_storable": True,
            "reorder_threshold": threshold,
        })
        if qty:
            self.Quant.create({
                "product_id": medicine.id,
                "location_id": self.location.id,
                "inventory_quantity": qty,
            })
        return medicine

    def _dashboard_row(self, medicine):
        self.Dashboard.invalidate_model()
        return self.Dashboard.search([("product_id", "=", medicine.id)], limit=1)

    def test_low_stock_flagged_when_at_or_below_threshold(self):
        medicine = self._make_medicine("Test Low Stock Medicine", 20.0, 5.0)
        row = self._dashboard_row(medicine)
        self.assertTrue(row)
        self.assertTrue(row.is_low_stock)
        self.assertEqual(row.qty_available, 5.0)

    def test_healthy_stock_not_flagged(self):
        medicine = self._make_medicine("Test Healthy Stock Medicine", 10.0, 100.0)
        row = self._dashboard_row(medicine)
        self.assertTrue(row)
        self.assertFalse(row.is_low_stock)

    def test_zero_stock_is_low_stock(self):
        medicine = self._make_medicine("Test Zero Stock Medicine", 5.0, 0.0)
        row = self._dashboard_row(medicine)
        self.assertTrue(row)
        self.assertTrue(row.is_low_stock)
        self.assertEqual(row.qty_available, 0.0)

    def test_exactly_at_threshold_is_low_stock(self):
        medicine = self._make_medicine("Test Threshold Medicine", 10.0, 10.0)
        row = self._dashboard_row(medicine)
        self.assertTrue(row)
        self.assertTrue(row.is_low_stock)

    def test_non_medicine_product_excluded_from_dashboard(self):
        product = self.Product.create({"name": "Test Non Medicine Product"})
        row = self.Dashboard.search([("product_id", "=", product.id)], limit=1)
        self.assertFalse(row)

    def test_cron_creates_activity_for_low_stock(self):
        self.env.user.groups_id = [(4, self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager").id)]
        medicine = self._make_medicine("Test Cron Low Stock Medicine", 50.0, 1.0)
        self._dashboard_row(medicine)

        self.env["product.template"]._cron_check_low_stock()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", "product.template"),
            ("res_id", "=", medicine.product_tmpl_id.id),
            ("summary", "=", "Medicine Stock Below Reorder Threshold"),
        ])
        self.assertTrue(activities)

    def test_cron_is_idempotent(self):
        self.env.user.groups_id = [(4, self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager").id)]
        medicine = self._make_medicine("Test Cron Idempotent Medicine", 50.0, 1.0)
        self._dashboard_row(medicine)

        self.env["product.template"]._cron_check_low_stock()
        self.env["product.template"]._cron_check_low_stock()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", "product.template"),
            ("res_id", "=", medicine.product_tmpl_id.id),
            ("summary", "=", "Medicine Stock Below Reorder Threshold"),
        ])
        self.assertEqual(len(activities), 1)
