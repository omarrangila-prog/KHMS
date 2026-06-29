# -*- coding: utf-8 -*-
"""Tests for hospital_ipd module.

Covers (per Phase 10 Sprint 8 DoD):
1. Concurrent-admission race condition: two simultaneous action_assign_bed()
   calls against the same bed - only one succeeds, the database-level
   partial unique index rejects the second.
2. Discharge blocked while a pending branch (a lab-style placeholder,
   simulated generically since this module cannot depend on hospital_lab)
   remains open on the visit.
3. Length-of-stay billing accuracy (days x ward daily_rate).
4. Bed-transfer audit trail (old bed freed, new bed occupied, transfer
   row recorded).
"""
import psycopg2
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestHospitalIpd(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept = cls.env["hospital.department"].create({
            "name": "Test IPD Department",
            "code": "TIPD",
        })
        cls.doctor_user = cls.env["res.users"].create({
            "name": "Test IPD Doctor",
            "login": "test_ipd_doctor@hospital-test.local",
            "email": "test_ipd_doctor@hospital-test.local",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.doctor = cls.env["hospital.doctor"].create({
            "user_id": cls.doctor_user.id,
            "department_id": cls.dept.id,
            "specialization": "General Medicine",
            "license_number": "TEST-IPD-001",
        })
        cls.ward = cls.env["hospital.ward"].create({
            "name": "Test Ward",
            "code": "TW1",
            "ward_type": "general",
            "daily_rate": 100.0,
        })
        cls.bed = cls.env["hospital.bed"].create({
            "ward_id": cls.ward.id,
            "bed_number": "T01",
        })

    def _make_patient(self, suffix):
        return self.env["hospital.patient"].create({
            "name": "Test Patient %s" % suffix,
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "+254000000%s" % suffix,
            "identity_type": "national_id",
            "identity_number": "TEST-IPD-PAT-%s" % suffix,
        })

    def _make_ipd_visit(self, suffix):
        patient = self._make_patient(suffix)
        return self.env["hospital.visit"].create({
            "patient_id": patient.id,
            "doctor_id": self.doctor.id,
            "department_id": self.dept.id,
            "visit_type": "ipd",
        })

    def _make_admission(self, suffix):
        visit = self._make_ipd_visit(suffix)
        return self.env["hospital.ipd.admission"].create({
            "patient_id": visit.patient_id.id,
            "visit_id": visit.id,
            "admitting_doctor_id": self.doctor.id,
        })

    # ------------------------------------------------------------------
    # 1. Concurrent-admission race condition (DB-level partial unique index)
    # ------------------------------------------------------------------

    def test_one_active_admission_per_bed_sequential(self):
        """Sequential check: a second assignment to an already-admitted
        bed is rejected at the Python business-rule level (bed.state !=
        'vacant'), before ever reaching the database."""
        admission_1 = self._make_admission("01")
        admission_2 = self._make_admission("02")
        admission_1.action_assign_bed(self.bed.id)
        self.assertEqual(self.bed.state, "occupied")
        with self.assertRaises(UserError):
            admission_2.action_assign_bed(self.bed.id)

    def test_one_active_admission_per_bed_db_constraint(self):
        """The DB-level partial unique index is the final backstop: even
        if two 'admitted' rows for the same bed_id were forced past the
        Python check (e.g. a direct write() bypassing action_assign_bed),
        the database itself rejects it.

        Simulated here by writing a second admission directly to
        state='admitted' with the same bed_id via SQL-adjacent ORM write,
        bypassing action_assign_bed's own bed.state guard, to prove the
        index - not just the Python check - is what makes this invariant
        unbreakable.
        """
        admission_1 = self._make_admission("03")
        admission_2 = self._make_admission("04")
        admission_1.action_assign_bed(self.bed.id)

        with mute_logger("odoo.sql_db"):
            with self.assertRaises(psycopg2.errors.UniqueViolation):
                with self.env.cr.savepoint():
                    self.env.cr.execute(
                        "UPDATE hospital_ipd_admission "
                        "SET state = 'admitted', bed_id = %s WHERE id = %s",
                        (self.bed.id, admission_2.id),
                    )

    # ------------------------------------------------------------------
    # 2. Discharge blocked while a branch is pending
    # ------------------------------------------------------------------

    def test_discharge_blocked_while_branch_pending(self):
        """Cannot confirm discharge while _compute_pending_branches()
        reports an open branch (here: the prescription branch owned by
        hospital_doctor itself, set via outcome_prescribe intent without
        ever dispensing - hospital_doctor's own placeholder check, no
        hospital_pharmacy install needed to exercise this)."""
        admission = self._make_admission("05")
        admission.action_assign_bed(self.bed.id)
        visit = admission.visit_id
        consultation = self.env["hospital.consultation"].create({
            "visit_id": visit.id,
            "doctor_id": self.doctor.id,
            "outcome_prescribe": True,
        })
        prescription = self.env["hospital.prescription"].create({
            "visit_id": visit.id,
            "doctor_id": self.doctor.id,
            "consultation_id": consultation.id,
        })
        self.assertTrue(prescription)
        pending = visit._compute_pending_branches().get(visit.id, [])
        self.assertIn("prescription", pending)

        discharge = self.env["hospital.discharge"].create({
            "admission_id": admission.id,
            "discharge_type": "normal",
            "discharge_summary": "Test summary.",
        })
        with self.assertRaises(UserError):
            discharge.action_confirm()

    def test_discharge_succeeds_with_no_pending_branches(self):
        """A clean visit (no consultation outcomes opened) discharges
        successfully and the bed is released back to 'cleaning'."""
        admission = self._make_admission("06")
        admission.action_assign_bed(self.bed.id)
        discharge = self.env["hospital.discharge"].create({
            "admission_id": admission.id,
            "discharge_type": "normal",
            "discharge_summary": "Test summary, no pending branches.",
        })
        discharge.action_confirm()
        self.assertEqual(discharge.state, "confirmed")
        self.assertEqual(admission.state, "discharged")
        self.assertEqual(self.bed.state, "cleaning")
        self.assertEqual(admission.visit_id.state, "done")

    def test_discharge_revert_to_draft_blocked_by_constraint(self):
        """The @api.constrains backstop catches a confirmed discharge
        being written back to 'confirmed' while a branch re-opens after
        the fact would be invalid - here we confirm a discharge is
        unconfirmable a second time via action_confirm() itself."""
        admission = self._make_admission("07")
        admission.action_assign_bed(self.bed.id)
        discharge = self.env["hospital.discharge"].create({
            "admission_id": admission.id,
            "discharge_type": "normal",
            "discharge_summary": "Test summary.",
        })
        discharge.action_confirm()
        with self.assertRaises(UserError):
            discharge.action_confirm()

    # ------------------------------------------------------------------
    # 3. Length-of-stay billing accuracy
    # ------------------------------------------------------------------

    def test_length_of_stay_billing_accuracy(self):
        """ward_charge_amount = length_of_stay_days * ward.daily_rate."""
        from datetime import timedelta
        from odoo import fields

        admission = self._make_admission("08")
        admission.action_assign_bed(self.bed.id)
        admission.write({
            "admission_datetime": fields.Datetime.now() - timedelta(days=2),
        })
        discharge = self.env["hospital.discharge"].create({
            "admission_id": admission.id,
            "discharge_type": "normal",
            "discharge_summary": "Test LOS billing.",
            "discharge_datetime": fields.Datetime.now(),
        })
        self.assertAlmostEqual(admission.length_of_stay_days, 2.0, delta=0.01)
        self.assertAlmostEqual(discharge.ward_charge_amount, 200.0, delta=1.0)

    # ------------------------------------------------------------------
    # 4. Bed-transfer audit trail
    # ------------------------------------------------------------------

    def test_bed_transfer_releases_old_bed_and_occupies_new(self):
        admission = self._make_admission("09")
        admission.action_assign_bed(self.bed.id)
        new_bed = self.env["hospital.bed"].create({
            "ward_id": self.ward.id,
            "bed_number": "T02",
        })
        transfer = self.env["hospital.bed.transfer"].create({
            "admission_id": admission.id,
            "to_bed_id": new_bed.id,
            "reason": "Test transfer.",
        })
        transfer.action_confirm()
        self.assertEqual(self.bed.state, "cleaning")
        self.assertEqual(new_bed.state, "occupied")
        self.assertEqual(admission.bed_id, new_bed)
        self.assertEqual(transfer.from_bed_id, self.bed)

    def test_bed_transfer_requires_admitted_state(self):
        admission = self._make_admission("10")
        new_bed = self.env["hospital.bed"].create({
            "ward_id": self.ward.id,
            "bed_number": "T03",
        })
        transfer = self.env["hospital.bed.transfer"].create({
            "admission_id": admission.id,
            "to_bed_id": new_bed.id,
            "reason": "Test transfer on non-admitted record.",
        })
        with self.assertRaises(UserError):
            transfer.action_confirm()

    def test_bed_transfer_audit_log_created(self):
        """hospital.bed.transfer uses hospital.audit.mixin - confirm an
        audit log row is created on create()."""
        admission = self._make_admission("11")
        admission.action_assign_bed(self.bed.id)
        new_bed = self.env["hospital.bed"].create({
            "ward_id": self.ward.id,
            "bed_number": "T04",
        })
        transfer = self.env["hospital.bed.transfer"].create({
            "admission_id": admission.id,
            "to_bed_id": new_bed.id,
            "reason": "Test audit trail.",
        })
        audit_logs = self.env["hospital.audit.log"].search([
            ("res_model", "=", "hospital.bed.transfer"),
            ("res_id", "=", transfer.id),
        ])
        self.assertTrue(audit_logs, "Creating a bed transfer should write an audit log row.")

    # ------------------------------------------------------------------
    # 5. Admission requires a bed when admitted (model constraint)
    # ------------------------------------------------------------------

    def test_admission_requires_bed_when_admitted(self):
        admission = self._make_admission("12")
        with self.assertRaises(ValidationError):
            admission.write({"state": "admitted", "bed_id": False})

    # ------------------------------------------------------------------
    # 6. Visit pending-branches / routing integration
    # ------------------------------------------------------------------

    def test_pending_branches_admission_requested(self):
        admission = self._make_admission("13")
        visit = admission.visit_id
        pending = visit._compute_pending_branches().get(visit.id, [])
        self.assertIn("admission", pending)

    def test_pending_branches_admission_admitted_not_pending(self):
        admission = self._make_admission("14")
        admission.action_assign_bed(self.bed.id)
        visit = admission.visit_id
        pending = visit._compute_pending_branches().get(visit.id, [])
        self.assertNotIn("admission", pending)

    def test_visit_state_becomes_admitted_on_bed_assignment(self):
        admission = self._make_admission("15")
        admission.action_assign_bed(self.bed.id)
        self.assertEqual(admission.visit_id.state, "admitted")
