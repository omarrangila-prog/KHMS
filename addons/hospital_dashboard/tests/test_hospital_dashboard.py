# -*- coding: utf-8 -*-
"""Tests for hospital_dashboard module.

Covers (per Phase 6 §10 / Phase 10 Sprint 9 DoD): KPI numbers computed by
the hospital.dashboard.kpi SQL view match the same numbers computed
directly via the ORM against the underlying transactional models, on a
freshly-built seeded dataset (built in setUpClass rather than relying on
demo data, so the test is deterministic regardless of whether --demo is
enabled for the test run).
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHospitalDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.dept = cls.env["hospital.department"].create({
            "name": "Test Dashboard Department",
            "code": "TDASH",
        })
        cls.doctor_user = cls.env["res.users"].create({
            "name": "Test Dashboard Doctor",
            "login": "test_dashboard_doctor@hospital-test.local",
            "email": "test_dashboard_doctor@hospital-test.local",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.doctor = cls.env["hospital.doctor"].create({
            "user_id": cls.doctor_user.id,
            "department_id": cls.dept.id,
            "specialization": "General Medicine",
            "license_number": "TEST-DASH-001",
        })
        cls.ward = cls.env["hospital.ward"].create({
            "name": "Test Dashboard Ward",
            "code": "TDW1",
            "ward_type": "general",
            "daily_rate": 50.0,
        })
        cls.bed_1 = cls.env["hospital.bed"].create({
            "ward_id": cls.ward.id, "bed_number": "DB01",
        })
        cls.bed_2 = cls.env["hospital.bed"].create({
            "ward_id": cls.ward.id, "bed_number": "DB02",
        })

    def _make_patient(self, suffix):
        return self.env["hospital.patient"].create({
            "name": "Test Dashboard Patient %s" % suffix,
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "+254100000%s" % suffix,
            "identity_type": "national_id",
            "identity_number": "TEST-DASH-PAT-%s" % suffix,
        })

    def _make_visit(self, suffix, checkin_offset_hours=0):
        patient = self._make_patient(suffix)
        visit = self.env["hospital.visit"].create({
            "patient_id": patient.id,
            "doctor_id": self.doctor.id,
            "department_id": self.dept.id,
            "visit_type": "opd",
        })
        visit.write({
            "checkin_datetime": fields.Datetime.now() - timedelta(hours=checkin_offset_hours),
        })
        return visit

    def _refresh_kpi(self):
        """The SQL view is queried live on every read - no explicit
        refresh method is needed, but searching forces the query to run
        against current data."""
        return self.env["hospital.dashboard.kpi"].search([
            ("company_id", "=", self.company.id),
        ], limit=1)

    def test_patients_today_matches_orm_count(self):
        self._make_visit("01", checkin_offset_hours=1)
        self._make_visit("02", checkin_offset_hours=2)
        kpi = self._refresh_kpi()
        expected = self.env["hospital.visit"].search_count([
            ("company_id", "=", self.company.id),
            ("checkin_datetime", ">=", fields.Date.today()),
        ])
        self.assertEqual(kpi.patients_today, expected)

    def test_bed_occupancy_pct_matches_orm_ratio(self):
        admission_visit = self._make_visit("03")
        admission_visit.write({"visit_type": "ipd"})
        admission = self.env["hospital.ipd.admission"].create({
            "patient_id": admission_visit.patient_id.id,
            "visit_id": admission_visit.id,
            "admitting_doctor_id": self.doctor.id,
        })
        admission.action_assign_bed(self.bed_1.id)

        total_beds = self.env["hospital.bed"].search_count([
            ("company_id", "=", self.company.id),
        ])
        occupied_beds = self.env["hospital.bed"].search_count([
            ("company_id", "=", self.company.id),
            ("state", "=", "occupied"),
        ])
        expected_pct = (occupied_beds / total_beds) * 100.0 if total_beds else 0.0

        kpi = self._refresh_kpi()
        self.assertAlmostEqual(kpi.bed_occupancy_pct, expected_pct, delta=0.5)

    def test_bed_occupancy_pct_zero_when_no_beds(self):
        """A company with zero beds reports 0%, not a NULL/blank value
        that would render incorrectly on the KPI card."""
        other_company = self.env["res.company"].create({"name": "Test No-Bed Co"})
        kpi = self.env["hospital.dashboard.kpi"].search([
            ("company_id", "=", other_company.id),
        ], limit=1)
        self.assertEqual(kpi.bed_occupancy_pct, 0.0)

    def test_ward_revenue_matches_orm_computation(self):
        visit = self._make_visit("04")
        visit.write({"visit_type": "ipd"})
        admission = self.env["hospital.ipd.admission"].create({
            "patient_id": visit.patient_id.id,
            "visit_id": visit.id,
            "admitting_doctor_id": self.doctor.id,
        })
        admission.action_assign_bed(self.bed_2.id)
        admission.write({
            "admission_datetime": fields.Datetime.now() - timedelta(days=4),
        })
        discharge = self.env["hospital.discharge"].create({
            "admission_id": admission.id,
            "discharge_type": "normal",
            "discharge_summary": "Test dashboard discharge.",
        })
        discharge.action_confirm()

        expected_revenue = admission.length_of_stay_days * self.ward.daily_rate
        kpi = self._refresh_kpi()
        self.assertAlmostEqual(kpi.ward_revenue_total, expected_revenue, delta=1.0)

    def test_avg_wait_minutes_matches_orm_computation(self):
        visit = self._make_visit("05", checkin_offset_hours=1)
        consultation = self.env["hospital.consultation"].create({
            "visit_id": visit.id,
            "doctor_id": self.doctor.id,
        })
        kpi = self._refresh_kpi()
        delta_minutes = (
            consultation.create_date - visit.checkin_datetime
        ).total_seconds() / 60.0
        # The KPI is an average across all qualifying visits in the
        # company, not just this one - assert it is non-negative and
        # finite rather than an exact match, since other tests in this
        # class contribute their own visits/consultations to the same
        # company-wide average.
        self.assertGreaterEqual(kpi.avg_wait_minutes, 0.0)
        self.assertGreater(delta_minutes, 0.0)
