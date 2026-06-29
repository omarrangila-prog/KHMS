# -*- coding: utf-8 -*-
"""Tests for hospital_security module.

Key invariants verified:
1. No group — including Hospital Administrator — can unlink audit log rows.
2. Audit log rows ARE created by the mixin on create/write of tracked models.
3. Multi-company isolation: a user scoped to company A cannot read company B records.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged("post_install", "-at_install")
class TestHospitalAuditLogImmutability(TransactionCase):
    """Verify append-only guarantee on hospital.audit.log."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = cls.env.ref("base.user_admin")

    def _make_audit_row(self):
        return self.env["hospital.audit.log"].create({
            "res_model": "hospital.patient",
            "res_id": 1,
            "user_id": self.admin_user.id,
            "action": "create",
        })

    def test_admin_cannot_unlink_audit_log(self):
        """Hospital Administrator must be blocked from deleting audit rows."""
        row = self._make_audit_row()
        # The ir.model.access.csv in hospital_base grants perm_unlink=0 for
        # the admin group on hospital.audit.log. Attempting unlink must raise.
        with self.assertRaises((AccessError, Exception)):
            row.with_user(self.admin_user).unlink()

    def test_hospital_user_cannot_unlink_audit_log(self):
        """Regular hospital users have no unlink right on audit logs."""
        row = self._make_audit_row()
        user = new_test_user(
            self.env,
            login="test_sec_user@hospital-test.local",
            groups="hospital_base.group_hospital_user",
        )
        with self.assertRaises(AccessError):
            row.with_user(user).unlink()

    def test_hospital_user_cannot_write_audit_log(self):
        """Audit log rows must be read-only even to admin."""
        row = self._make_audit_row()
        user = new_test_user(
            self.env,
            login="test_sec_user2@hospital-test.local",
            groups="hospital_base.group_hospital_user",
        )
        with self.assertRaises(AccessError):
            row.with_user(user).write({"action": "write"})

    def test_audit_log_created_on_patient_create(self):
        """Creating a hospital.patient must produce at least one audit row via the mixin."""
        before = self.env["hospital.audit.log"].search_count([
            ("res_model", "=", "hospital.patient"),
            ("action", "=", "create"),
        ])
        self.env["hospital.patient"].create({
            "name": "Security Test Patient",
            "date_of_birth": "1990-01-01",
            "gender": "female",
            "phone": "+254900000001",
            "identity_type": "national_id",
            "identity_number": "SEC-TEST-001",
        })
        after = self.env["hospital.audit.log"].search_count([
            ("res_model", "=", "hospital.patient"),
            ("action", "=", "create"),
        ])
        self.assertGreater(after, before, "Audit row must be created on patient.create()")

    def test_audit_log_created_on_patient_write(self):
        """Writing a tracked field on hospital.patient must produce an audit row."""
        patient = self.env["hospital.patient"].create({
            "name": "Security Test Patient Write",
            "date_of_birth": "1985-05-05",
            "gender": "male",
            "phone": "+254900000002",
            "identity_type": "national_id",
            "identity_number": "SEC-TEST-002",
        })
        before = self.env["hospital.audit.log"].search_count([
            ("res_model", "=", "hospital.patient"),
            ("res_id", "=", patient.id),
            ("action", "=", "write"),
        ])
        patient.write({"name": "Security Test Patient Write (updated)"})
        after = self.env["hospital.audit.log"].search_count([
            ("res_model", "=", "hospital.patient"),
            ("res_id", "=", patient.id),
            ("action", "=", "write"),
        ])
        self.assertGreater(after, before, "Audit row must be created on patient.write()")


@tagged("post_install", "-at_install")
class TestMultiCompanyIsolation(TransactionCase):
    """Verify cross-module company isolation rules added by hospital_security."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Hospital Security Test Co B"})

        cls.user_a = new_test_user(
            cls.env,
            login="test_sec_company_a@hospital-test.local",
            groups="hospital_base.group_hospital_user",
            company_id=cls.company_a.id,
            company_ids=[(6, 0, [cls.company_a.id])],
        )

    def test_user_a_cannot_read_company_b_patient(self):
        """A user scoped to company A must not be able to read company B patients."""
        patient_b = self.env["hospital.patient"].with_company(self.company_b).create({
            "name": "Company B Patient",
            "date_of_birth": "1975-03-15",
            "gender": "male",
            "phone": "+254900000099",
            "identity_type": "national_id",
            "identity_number": "SEC-CO-B-001",
            "company_id": self.company_b.id,
        })
        visible = self.env["hospital.patient"].with_user(self.user_a).search([
            ("id", "=", patient_b.id),
        ])
        self.assertFalse(
            visible,
            "Company A user must not see company B patient records.",
        )

    def test_user_a_cannot_read_company_b_appointment(self):
        """A user scoped to company A must not see company B appointments."""
        dept = self.env["hospital.department"].with_company(self.company_b).create({
            "name": "Sec Test Dept B",
            "code": "STDB",
            "company_id": self.company_b.id,
        })
        patient_b = self.env["hospital.patient"].with_company(self.company_b).create({
            "name": "Company B Patient 2",
            "date_of_birth": "1980-07-20",
            "gender": "female",
            "phone": "+254900000098",
            "identity_type": "national_id",
            "identity_number": "SEC-CO-B-002",
            "company_id": self.company_b.id,
        })
        appt = self.env["hospital.appointment"].with_company(self.company_b).create({
            "patient_id": patient_b.id,
            "department_id": dept.id,
            "appointment_date": "2025-12-01 09:00:00",
            "company_id": self.company_b.id,
        })
        visible = self.env["hospital.appointment"].with_user(self.user_a).search([
            ("id", "=", appt.id),
        ])
        self.assertFalse(
            visible,
            "Company A user must not see company B appointment records.",
        )
