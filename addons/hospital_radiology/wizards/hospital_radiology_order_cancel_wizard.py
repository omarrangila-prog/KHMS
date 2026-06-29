# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalRadiologyOrderCancelWizard(models.TransientModel):
    """Wizard requiring a cancellation reason before cancelling a radiology order.

    Phase 3 §6 edge case: cancellation after scheduling requires a reason
    and is audit-logged because the slot/preparation may have been consumed.
    """

    _name = "hospital.radiology.order.cancel.wizard"
    _description = "Radiology Order Cancellation Wizard"

    order_id = fields.Many2one(
        comodel_name="hospital.radiology.order",
        string="Radiology Order",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Cancellation Reason",
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            res["order_id"] = active_id
        return res

    def action_confirm_cancel(self):
        """Cancel the radiology order with the supplied reason."""
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("A cancellation reason is required."))
        self.order_id.action_cancel(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
