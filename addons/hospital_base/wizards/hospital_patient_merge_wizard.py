# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalPatientMergeWizard(models.TransientModel):
    """Admin-only duplicate merge tool (Phase 3 §7).

    Re-parents visits/allergies/conditions from the duplicate patient
    records onto the surviving patient, then archives the duplicates
    (never a hard delete of clinical-adjacent data).
    """

    _name = "hospital.patient.merge.wizard"
    _description = "Merge Duplicate Patients"

    survivor_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient to Keep",
        required=True,
    )
    duplicate_ids = fields.Many2many(
        comodel_name="hospital.patient",
        string="Duplicate Patients to Merge",
        help="These records will be archived after their visits, "
             "allergies and chronic conditions are moved to the patient "
             "to keep.",
    )

    @api.model
    def default_get(self, field_list):
        defaults = super().default_get(field_list)
        active_ids = self.env.context.get("active_ids") or []
        if active_ids:
            defaults["survivor_id"] = active_ids[0]
            defaults["duplicate_ids"] = [(6, 0, active_ids[1:])]
        return defaults

    def action_merge(self):
        self.ensure_one()
        if not self.duplicate_ids:
            raise UserError(_("Select at least one duplicate patient to merge."))
        if self.survivor_id in self.duplicate_ids:
            raise UserError(
                _("The patient to keep cannot also be listed as a duplicate.")
            )
        for duplicate in self.duplicate_ids:
            duplicate.visit_ids.write({"patient_id": self.survivor_id.id})
            duplicate.allergy_ids.write({"patient_id": self.survivor_id.id})
            duplicate.chronic_condition_ids.write({"patient_id": self.survivor_id.id})
            duplicate.write({"active": False})
        return {
            "type": "ir.actions.act_window",
            "res_model": "hospital.patient",
            "res_id": self.survivor_id.id,
            "view_mode": "form",
            "target": "current",
        }
