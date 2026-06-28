# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalVisitCancelWizard(models.TransientModel):
    """Mandatory-reason cancellation wizard (Phase 3 §7: "Patient leaves
    mid-workflow ... cancelled with mandatory reason").

    ``hospital.visit.action_cancel()`` (defined in ``hospital_base``)
    takes no arguments -- it reads ``cancel_reason`` directly off the
    record and raises ``UserError`` if it is empty. This wizard simply
    writes the reason onto the visit first, then calls ``action_cancel()``,
    so the existing model-level guarantee (and its ``@api.constrains``
    backstop) is reused rather than duplicated.
    """

    _name = "hospital.visit.cancel.wizard"
    _description = "Cancel Visit"

    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
    )
    reason = fields.Text(string="Cancellation Reason", required=True)

    @api.model
    def default_get(self, field_list):
        defaults = super().default_get(field_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            defaults["visit_id"] = active_id
        return defaults

    def action_confirm_cancel(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("Please provide a cancellation reason."))
        self.visit_id.write({"cancel_reason": self.reason})
        self.visit_id.action_cancel()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hospital.visit",
            "res_id": self.visit_id.id,
            "view_mode": "form",
            "target": "current",
        }
