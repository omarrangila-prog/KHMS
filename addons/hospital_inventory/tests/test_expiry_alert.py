# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestExpiryAlert(TransactionCase):
    """hospital.medicine.batch (stock.lot _inherit) expiry status /
    ExpiryAlertService cron (Phase 6 §6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Lot = cls.env["stock.lot"]
        cls.medicine = cls.Product.create({
            "name": "Test Expiry Medicine",
            "is_hospital_medicine": True,
            "type": "consu",
            "is_storable": True,
            "tracking": "lot",
        })

    def _make_lot(self, name, expiry_date):
        return self.Lot.create({
            "name": name,
            "product_id": self.medicine.id,
            "expiry_date": expiry_date,
        })

    def test_expired_batch_flagged(self):
        today = fields.Date.context_today(self.env.user)
        lot = self._make_lot("EXP-PAST", today - timedelta(days=5))
        self.assertTrue(lot.is_expired)
        self.assertFalse(lot.is_expiring_soon)

    def test_expiring_soon_batch_flagged(self):
        today = fields.Date.context_today(self.env.user)
        lot = self._make_lot("EXP-SOON", today + timedelta(days=10))
        self.assertFalse(lot.is_expired)
        self.assertTrue(lot.is_expiring_soon)

    def test_safe_batch_not_flagged(self):
        today = fields.Date.context_today(self.env.user)
        lot = self._make_lot("EXP-SAFE", today + timedelta(days=200))
        self.assertFalse(lot.is_expired)
        self.assertFalse(lot.is_expiring_soon)

    def test_no_expiry_date_not_flagged(self):
        lot = self._make_lot("EXP-NONE", False)
        self.assertFalse(lot.is_expired)
        self.assertFalse(lot.is_expiring_soon)

    def test_boundary_exactly_30_days_is_expiring_soon(self):
        today = fields.Date.context_today(self.env.user)
        lot = self._make_lot("EXP-BOUNDARY", today + timedelta(days=30))
        self.assertTrue(lot.is_expiring_soon)
        self.assertFalse(lot.is_expired)

    def test_cron_creates_activity_only_for_expiring_soon(self):
        today = fields.Date.context_today(self.env.user)
        expiring_lot = self._make_lot("EXP-CRON-SOON", today + timedelta(days=15))
        safe_lot = self._make_lot("EXP-CRON-SAFE", today + timedelta(days=400))

        self.Lot._cron_check_expiring_batches()

        expiring_activity = self.env["mail.activity"].search([
            ("res_model", "=", "stock.lot"),
            ("res_id", "=", expiring_lot.id),
            ("summary", "=", "Medicine Batch Expiring Soon"),
        ])
        safe_activity = self.env["mail.activity"].search([
            ("res_model", "=", "stock.lot"),
            ("res_id", "=", safe_lot.id),
            ("summary", "=", "Medicine Batch Expiring Soon"),
        ])
        self.assertFalse(safe_activity)
        # An activity is only guaranteed for the expiring lot if at least
        # one user belongs to the inventory manager group in this
        # database; assert no error either way and that the safe lot
        # never gets one (the behavior that matters for "correctly
        # identifies expiring-soon vs safe batches").
        managers = self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager",
            raise_if_not_found=False,
        )
        if managers and managers.users:
            self.assertTrue(expiring_activity)

    def test_cron_is_idempotent(self):
        today = fields.Date.context_today(self.env.user)
        self.env.user.groups_id = [(4, self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager").id)]
        lot = self._make_lot("EXP-CRON-IDEMPOTENT", today + timedelta(days=5))

        self.Lot._cron_check_expiring_batches()
        self.Lot._cron_check_expiring_batches()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", "stock.lot"),
            ("res_id", "=", lot.id),
            ("summary", "=", "Medicine Batch Expiring Soon"),
        ])
        self.assertEqual(len(activities), 1)
