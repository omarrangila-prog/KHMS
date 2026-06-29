# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalLabOrderCancelWizard(models.TransientModel):
    """Wizard requiring a cancellation reason before cancelling a lab order.

    A reason is mandatory so the audit trail always explains why a sample
    may have been discarded (Phase 3 §6 edge case: "cancellation requires
    a reason and is audit-logged, sample already consumed").
    """

    _name = "hospital.lab.order.cancel.wizard"
    _description = "Lab Order Cancellation Wizard"

    order_id = fields.Many2one(
        comodel_name="hospital.lab.order",
        string="Lab Order",
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
        """Cancel the lab order with the supplied reason."""
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("A cancellation reason is required."))
        self.order_id.action_cancel(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
