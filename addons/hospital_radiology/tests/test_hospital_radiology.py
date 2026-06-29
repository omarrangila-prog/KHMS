# -*- coding: utf-8 -*-
"""Tests for hospital_radiology module.

Covers (per Phase 6 §8 spec):
1. Order state transitions (ordered -> scheduled -> in_progress -> completed).
2. Doctor notification on completion (mail.activity created).
3. Cancel wizard requires reason (wizard validates; direct call also works with reason).
4. Visit branch-completion integration test (radiology order completed ->
   "radiology" removed from pending branches).
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHospitalRadiology(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.dept = cls.env["hospital.department"].create({
            "name": "Test Radiology Department",
            "code": "TRAD",
        })
        cls.doctor_user = cls.env["res.users"].create({
            "name": "Test Radiology Doctor",
            "login": "test_radiology_doctor@hospital-test.local",
            "email": "test_radiology_doctor@hospital-test.local",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.doctor = cls.env["hospital.doctor"].create({
            "user_id": cls.doctor_user.id,
            "department_id": cls.dept.id,
            "specialization": "Radiology",
            "license_number": "TEST-RAD-001",
        })
        cls.patient = cls.env["hospital.patient"].create({
            "name": "Test Patient Radiology",
            "date_of_birth": "1985-06-15",
            "gender": "female",
            "phone": "+2540000000088",
            "identity_type": "national_id",
            "identity_number": "TEST-RAD-PAT-001",
        })
        cls.visit = cls.env["hospital.visit"].create({
            "patient_id": cls.patient.id,
            "doctor_id": cls.doctor.id,
            "department_id": cls.dept.id,
            "visit_type": "opd",
        })
        cls.study = cls.env["hospital.radiology.study"].create({
            "name": "Test Chest X-Ray",
            "code": "TEST-CXR-001",
            "modality": "xray",
            "price": 25.0,
        })

    def _make_order(self, state="ordered", priority="normal"):
        """Helper: create a radiology order and advance to the requested state."""
        order = self.env["hospital.radiology.order"].create({
            "visit_id": self.visit.id,
            "doctor_id": self.doctor.id,
            "study_id": self.study.id,
            "priority": priority,
        })
        self.assertEqual(order.state, "ordered")
        if state in ("scheduled", "in_progress", "completed"):
            order.action_schedule()
            self.assertEqual(order.state, "scheduled")
        if state in ("in_progress", "completed"):
            order.action_start()
            self.assertEqual(order.state, "in_progress")
        if state == "completed":
            order.action_complete()
            self.assertEqual(order.state, "completed")
        return order

    # ------------------------------------------------------------------
    # 1. Order state transitions
    # ------------------------------------------------------------------

    def test_state_transition_full_path(self):
        """ordered -> scheduled -> in_progress -> completed."""
        order = self._make_order(state="completed")
        self.assertEqual(order.state, "completed")

    def test_cannot_start_from_ordered(self):
        """action_start raises UserError if not in 'scheduled' state."""
        from odoo.exceptions import UserError
        order = self._make_order(state="ordered")
        with self.assertRaises(UserError):
            order.action_start()

    def test_cannot_complete_from_scheduled(self):
        """action_complete raises UserError if not in 'in_progress' state."""
        from odoo.exceptions import UserError
        order = self._make_order(state="scheduled")
        with self.assertRaises(UserError):
            order.action_complete()

    def test_cannot_schedule_from_in_progress(self):
        """action_schedule raises UserError if not in 'ordered' state."""
        from odoo.exceptions import UserError
        order = self._make_order(state="in_progress")
        with self.assertRaises(UserError):
            order.action_schedule()

    def test_performed_by_set_on_start(self):
        """action_start sets performed_by to current user and performed_at."""
        order = self._make_order(state="in_progress")
        self.assertTrue(order.performed_by, "performed_by should be set after action_start.")
        self.assertTrue(order.performed_at, "performed_at should be set after action_start.")

    # ------------------------------------------------------------------
    # 2. Doctor notification on completion
    # ------------------------------------------------------------------

    def test_doctor_notification_on_completion(self):
        """action_complete creates a mail.activity for the ordering doctor."""
        order = self._make_order(state="in_progress")
        activities_before = self.env["mail.activity"].search([
            ("res_model", "=", "hospital.radiology.order"),
            ("res_id", "=", order.id),
        ])
        count_before = len(activities_before)
        order.action_complete()
        activities_after = self.env["mail.activity"].search([
            ("res_model", "=", "hospital.radiology.order"),
            ("res_id", "=", order.id),
        ])
        self.assertGreater(
            len(activities_after), count_before,
            "action_complete should create a mail.activity.",
        )
        new_activities = activities_after - activities_before
        doctor_activities = new_activities.filtered(
            lambda a: a.user_id == self.doctor_user
        )
        self.assertTrue(
            doctor_activities,
            "The created mail.activity should be for the ordering doctor's user.",
        )

    # ------------------------------------------------------------------
    # 3. Cancel wizard requires reason
    # ------------------------------------------------------------------

    def test_cancel_with_reason(self):
        """action_cancel with reason cancels the order successfully."""
        order = self._make_order(state="ordered")
        order.action_cancel(reason="Equipment maintenance, will reschedule.")
        self.assertEqual(order.state, "cancelled")
        self.assertEqual(order.cancel_reason, "Equipment maintenance, will reschedule.")

    def test_cannot_cancel_completed_order(self):
        """action_cancel raises UserError for a completed order."""
        from odoo.exceptions import UserError
        order = self._make_order(state="completed")
        with self.assertRaises(UserError):
            order.action_cancel(reason="Trying to cancel a completed order.")

    def test_cancel_wizard_requires_reason(self):
        """Cancel wizard raises UserError if reason is empty."""
        from odoo.exceptions import UserError
        order = self._make_order(state="ordered")
        wizard = self.env["hospital.radiology.order.cancel.wizard"].create({
            "order_id": order.id,
            "reason": "",
        })
        with self.assertRaises(UserError):
            wizard.action_confirm_cancel()

    # ------------------------------------------------------------------
    # 4. Visit branch-completion integration
    # ------------------------------------------------------------------

    def test_pending_branches_radiology_order_open(self):
        """With an open radiology order, 'radiology' appears in pending branches."""
        order = self._make_order(state="ordered")
        pending = self.visit._compute_pending_branches()
        self.assertIn(
            "radiology", pending.get(self.visit.id, []),
            "Open radiology order should add 'radiology' to pending branches.",
        )
        order.action_cancel(reason="Test cleanup")

    def test_pending_branches_radiology_order_completed(self):
        """After completing the radiology order, 'radiology' is removed from pending."""
        order = self._make_order(state="completed")
        pending = self.visit._compute_pending_branches()
        self.assertNotIn(
            "radiology", pending.get(self.visit.id, []),
            "Completed radiology order should remove 'radiology' from pending.",
        )

    def test_pending_branches_radiology_order_cancelled(self):
        """A cancelled radiology order is treated as resolved (not pending)."""
        order = self._make_order(state="ordered")
        order.action_cancel(reason="Test: cancelled before scheduling.")
        pending = self.visit._compute_pending_branches()
        self.assertNotIn(
            "radiology", pending.get(self.visit.id, []),
            "Cancelled radiology order should not keep 'radiology' in pending branches.",
        )
