# -*- coding: utf-8 -*-
"""Tests for hospital_lab module.

Covers (per Phase 6 §7 spec):
1. Abnormal range flagging (numeric value outside normal_range_min/max sets is_abnormal=True).
2. Order state transitions (ordered -> sample_collected -> processing -> completed).
3. Doctor notification on completion (mail.activity created).
4. action_cancel requires reason (wizard guards it; direct call also works with reason).
5. Visit branch-completion integration test (lab order completed -> "lab" removed from pending).
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHospitalLab(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Shared fixtures reused across test methods.
        cls.company = cls.env.company

        # Create a minimal department, doctor user, and doctor.
        cls.dept = cls.env["hospital.department"].create({
            "name": "Test Lab Department",
            "code": "TLAB",
        })
        cls.doctor_user = cls.env["res.users"].create({
            "name": "Test Lab Doctor",
            "login": "test_lab_doctor@hospital-test.local",
            "email": "test_lab_doctor@hospital-test.local",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.doctor = cls.env["hospital.doctor"].create({
            "user_id": cls.doctor_user.id,
            "department_id": cls.dept.id,
            "specialization": "General Medicine",
            "license_number": "TEST-LAB-001",
        })

        # Create a patient and visit.
        cls.patient = cls.env["hospital.patient"].create({
            "name": "Test Patient Lab",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "+2540000000099",
            "identity_type": "national_id",
            "identity_number": "TEST-LAB-PAT-001",
        })
        cls.visit = cls.env["hospital.visit"].create({
            "patient_id": cls.patient.id,
            "doctor_id": cls.doctor.id,
            "department_id": cls.dept.id,
            "visit_type": "opd",
        })

        # Create a lab test with known normal range.
        cls.lab_test = cls.env["hospital.lab.test"].create({
            "name": "Test CBC",
            "code": "TEST-CBC-001",
            "sample_type": "blood",
            "price": 10.0,
            "normal_range_min": 12.0,
            "normal_range_max": 17.5,
        })

    def _make_order(self, state="ordered", priority="normal"):
        """Helper: create a lab order and advance to the requested state."""
        order = self.env["hospital.lab.order"].create({
            "visit_id": self.visit.id,
            "doctor_id": self.doctor.id,
            "test_id": self.lab_test.id,
            "priority": priority,
        })
        self.assertEqual(order.state, "ordered")
        if state in ("sample_collected", "processing", "completed"):
            order.action_collect_sample()
            self.assertEqual(order.state, "sample_collected")
        if state in ("processing", "completed"):
            order.action_processing()
            self.assertEqual(order.state, "processing")
        if state == "completed":
            order.action_complete()
            self.assertEqual(order.state, "completed")
        return order

    # ------------------------------------------------------------------
    # 1. Abnormal range flagging
    # ------------------------------------------------------------------

    def test_is_abnormal_below_min(self):
        """Value below normal_range_min => is_abnormal = True."""
        result = self.env["hospital.lab.result"].create({
            "order_id": self._make_order().id,
            "parameter_name": "Haemoglobin",
            "value": "9.5",
            "unit": "g/dL",
            "normal_range_min": 12.0,
            "normal_range_max": 17.5,
        })
        self.assertTrue(result.is_abnormal, "Value 9.5 below min 12.0 should be abnormal.")

    def test_is_abnormal_above_max(self):
        """Value above normal_range_max => is_abnormal = True."""
        result = self.env["hospital.lab.result"].create({
            "order_id": self._make_order().id,
            "parameter_name": "Haemoglobin",
            "value": "20.0",
            "unit": "g/dL",
            "normal_range_min": 12.0,
            "normal_range_max": 17.5,
        })
        self.assertTrue(result.is_abnormal, "Value 20.0 above max 17.5 should be abnormal.")

    def test_is_normal_within_range(self):
        """Value within normal range => is_abnormal = False."""
        result = self.env["hospital.lab.result"].create({
            "order_id": self._make_order().id,
            "parameter_name": "Haemoglobin",
            "value": "14.0",
            "unit": "g/dL",
            "normal_range_min": 12.0,
            "normal_range_max": 17.5,
        })
        self.assertFalse(result.is_abnormal, "Value 14.0 within range should not be abnormal.")

    def test_is_abnormal_text_value_not_flagged(self):
        """Non-numeric values (e.g. 'Negative') are never flagged abnormal."""
        result = self.env["hospital.lab.result"].create({
            "order_id": self._make_order().id,
            "parameter_name": "Protein",
            "value": "Negative",
            "unit": "",
            "normal_range_min": 0.0,
            "normal_range_max": 0.0,
        })
        self.assertFalse(result.is_abnormal, "Text value should not be flagged abnormal.")

    def test_is_abnormal_no_range_not_flagged(self):
        """When both bounds are 0 (no range set), is_abnormal is False."""
        result = self.env["hospital.lab.result"].create({
            "order_id": self._make_order().id,
            "parameter_name": "Qualitative Result",
            "value": "5.0",
            "unit": "U/L",
            "normal_range_min": 0.0,
            "normal_range_max": 0.0,
        })
        self.assertFalse(result.is_abnormal, "No range set: should not be flagged.")

    # ------------------------------------------------------------------
    # 2. Order state transitions
    # ------------------------------------------------------------------

    def test_state_transition_full_path(self):
        """ordered -> sample_collected -> processing -> completed."""
        order = self._make_order(state="completed")
        self.assertEqual(order.state, "completed")

    def test_cannot_collect_sample_from_processing(self):
        """action_collect_sample raises UserError if not in 'ordered' state."""
        from odoo.exceptions import UserError
        order = self._make_order(state="processing")
        with self.assertRaises(UserError):
            order.action_collect_sample()

    def test_cannot_process_from_ordered(self):
        """action_processing raises UserError if not in 'sample_collected' state."""
        from odoo.exceptions import UserError
        order = self._make_order(state="ordered")
        with self.assertRaises(UserError):
            order.action_processing()

    def test_cannot_complete_from_ordered(self):
        """action_complete raises UserError if not in 'processing' state."""
        from odoo.exceptions import UserError
        order = self._make_order(state="ordered")
        with self.assertRaises(UserError):
            order.action_complete()

    # ------------------------------------------------------------------
    # 3. Doctor notification on completion
    # ------------------------------------------------------------------

    def test_doctor_notification_on_completion(self):
        """action_complete creates a mail.activity for the ordering doctor."""
        order = self._make_order(state="processing")
        activities_before = self.env["mail.activity"].search([
            ("res_model", "=", "hospital.lab.order"),
            ("res_id", "=", order.id),
        ])
        count_before = len(activities_before)
        order.action_complete()
        activities_after = self.env["mail.activity"].search([
            ("res_model", "=", "hospital.lab.order"),
            ("res_id", "=", order.id),
        ])
        self.assertGreater(
            len(activities_after), count_before,
            "action_complete should create a mail.activity for the doctor.",
        )
        # Confirm the activity is assigned to the doctor's user.
        new_activities = activities_after - activities_before
        doctor_activities = new_activities.filtered(
            lambda a: a.user_id == self.doctor_user
        )
        self.assertTrue(
            doctor_activities,
            "The created mail.activity should be for the ordering doctor's user.",
        )

    # ------------------------------------------------------------------
    # 4. Cancel requires reason
    # ------------------------------------------------------------------

    def test_cancel_with_reason(self):
        """action_cancel with a reason cancels the order successfully."""
        order = self._make_order(state="ordered")
        order.action_cancel(reason="Patient refused test.")
        self.assertEqual(order.state, "cancelled")
        self.assertEqual(order.cancel_reason, "Patient refused test.")

    def test_cannot_cancel_completed_order(self):
        """action_cancel raises UserError when order is already completed."""
        from odoo.exceptions import UserError
        order = self._make_order(state="completed")
        with self.assertRaises(UserError):
            order.action_cancel(reason="Trying to cancel a done order.")

    def test_cancel_wizard_requires_reason(self):
        """Cancel wizard raises UserError if reason is empty."""
        from odoo.exceptions import UserError
        order = self._make_order(state="ordered")
        wizard = self.env["hospital.lab.order.cancel.wizard"].create({
            "order_id": order.id,
            "reason": "   ",
        })
        with self.assertRaises(UserError):
            wizard.action_confirm_cancel()

    # ------------------------------------------------------------------
    # 5. Visit branch-completion integration
    # ------------------------------------------------------------------

    def test_pending_branches_lab_order_open(self):
        """With an open lab order, 'lab' appears in the pending branches."""
        order = self._make_order(state="ordered")
        pending = self.visit._compute_pending_branches()
        self.assertIn(
            "lab", pending.get(self.visit.id, []),
            "Open lab order should add 'lab' to pending branches.",
        )
        # Clean up to avoid interference with other tests.
        order.action_cancel(reason="Test cleanup")

    def test_pending_branches_lab_order_completed(self):
        """After completing the lab order, 'lab' is removed from pending."""
        order = self._make_order(state="completed")
        pending = self.visit._compute_pending_branches()
        self.assertNotIn(
            "lab", pending.get(self.visit.id, []),
            "Completed lab order should remove 'lab' from pending branches.",
        )

    def test_pending_branches_lab_order_cancelled(self):
        """A cancelled lab order is treated as resolved (not pending)."""
        order = self._make_order(state="ordered")
        order.action_cancel(reason="Test: cancelled before processing.")
        pending = self.visit._compute_pending_branches()
        self.assertNotIn(
            "lab", pending.get(self.visit.id, []),
            "Cancelled lab order should not keep 'lab' in pending branches.",
        )
