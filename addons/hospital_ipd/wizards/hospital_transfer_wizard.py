# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalTransferWizard(models.TransientModel):
    """Mid-stay ward/bed transfer wizard (Phase 6 §9
    ``hospital.bed.transfer.wizard``).

    Creates and confirms a ``hospital.bed.transfer`` row in one step --
    the admission's bed changes, the old bed goes to ``cleaning``, the
    new bed becomes ``occupied``, all within
    ``hospital.bed.transfer.action_confirm()``'s single transaction.
    """

    _name = "hospital.transfer.wizard"
    _description = "Hospital Bed Transfer Wizard"

    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Admission",
        required=True,
        domain="[('state', '=', 'admitted')]",
    )
    from_bed_id = fields.Many2one(
        comodel_name="hospital.bed",
        string="Current Bed",
        related="admission_id.bed_id",
        readonly=True,
    )
    ward_id = fields.Many2one(
        comodel_name="hospital.ward",
        string="New Ward",
    )
    to_bed_id = fields.Many2one(
        comodel_name="hospital.bed",
        string="New Bed",
        domain="[('ward_id', '=', ward_id), ('state', '=', 'vacant')]",
    )
    reason = fields.Text(string="Reason", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "hospital.ipd.admission" and active_id:
            res["admission_id"] = active_id
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.to_bed_id:
            raise UserError(_("Please select a vacant destination bed."))
        if self.to_bed_id == self.admission_id.bed_id:
            raise UserError(_("The destination bed must be different from the current bed."))
        transfer = self.env["hospital.bed.transfer"].create({
            "admission_id": self.admission_id.id,
            "from_bed_id": self.admission_id.bed_id.id,
            "to_bed_id": self.to_bed_id.id,
            "reason": self.reason,
            "transferred_by": self.env.uid,
        })
        transfer.action_confirm()
        return {"type": "ir.actions.act_window_close"}
