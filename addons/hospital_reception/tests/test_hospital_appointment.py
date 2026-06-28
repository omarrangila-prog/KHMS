# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHospitalAppointment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Appointment = cls.env["hospital.appointment"]
        cls.Visit = cls.env["hospital.visit"]
        cls.patient = cls.Patient.create(
            {
                "name": "Appointment Test Patient",
                "date_of_birth": "1992-04-10",
                "phone": "+10000002001",
                "identity_number": "APT-TEST-0001",
            }
        )

    def _new_appointment(self, **extra):
        vals = {
            "patient_id": self.patient.id,
            "scheduled_datetime": "2026-07-01 09:00:00",
        }
        vals.update(extra)
        return self.Appointment.create(vals)

    def test_appointment_reference_sequence_generated(self):
        appointment = self._new_appointment()
        self.assertTrue(appointment.name)
        self.assertTrue(appointment.name.startswith("APT/"))
        self.assertEqual(appointment.state, "draft")

    def test_check_in_creates_visit_in_waiting_nurse(self):
        appointment = self._new_appointment()
        appointment.action_check_in()
        self.assertEqual(appointment.state, "checked_in")
        self.assertTrue(appointment.visit_id)
        self.assertEqual(appointment.visit_id.state, "waiting_nurse")
        self.assertEqual(appointment.visit_id.patient_id, self.patient)

    def test_check_in_links_doctor_and_department(self):
        department = self.env["hospital.department"].create(
            {"name": "Test Dept", "code": "TSTD"}
        )
        doctor_user = self.env["res.users"].create(
            {
                "name": "Dr. Test Appointment",
                "login": "dr.test.appointment@example.com",
                "email": "dr.test.appointment@example.com",
            }
        )
        doctor = self.env["hospital.doctor"].create(
            {"user_id": doctor_user.id, "department_id": department.id}
        )
        appointment = self._new_appointment(
            doctor_id=doctor.id, department_id=department.id
        )
        appointment.action_check_in()
        self.assertEqual(appointment.visit_id.doctor_id, doctor)
        self.assertEqual(appointment.visit_id.department_id, department)

    def test_no_show_transition(self):
        appointment = self._new_appointment()
        appointment.action_no_show()
        self.assertEqual(appointment.state, "no_show")

    def test_no_show_blocked_after_check_in(self):
        appointment = self._new_appointment()
        appointment.action_check_in()
        with self.assertRaises(UserError):
            appointment.action_no_show()

    def test_cancel_transition(self):
        appointment = self._new_appointment()
        appointment.action_cancel()
        self.assertEqual(appointment.state, "cancelled")

    def test_cancel_blocked_after_check_in(self):
        appointment = self._new_appointment()
        appointment.action_check_in()
        with self.assertRaises(UserError):
            appointment.action_cancel()

    def test_confirm_transition(self):
        appointment = self._new_appointment()
        appointment.action_confirm()
        self.assertEqual(appointment.state, "confirmed")

    def test_confirm_requires_draft(self):
        appointment = self._new_appointment()
        appointment.action_confirm()
        with self.assertRaises(UserError):
            appointment.action_confirm()

    def test_check_in_allowed_from_confirmed(self):
        appointment = self._new_appointment()
        appointment.action_confirm()
        appointment.action_check_in()
        self.assertEqual(appointment.state, "checked_in")
