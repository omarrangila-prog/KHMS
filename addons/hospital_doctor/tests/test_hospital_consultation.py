# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHospitalConsultation(TransactionCase):
    """Integration tests covering every outcome combination from Phase 3
    §3, verifying the visit's aggregate state ends up correct per the
    routing rules implemented in hospital.visit.action_route_from_consultation()
    / _compute_pending_branches().
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Patient = cls.env["hospital.patient"]
        cls.Visit = cls.env["hospital.visit"]
        cls.Vitals = cls.env["hospital.vitals"]
        cls.Consultation = cls.env["hospital.consultation"]
        cls.Prescription = cls.env["hospital.prescription"]
        cls.Doctor = cls.env["hospital.doctor"]
        cls.Product = cls.env["product.product"]

        cls.doctor_user = cls.env["res.users"].create(
            {
                "name": "Dr. Test Routing",
                "login": "dr.test.routing@example.com",
                "email": "dr.test.routing@example.com",
            }
        )
        cls.doctor = cls.Doctor.create(
            {
                "user_id": cls.doctor_user.id,
                "specialization": "General Medicine",
            }
        )
        cls.patient = cls.Patient.create(
            {
                "name": "Consultation Test Patient",
                "date_of_birth": "1990-01-01",
                "phone": "+10000004001",
                "identity_number": "CONS-TEST-0001",
            }
        )
        cls.medicine = cls.Product.create(
            {"name": "Test Medicine", "type": "consu"}
        )

    def _new_visit_at_doctor(self, **extra):
        vals = {
            "patient_id": self.patient.id,
            "visit_type": "opd",
            "doctor_id": self.doctor.id,
        }
        vals.update(extra)
        visit = self.Visit.create(vals)
        visit.action_confirm()
        self.Vitals.create({"visit_id": visit.id, "pulse_rate": 72})
        self.assertEqual(visit.state, "waiting_doctor")
        return visit

    def _new_consultation(self, visit, **outcome_flags):
        return self.Consultation.create(
            {
                "visit_id": visit.id,
                "doctor_id": self.doctor.id,
                "diagnosis_text": "Test diagnosis",
                **outcome_flags,
            }
        )

    # -- Validation --------------------------------------------------------

    def test_action_done_requires_at_least_one_outcome(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit)
        with self.assertRaises(UserError):
            consultation.action_done()

    # -- Discharge only -> billing ------------------------------------------

    def test_discharge_only_routes_visit_to_billing(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_discharge=True)
        consultation.action_done()
        self.assertEqual(consultation.state, "done")
        self.assertEqual(visit.state, "billing")

    # -- Prescribe only -> stays in_progress_multi (open prescription) -----

    def test_prescribe_only_with_open_prescription_keeps_in_progress_multi(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_prescribe=True)
        self.Prescription.create(
            {
                "visit_id": visit.id,
                "consultation_id": consultation.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {
                        "medicine_id": self.medicine.id,
                        "qty_prescribed": 10,
                    })
                ],
            }
        )
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")

    def test_prescribe_with_cancelled_prescription_routes_to_billing(self):
        # A prescription cancelled before being acted on is excluded from
        # the all-branches-completed check (Phase 3 §3 "If a lab/radiology
        # order is cancelled ... it's excluded").
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_prescribe=True)
        prescription = self.Prescription.create(
            {
                "visit_id": visit.id,
                "consultation_id": consultation.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {
                        "medicine_id": self.medicine.id,
                        "qty_prescribed": 10,
                    })
                ],
            }
        )
        prescription.action_cancel()
        consultation.action_done()
        self.assertEqual(visit.state, "billing")

    # -- Prescribe + lab requested (multi-branch) ---------------------------

    def test_prescribe_and_lab_requested_keeps_in_progress_multi(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(
            visit, outcome_prescribe=True, outcome_lab_requested=True
        )
        self.Prescription.create(
            {
                "visit_id": visit.id,
                "consultation_id": consultation.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {
                        "medicine_id": self.medicine.id,
                        "qty_prescribed": 5,
                    })
                ],
            }
        )
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")
        pending = visit._compute_pending_branches()[visit.id]
        self.assertIn("prescription", pending)
        self.assertIn("lab", pending)

    # -- Admit requested alone (intent-only) ---------------------------------

    def test_admit_requested_alone_keeps_in_progress_multi(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_admit_requested=True)
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")
        pending = visit._compute_pending_branches()[visit.id]
        self.assertEqual(pending, ["admission"])

    # -- Radiology requested alone --------------------------------------------

    def test_radiology_requested_alone_keeps_in_progress_multi(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_radiology_requested=True)
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")
        pending = visit._compute_pending_branches()[visit.id]
        self.assertEqual(pending, ["radiology"])

    # -- Lab + radiology requested together (two intent-only branches) -------

    def test_lab_and_radiology_requested_together(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(
            visit, outcome_lab_requested=True, outcome_radiology_requested=True
        )
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")
        pending = set(visit._compute_pending_branches()[visit.id])
        self.assertEqual(pending, {"lab", "radiology"})

    # -- Prescribe + admit requested ------------------------------------------

    def test_prescribe_and_admit_requested(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(
            visit, outcome_prescribe=True, outcome_admit_requested=True
        )
        self.Prescription.create(
            {
                "visit_id": visit.id,
                "consultation_id": consultation.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {
                        "medicine_id": self.medicine.id,
                        "qty_prescribed": 3,
                    })
                ],
            }
        )
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")
        pending = set(visit._compute_pending_branches()[visit.id])
        self.assertEqual(pending, {"prescription", "admission"})

    # -- Discharge + prescribe together (discharge not exclusive) ------------

    def test_discharge_and_prescribe_together_keeps_in_progress_multi(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(
            visit, outcome_prescribe=True, outcome_discharge=True
        )
        self.Prescription.create(
            {
                "visit_id": visit.id,
                "consultation_id": consultation.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {
                        "medicine_id": self.medicine.id,
                        "qty_prescribed": 2,
                    })
                ],
            }
        )
        consultation.action_done()
        # Even though discharge was also selected, the open prescription
        # branch means the visit cannot jump straight to billing.
        self.assertEqual(visit.state, "in_progress_multi")

    # -- All five outcomes at once -------------------------------------------

    def test_all_outcomes_selected_at_once(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(
            visit,
            outcome_prescribe=True,
            outcome_lab_requested=True,
            outcome_radiology_requested=True,
            outcome_admit_requested=True,
            outcome_discharge=True,
        )
        self.Prescription.create(
            {
                "visit_id": visit.id,
                "consultation_id": consultation.id,
                "doctor_id": self.doctor.id,
                "line_ids": [
                    (0, 0, {
                        "medicine_id": self.medicine.id,
                        "qty_prescribed": 1,
                    })
                ],
            }
        )
        consultation.action_done()
        self.assertEqual(visit.state, "in_progress_multi")
        pending = set(visit._compute_pending_branches()[visit.id])
        self.assertEqual(pending, {"prescription", "lab", "radiology", "admission"})

    # -- Same-day amendment reopens visit from billing -----------------------

    def test_amendment_wizard_reopens_visit_from_billing(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_discharge=True)
        consultation.action_done()
        self.assertEqual(visit.state, "billing")

        wizard = self.env["hospital.consultation.amend.wizard"].create(
            {
                "consultation_id": consultation.id,
                "reason": "Forgot to order bloodwork.",
            }
        )
        result = wizard.action_confirm_amend()
        new_consultation = self.Consultation.browse(result["res_id"])
        self.assertEqual(new_consultation.amended_from_id, consultation)
        self.assertEqual(visit.state, "in_progress_multi")

        # Original consultation is untouched.
        self.assertEqual(consultation.state, "done")

    def test_amendment_blocked_on_non_done_consultation(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_discharge=True)
        wizard = self.env["hospital.consultation.amend.wizard"].create(
            {
                "consultation_id": consultation.id,
                "reason": "Trying to amend a draft consultation.",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_confirm_amend()

    def test_amendment_requires_reason(self):
        visit = self._new_visit_at_doctor()
        consultation = self._new_consultation(visit, outcome_discharge=True)
        consultation.action_done()
        wizard = self.env["hospital.consultation.amend.wizard"].create(
            {"consultation_id": consultation.id, "reason": " "}
        )
        with self.assertRaises(UserError):
            wizard.action_confirm_amend()

    # -- Doctor default --------------------------------------------------------

    def test_default_doctor_id_resolves_from_current_user(self):
        consultation = self.Consultation.with_user(self.doctor_user).create(
            {
                "visit_id": self._new_visit_at_doctor().id,
                "outcome_discharge": True,
            }
        )
        self.assertEqual(consultation.doctor_id, self.doctor)
