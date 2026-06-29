# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalRadiologyOrder(models.Model):
    """A radiology imaging order raised by a doctor against a visit.

    State machine (Phase 3 §6, Phase 5 §4.4, mirroring hospital_lab):
        ordered -> scheduled -> in_progress -> completed
        (cancelled reachable from ordered or scheduled via wizard)

    ``action_complete`` notifies the ordering doctor by creating a
    ``mail.activity`` (type todo) on the visit's doctor user, per
    Phase 6 §8 OrderCompletionNotifyService.

    NOTE: ``admission_id`` is intentionally omitted (same rationale as
    hospital_lab: hospital_ipd will add it via _inherit once it exists).
    """

    _name = "hospital.radiology.order"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Radiology Order"
    _order = "priority desc, create_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Order Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
    )
    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        required=True,
        ondelete="restrict",
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
        string="Ordering Doctor",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    study_id = fields.Many2one(
        comodel_name="hospital.radiology.study",
        string="Study",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("ordered", "Ordered"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="ordered",
        index=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("urgent", "Urgent"),
            ("emergency", "Emergency"),
        ],
        string="Priority",
        required=True,
        default="normal",
        index=True,
        tracking=True,
    )
    scheduled_datetime = fields.Datetime(
        string="Scheduled Date/Time",
        tracking=True,
    )
    performed_by = fields.Many2one(
        comodel_name="res.users",
        string="Performed By",
        ondelete="set null",
    )
    performed_at = fields.Datetime(string="Performed At")
    cancel_reason = fields.Text(string="Cancellation Reason")
    result_ids = fields.One2many(
        comodel_name="hospital.radiology.result",
        inverse_name="order_id",
        string="Results",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hospital.radiology.order"
                ) or _("New")
        return super().create(vals_list)

    def action_schedule(self):
        """Transition ordered -> scheduled."""
        for order in self:
            if order.state != "ordered":
                raise UserError(
                    _("Only orders in 'Ordered' state can be scheduled. "
                      "Order %s is in state '%s'.") % (order.name, order.state)
                )
            order.state = "scheduled"
        return True

    def action_start(self):
        """Transition scheduled -> in_progress."""
        for order in self:
            if order.state != "scheduled":
                raise UserError(
                    _("Only scheduled orders can be started. "
                      "Order %s is in state '%s'.") % (order.name, order.state)
                )
            order.write({
                "state": "in_progress",
                "performed_by": self.env.uid,
                "performed_at": fields.Datetime.now(),
            })
        return True

    def action_complete(self):
        """Transition in_progress -> completed and notify the ordering doctor.

        Creates a ``mail.activity`` (type: todo) on the visit's doctor user
        so the doctor knows imaging results are ready, per Phase 6 §8
        OrderCompletionNotifyService.
        """
        for order in self:
            if order.state != "in_progress":
                raise UserError(
                    _("Only orders in progress can be completed. "
                      "Order %s is in state '%s'.") % (order.name, order.state)
                )
            order.state = "completed"
            order._notify_doctor_on_completion()
        return True

    def action_cancel(self, reason=None):
        """Cancel the order. Requires a reason (enforced by the wizard)."""
        for order in self:
            if order.state == "completed":
                raise UserError(
                    _("A completed radiology order cannot be cancelled. "
                      "Order: %s") % order.name
                )
            if order.state == "cancelled":
                continue
            write_vals = {"state": "cancelled"}
            if reason:
                write_vals["cancel_reason"] = reason
            order.write(write_vals)
        return True

    def action_cancel_wizard(self):
        """Open the cancel wizard dialog for this radiology order."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cancel Radiology Order"),
            "res_model": "hospital.radiology.order.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def _notify_doctor_on_completion(self):
        """Create a mail.activity for the ordering doctor on completion."""
        self.ensure_one()
        todo_activity_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        if not todo_activity_type:
            return
        doctor_user = self.doctor_id.user_id
        if not doctor_user:
            return
        self.env["mail.activity"].create({
            "activity_type_id": todo_activity_type.id,
            "res_model_id": self.env["ir.model"]._get_id("hospital.radiology.order"),
            "res_id": self.id,
            "user_id": doctor_user.id,
            "summary": _("Radiology results ready for %s") % self.study_id.name,
            "note": _(
                "Radiology order %s (%s) has been completed. "
                "Please review the findings."
            ) % (self.name, self.study_id.name),
        })
