# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalPatientRegistrationWizard(models.TransientModel):
    """Combined "search existing or register new" reception flow
    (Phase 8 §2). One screen: pick an existing patient OR fill in new
    identity fields, assign a doctor/department + payer type, and confirm
    to create/reuse the patient and open a queued ``hospital.visit`` in a
    single action.

    Duplicate detection reuses ``hospital.patient.check_duplicate()``
    (Phase 3 FR-3 / Phase 5 §1.1, defined in ``hospital_base``) -- it is
    non-blocking by design, so the warning is surfaced for staff awareness
    only and never prevents confirmation.
    """

    _name = "hospital.patient.registration.wizard"
    _description = "Patient Registration"

    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Existing Patient",
        help="Select an existing patient instead of registering a new one.",
    )

    # New-patient identity fields (Phase 8 §2 wireframe).
    name = fields.Char(string="Full Name")
    date_of_birth = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        selection=[
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    email = fields.Char(string="Email")
    identity_type = fields.Selection(
        selection=[
            ("national_id", "National ID"),
            ("passport", "Passport"),
            ("other", "Other"),
        ],
        string="Identity Type",
        default="national_id",
    )
    identity_number = fields.Char(string="Identity Number")
    emergency_contact_name = fields.Char(string="Emergency Contact Name")
    emergency_contact_phone = fields.Char(string="Emergency Contact Phone")

    # Visit assignment.
    doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Assign Doctor",
    )
    department_id = fields.Many2one(
        comodel_name="hospital.department",
        string="Department",
    )
    payer_type = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("insurance", "Insurance"),
        ],
        string="Payer Type",
        default="cash",
    )
    priority = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("urgent", "Urgent"),
            ("emergency", "Emergency"),
        ],
        string="Priority",
        default="normal",
    )

    # Duplicate-match warning area (Phase 8 §2).
    duplicate_patient_ids = fields.Many2many(
        comodel_name="hospital.patient",
        string="Possible Duplicate Matches",
        compute="_compute_duplicate_patient_ids",
    )
    has_duplicate_warning = fields.Boolean(
        string="Has Duplicate Warning",
        compute="_compute_duplicate_patient_ids",
    )

    @api.depends("identity_number", "patient_id")
    def _compute_duplicate_patient_ids(self):
        Patient = self.env["hospital.patient"]
        for wizard in self:
            if wizard.patient_id or not wizard.identity_number:
                wizard.duplicate_patient_ids = Patient
                wizard.has_duplicate_warning = False
                continue
            matches = Patient.search(
                [("identity_number", "=", wizard.identity_number)]
            )
            wizard.duplicate_patient_ids = matches
            wizard.has_duplicate_warning = bool(matches)

    def action_confirm(self):
        """Create/reuse the patient, create a visit, and confirm it
        (moves the visit to ``waiting_nurse``, per Phase 3 §2).
        """
        self.ensure_one()
        patient = self.patient_id
        if not patient:
            if not self.name or not self.date_of_birth or not self.phone:
                raise UserError(
                    _("Name, date of birth and phone are required to "
                      "register a new patient.")
                )
            patient = self.env["hospital.patient"].create(
                {
                    "name": self.name,
                    "date_of_birth": self.date_of_birth,
                    "gender": self.gender,
                    "phone": self.phone,
                    "mobile": self.mobile,
                    "email": self.email,
                    "identity_type": self.identity_type,
                    "identity_number": self.identity_number,
                    "emergency_contact_name": self.emergency_contact_name,
                    "emergency_contact_phone": self.emergency_contact_phone,
                }
            )

        visit = self.env["hospital.visit"].create(
            {
                "patient_id": patient.id,
                "visit_type": "opd",
                "doctor_id": self.doctor_id.id,
                "department_id": self.department_id.id,
                "payer_type": self.payer_type,
                "priority": self.priority,
            }
        )
        visit.action_confirm()

        return {
            "type": "ir.actions.act_window",
            "res_model": "hospital.visit",
            "res_id": visit.id,
            "view_mode": "form",
            "target": "current",
        }
