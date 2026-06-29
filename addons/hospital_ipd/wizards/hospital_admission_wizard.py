# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalAdmissionWizard(models.TransientModel):
    """Convert a doctor's admission request into a bed assignment
    (Phase 8 §15 "Admission" screen).

    Two entry points are supported:

    1. From a visit/consultation with ``outcome_admit_requested`` set but
       no ``hospital.ipd.admission`` yet -- creates the admission record
       (state ``requested``) and optionally assigns a bed in the same
       step if one is selected.
    2. From an existing ``waiting_for_bed``/``requested`` admission --
       only assigns the bed.

    Bed choices are pre-filtered to vacant beds only (Phase 8 §15: "ward/
    bed selector filtered to vacant beds only"); the actual uniqueness
    guarantee is still enforced by the DB partial index on
    ``hospital.ipd.admission`` (see that model's ``init()`` hook), this
    wizard's domain is a UX convenience, not the source of truth.
    """

    _name = "hospital.admission.wizard"
    _description = "Hospital Admission Wizard"

    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        domain="[('visit_type', '=', 'ipd')]",
    )
    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Existing Admission",
        help="Set when assigning a bed to an admission already in "
             "'Requested' or 'Waiting for Bed' state.",
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        related="visit_id.patient_id",
    )
    admitting_doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Admitting Doctor",
    )
    ward_id = fields.Many2one(
        comodel_name="hospital.ward",
        string="Ward",
    )
    bed_id = fields.Many2one(
        comodel_name="hospital.bed",
        string="Bed",
        domain="[('ward_id', '=', ward_id), ('state', '=', 'vacant')]",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "hospital.visit" and active_id:
            res["visit_id"] = active_id
        elif active_model == "hospital.ipd.admission" and active_id:
            admission = self.env["hospital.ipd.admission"].browse(active_id)
            res["admission_id"] = admission.id
            res["visit_id"] = admission.visit_id.id
            res["admitting_doctor_id"] = admission.admitting_doctor_id.id
        return res

    def action_confirm(self):
        """Create the admission (if needed) and assign the bed.

        Letting the DB-level partial unique index be the final word on
        bed exclusivity (rather than re-checking and trusting a Python
        read) is intentional -- see
        ``hospital.ipd.admission``'s class docstring concurrency note.
        """
        self.ensure_one()
        if not self.bed_id:
            raise UserError(_("Please select a vacant bed."))

        admission = self.admission_id
        if not admission:
            if not self.visit_id:
                raise UserError(_("Please select a visit to admit."))
            admission = self.env["hospital.ipd.admission"].create({
                "patient_id": self.visit_id.patient_id.id,
                "visit_id": self.visit_id.id,
                "admitting_doctor_id": self.admitting_doctor_id.id,
            })

        admission.action_assign_bed(self.bed_id.id)
        return {"type": "ir.actions.act_window_close"}
