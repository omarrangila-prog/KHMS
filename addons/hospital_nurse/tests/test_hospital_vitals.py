# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHospitalVitals(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Visit = cls.env["hospital.visit"]
        cls.Vitals = cls.env["hospital.vitals"]
        cls.patient = cls.Patient.create(
            {
                "name": "Vitals Test Patient",
                "date_of_birth": "1985-05-15",
                "phone": "+10000003001",
                "identity_number": "VIT-TEST-0001",
            }
        )

    def _new_visit(self, **extra):
        vals = {"patient_id": self.patient.id, "visit_type": "opd"}
        vals.update(extra)
        visit = self.Visit.create(vals)
        visit.action_confirm()
        self.assertEqual(visit.state, "waiting_nurse")
        return visit

    # -- BMI computation -------------------------------------------------

    def test_bmi_computation_correct(self):
        visit = self._new_visit()
        vitals = self.Vitals.create(
            {
                "visit_id": visit.id,
                "height_cm": 170,
                "weight_kg": 70,
            }
        )
        # 70 / (1.70^2) = 24.221...
        self.assertAlmostEqual(vitals.bmi, 24.2, places=1)
        self.assertEqual(vitals.bmi_status, "normal")

    def test_bmi_zero_when_height_or_weight_missing(self):
        visit = self._new_visit()
        vitals = self.Vitals.create(
            {
                "visit_id": visit.id,
                "height_cm": 170,
            }
        )
        self.assertEqual(vitals.bmi, 0.0)
        self.assertFalse(vitals.bmi_status)

    def test_bmi_status_bands(self):
        visit = self._new_visit()
        underweight = self.Vitals.create(
            {"visit_id": visit.id, "height_cm": 170, "weight_kg": 50}
        )
        self.assertEqual(underweight.bmi_status, "underweight")

        visit2 = self._new_visit()
        overweight = self.Vitals.create(
            {"visit_id": visit2.id, "height_cm": 170, "weight_kg": 80}
        )
        self.assertEqual(overweight.bmi_status, "overweight")

        visit3 = self._new_visit()
        obese = self.Vitals.create(
            {"visit_id": visit3.id, "height_cm": 170, "weight_kg": 100}
        )
        self.assertEqual(obese.bmi_status, "obese")

    # -- Range constraints -------------------------------------------------

    def test_spo2_out_of_range_rejected(self):
        visit = self._new_visit()
        with self.assertRaises(ValidationError):
            self.Vitals.create({"visit_id": visit.id, "spo2": 150})

    def test_pulse_rate_out_of_range_rejected(self):
        visit = self._new_visit()
        with self.assertRaises(ValidationError):
            self.Vitals.create({"visit_id": visit.id, "pulse_rate": 400})

    def test_temperature_out_of_range_rejected(self):
        visit = self._new_visit()
        with self.assertRaises(ValidationError):
            self.Vitals.create({"visit_id": visit.id, "temperature": 50.0})

    def test_respiratory_rate_out_of_range_rejected(self):
        visit = self._new_visit()
        with self.assertRaises(ValidationError):
            self.Vitals.create({"visit_id": visit.id, "respiratory_rate": 150})

    def test_blood_pressure_out_of_range_rejected(self):
        visit = self._new_visit()
        with self.assertRaises(ValidationError):
            self.Vitals.create(
                {"visit_id": visit.id, "blood_pressure_systolic": 350}
            )
        visit2 = self._new_visit()
        with self.assertRaises(ValidationError):
            self.Vitals.create(
                {"visit_id": visit2.id, "blood_pressure_diastolic": 5}
            )

    def test_valid_vitals_within_range_accepted(self):
        visit = self._new_visit()
        vitals = self.Vitals.create(
            {
                "visit_id": visit.id,
                "blood_pressure_systolic": 120,
                "blood_pressure_diastolic": 80,
                "pulse_rate": 72,
                "temperature": 36.8,
                "spo2": 98,
                "respiratory_rate": 16,
            }
        )
        self.assertFalse(vitals.is_abnormal)

    # -- Abnormal-vitals auto-escalation (Phase 3 §2) ----------------------

    def test_abnormal_high_bp_escalates_priority_to_urgent(self):
        visit = self._new_visit()
        self.assertEqual(visit.priority, "normal")
        self.Vitals.create(
            {"visit_id": visit.id, "blood_pressure_systolic": 200}
        )
        self.assertEqual(visit.priority, "urgent")

    def test_abnormal_low_spo2_escalates_priority_to_urgent(self):
        visit = self._new_visit()
        self.Vitals.create({"visit_id": visit.id, "spo2": 85})
        self.assertEqual(visit.priority, "urgent")

    def test_abnormal_high_temperature_escalates_priority(self):
        visit = self._new_visit()
        self.Vitals.create({"visit_id": visit.id, "temperature": 40.0})
        self.assertEqual(visit.priority, "urgent")

    def test_abnormal_pulse_escalates_priority(self):
        visit = self._new_visit()
        self.Vitals.create({"visit_id": visit.id, "pulse_rate": 150})
        self.assertEqual(visit.priority, "urgent")

    def test_normal_vitals_do_not_change_priority(self):
        visit = self._new_visit()
        self.Vitals.create(
            {
                "visit_id": visit.id,
                "blood_pressure_systolic": 118,
                "pulse_rate": 70,
                "temperature": 36.6,
                "spo2": 99,
            }
        )
        self.assertEqual(visit.priority, "normal")

    def test_escalation_never_deescalates_existing_emergency(self):
        visit = self._new_visit(priority="emergency")
        self.assertEqual(visit.priority, "emergency")
        # Normal vitals must not downgrade an emergency visit.
        self.Vitals.create(
            {
                "visit_id": visit.id,
                "blood_pressure_systolic": 118,
                "pulse_rate": 70,
                "temperature": 36.6,
                "spo2": 99,
            }
        )
        self.assertEqual(visit.priority, "emergency")
        # Abnormal vitals must also leave emergency untouched (no downgrade
        # to 'urgent', which would actually be a de-escalation).
        visit2 = self._new_visit(priority="emergency")
        self.Vitals.create(
            {"visit_id": visit2.id, "blood_pressure_systolic": 200}
        )
        self.assertEqual(visit2.priority, "emergency")

    # -- Auto-transition waiting_nurse -> waiting_doctor -------------------

    def test_vitals_creation_auto_transitions_visit(self):
        visit = self._new_visit()
        self.assertEqual(visit.state, "waiting_nurse")
        self.Vitals.create({"visit_id": visit.id, "pulse_rate": 72})
        self.assertEqual(visit.state, "waiting_doctor")

    def test_auto_transition_happens_even_for_normal_vitals(self):
        visit = self._new_visit()
        self.Vitals.create(
            {
                "visit_id": visit.id,
                "blood_pressure_systolic": 118,
                "pulse_rate": 70,
                "temperature": 36.6,
                "spo2": 99,
            }
        )
        self.assertEqual(visit.state, "waiting_doctor")
        self.assertEqual(visit.priority, "normal")

    def test_vitals_creation_without_waiting_nurse_state_does_not_force_transition(self):
        visit = self._new_visit()
        self.Vitals.create({"visit_id": visit.id, "pulse_rate": 72})
        self.assertEqual(visit.state, "waiting_doctor")
        # Recording a second vitals entry (e.g. a re-check) while already
        # in waiting_doctor must not raise -- only visits still sitting in
        # waiting_nurse are transitioned.
        self.Vitals.create({"visit_id": visit.id, "pulse_rate": 75})
        self.assertEqual(visit.state, "waiting_doctor")
