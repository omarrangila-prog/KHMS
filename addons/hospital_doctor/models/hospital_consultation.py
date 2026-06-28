# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HospitalConsultation(models.Model):
    """Doctor's consultation record (Phase 3 §3, Phase 5 §3.2, Phase 6 §4).

    Outcome selection is modeled as five independent booleans rather than
    a Many2many to a tag model: Phase 3 §3 requires the doctor to be able
    to pick *any combination* of prescribe/lab/radiology/admit/discharge
    simultaneously, and there are exactly five fixed, well-known outcomes
    with no need for users to define new ones -- a tag model would be
    premature abstraction for a closed, small set of flags (Phase 11 §1
    "no business logic in views", and the project's general
    no-premature-abstraction preference).

    Only ``outcome_prescribe`` results in a real sub-record
    (``hospital.prescription``) being created by this module.
    ``outcome_lab_requested`` / ``outcome_radiology_requested`` /
    ``outcome_admit_requested`` are intent-only flags until
    ``hospital_lab`` / ``hospital_radiology`` / ``hospital_ipd`` exist --
    see ``hospital.visit._compute_pending_branches()`` for the extension
    contract those modules implement against these same flags.
    """

    _name = "hospital.consultation"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Hospital Consultation"
    _order = "create_date desc"

    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        related="visit_id.patient_id",
        store=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Doctor",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        default=lambda self: self._default_doctor_id(),
    )
    diagnosis_code = fields.Char(
        string="Diagnosis Code",
        help="Optional ICD-10 code.",
    )
    diagnosis_text = fields.Text(string="Diagnosis")
    clinical_notes = fields.Text(string="Clinical Notes")
    outcome_prescribe = fields.Boolean(string="Prescribe Medication")
    outcome_lab_requested = fields.Boolean(
        string="Lab Tests Requested",
        help="Intent-only until hospital_lab is installed: no "
             "hospital.lab.order is created yet. See hospital.visit."
             "_compute_pending_branches() for the extension contract.",
    )
    outcome_radiology_requested = fields.Boolean(
        string="Radiology Requested",
        help="Intent-only until hospital_radiology is installed: no "
             "hospital.radiology.order is created yet. See hospital.visit."
             "_compute_pending_branches() for the extension contract.",
    )
    outcome_admit_requested = fields.Boolean(
        string="Admission Requested",
        help="Intent-only until hospital_ipd is installed: no "
             "hospital.ipd.admission is created yet. See hospital.visit."
             "_compute_pending_branches() for the extension contract.",
    )
    outcome_discharge = fields.Boolean(string="Discharge")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("done", "Done"),
        ],
        string="Status",
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    amended_from_id = fields.Many2one(
        comodel_name="hospital.consultation",
        string="Amended From",
        ondelete="restrict",
        index=True,
        help="Set on the new consultation created by the same-day "
             "amendment wizard, pointing back to the original.",
    )
    prescription_ids = fields.One2many(
        comodel_name="hospital.prescription",
        inverse_name="consultation_id",
        string="Prescriptions",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        index=True,
    )
    vitals_history_ids = fields.One2many(
        comodel_name="hospital.vitals",
        related="visit_id.vitals_ids",
        string="Vitals (this visit)",
    )
    patient_consultation_history_ids = fields.Many2many(
        comodel_name="hospital.consultation",
        compute="_compute_patient_consultation_history_ids",
        string="Previous Consultations",
        help="Read-only cross-visit history for the same patient -- the "
             "'review history' half of the Phase 3 §3 consultation "
             "contract ('Doctor reviews history ... on one screen').",
    )
    allergy_summary = fields.Char(
        string="Allergy Summary",
        compute="_compute_allergy_summary",
        help="Flattened allergy banner sourced from hospital.patient."
             "allergy_ids, shown as a hard-to-miss warning on the "
             "consultation form (Phase 8 §9 allergy-conflict context).",
    )

    @api.model
    def _default_doctor_id(self):
        return self.env["hospital.doctor"].search(
            [("user_id", "=", self.env.uid)], limit=1
        )

    @api.depends("patient_id")
    def _compute_patient_consultation_history_ids(self):
        for consultation in self:
            if not consultation.patient_id:
                consultation.patient_consultation_history_ids = False
                continue
            consultation.patient_consultation_history_ids = self.search(
                [
                    ("patient_id", "=", consultation.patient_id.id),
                    ("id", "!=", consultation.id),
                ]
            )

    @api.depends("patient_id", "patient_id.allergy_ids.name",
                 "patient_id.allergy_ids.severity")
    def _compute_allergy_summary(self):
        for consultation in self:
            allergies = consultation.patient_id.allergy_ids
            if not allergies:
                consultation.allergy_summary = False
                continue
            consultation.allergy_summary = ", ".join(
                "%s (%s)" % (allergy.name, allergy.severity)
                for allergy in allergies
            )

    @api.constrains("outcome_prescribe", "outcome_lab_requested",
                     "outcome_radiology_requested", "outcome_admit_requested",
                     "outcome_discharge", "state")
    def _check_outcome_selected_on_done(self):
        # DB-level backstop (Phase 11 §6) for the same invariant
        # action_done() already validates explicitly -- catches the edge
        # case of a 'done' consultation later having its outcome flags
        # cleared by a direct write(), not just the action_done() button.
        for consultation in self:
            if consultation.state == "done" and not consultation._has_any_outcome():
                raise ValidationError(
                    _("Select at least one outcome (prescribe, lab, "
                      "radiology, admit, or discharge) before completing "
                      "the consultation.")
                )

    def _has_any_outcome(self):
        self.ensure_one()
        return any(
            (
                self.outcome_prescribe,
                self.outcome_lab_requested,
                self.outcome_radiology_requested,
                self.outcome_admit_requested,
                self.outcome_discharge,
            )
        )

    def action_done(self):
        """Complete the consultation and route the visit's aggregate
        state (Phase 3 §3).

        Validates at least one outcome is selected, sets ``state=done``,
        then delegates to ``hospital.visit.action_route_from_consultation()``
        so this method stays a thin orchestrator -- the actual aggregate-
        state logic (and its future-module extension point) lives on the
        visit, per Phase 11 §1 "model methods own the logic".
        """
        for consultation in self:
            if not consultation._has_any_outcome():
                raise UserError(
                    _("Select at least one outcome (prescribe, lab, "
                      "radiology, admit, or discharge) before completing "
                      "the consultation.")
                )
            consultation.state = "done"
        self.mapped("visit_id").action_route_from_consultation()
        return True

    def action_view_prescriptions(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "hospital_doctor.hospital_prescription_action"
        )
        action["domain"] = [("consultation_id", "=", self.id)]
        action["context"] = {
            "default_consultation_id": self.id,
            "default_visit_id": self.visit_id.id,
            "default_doctor_id": self.doctor_id.id,
        }
        return action
