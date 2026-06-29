# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalDischargeWizard(models.TransientModel):
    """Discharge summary wizard (Phase 8 §16).

    Creates the ``hospital.discharge`` record in draft, lets the user
    review the blocking-items panel, then confirms -- confirmation is
    delegated entirely to ``hospital.discharge.action_confirm()``, which
    is the single place the pending-branches block (Phase 3 §4) is
    enforced, so this wizard never duplicates that business rule.
    """

    _name = "hospital.discharge.wizard"
    _description = "Hospital Discharge Wizard"

    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Admission",
        required=True,
        domain="[('state', '=', 'admitted')]",
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        related="admission_id.patient_id",
    )
    discharge_type = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("ama", "Against Medical Advice"),
            ("deceased", "Deceased"),
            ("referred", "Referred"),
        ],
        string="Discharge Type",
        required=True,
        default="normal",
    )
    discharge_summary = fields.Text(string="Discharge Summary")
    follow_up_instructions = fields.Text(string="Follow-up Instructions")
    blocking_items_summary = fields.Text(
        string="Blocking Items",
        compute="_compute_blocking_items_summary",
    )
    medication_line_ids = fields.One2many(
        comodel_name="hospital.discharge.wizard.medication",
        inverse_name="wizard_id",
        string="Discharge Medications",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "hospital.ipd.admission" and active_id:
            res["admission_id"] = active_id
        return res

    @api.depends("admission_id")
    def _compute_blocking_items_summary(self):
        for wizard in self:
            visit = wizard.admission_id.visit_id
            if not visit:
                wizard.blocking_items_summary = False
                continue
            pending = visit._compute_pending_branches().get(visit.id, [])
            wizard.blocking_items_summary = (
                ", ".join(sorted(set(pending))) if pending else False
            )

    def action_confirm_discharge(self):
        """Create the discharge record and immediately confirm it.

        Any pending-branch block raises from
        ``hospital.discharge.action_confirm()`` itself (Phase 3 §4) -- no
        duplicate validation here, per Phase 11 §1 "model methods own
        the logic".
        """
        self.ensure_one()
        if not self.discharge_summary:
            raise UserError(_("Please enter a discharge summary."))
        discharge = self.env["hospital.discharge"].create({
            "admission_id": self.admission_id.id,
            "discharge_type": self.discharge_type,
            "discharge_summary": self.discharge_summary,
            "follow_up_instructions": self.follow_up_instructions,
            "discharged_by": self.env.uid,
            "discharge_medication_ids": [
                (0, 0, {
                    "medicine_id": line.medicine_id.id,
                    "dosage": line.dosage,
                    "frequency": line.frequency,
                    "duration_days": line.duration_days,
                    "instructions": line.instructions,
                })
                for line in self.medication_line_ids
            ],
        })
        discharge.action_confirm()
        return {"type": "ir.actions.act_window_close"}


class HospitalDischargeWizardMedication(models.TransientModel):
    """Transient medication line for the discharge wizard, copied onto
    the real ``hospital.discharge.medication`` rows on confirm.
    """

    _name = "hospital.discharge.wizard.medication"
    _description = "Hospital Discharge Wizard Medication Line"

    wizard_id = fields.Many2one(
        comodel_name="hospital.discharge.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    medicine_id = fields.Many2one(
        comodel_name="product.product",
        string="Medicine",
        required=True,
    )
    dosage = fields.Char(string="Dosage")
    frequency = fields.Char(string="Frequency")
    duration_days = fields.Integer(string="Duration (days)")
    instructions = fields.Char(string="Instructions")
