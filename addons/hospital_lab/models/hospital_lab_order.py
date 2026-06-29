# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalLabOrder(models.Model):
    """A laboratory test order raised by a doctor against a visit.

    State machine (Phase 3 §6, Phase 5 §4.2):
        ordered -> sample_collected -> processing -> completed
        (cancelled is reachable from ordered or sample_collected via wizard)

    ``action_complete`` notifies the ordering doctor by creating a
    ``mail.activity`` of type ``mail.activity.data_todo`` on the visit's
    doctor user, per Phase 6 §7's ``OrderCompletionNotifyService`` spec.

    NOTE: ``admission_id`` (Many2one to ``hospital.ipd.admission``) is
    intentionally omitted here. ``hospital.ipd.admission`` does not exist
    until ``hospital_ipd`` is installed. Following the exact same pattern
    used by ``hospital_nurse.hospital.nurse.task``, ``hospital_ipd`` will
    add ``admission_id`` to this model via ``_inherit`` once it exists.
    """

    _name = "hospital.lab.order"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Lab Order"
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
    test_id = fields.Many2one(
        comodel_name="hospital.lab.test",
        string="Test",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("ordered", "Ordered"),
            ("sample_collected", "Sample Collected"),
            ("processing", "Processing"),
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
    sample_barcode = fields.Char(string="Sample Barcode")
    collected_by = fields.Many2one(
        comodel_name="res.users",
        string="Collected By",
        ondelete="set null",
    )
    collected_at = fields.Datetime(string="Collected At")
    cancel_reason = fields.Text(string="Cancellation Reason")
    result_ids = fields.One2many(
        comodel_name="hospital.lab.result",
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
                    "hospital.lab.order"
                ) or _("New")
        return super().create(vals_list)

    def action_collect_sample(self):
        """Transition ordered -> sample_collected."""
        for order in self:
            if order.state != "ordered":
                raise UserError(
                    _("Only orders in 'Ordered' state can have their "
                      "sample collected. Order %s is in state '%s'.")
                    % (order.name, order.state)
                )
            order.write({
                "state": "sample_collected",
                "collected_by": self.env.uid,
                "collected_at": fields.Datetime.now(),
            })
        return True

    def action_processing(self):
        """Transition sample_collected -> processing."""
        for order in self:
            if order.state != "sample_collected":
                raise UserError(
                    _("Only orders with a collected sample can be moved to "
                      "processing. Order %s is in state '%s'.")
                    % (order.name, order.state)
                )
            order.state = "processing"
        return True

    def action_complete(self):
        """Transition processing -> completed and notify the ordering doctor.

        Creates a ``mail.activity`` (type: todo) on the visit's doctor
        user so the doctor knows lab results are ready, per
        Phase 6 §7 OrderCompletionNotifyService.
        """
        for order in self:
            if order.state != "processing":
                raise UserError(
                    _("Only orders in 'Processing' state can be completed. "
                      "Order %s is in state '%s'.")
                    % (order.name, order.state)
                )
            order.state = "completed"
            order._notify_doctor_on_completion()
        return True

    def action_cancel(self, reason=None):
        """Cancel the order. Requires a reason (enforced by the wizard)."""
        for order in self:
            if order.state == "completed":
                raise UserError(
                    _("A completed lab order cannot be cancelled. "
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
        """Open the cancel wizard dialog for this lab order."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cancel Lab Order"),
            "res_model": "hospital.lab.order.cancel.wizard",
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
            "res_model_id": self.env["ir.model"]._get_id("hospital.lab.order"),
            "res_id": self.id,
            "user_id": doctor_user.id,
            "summary": _("Lab results ready for %s") % self.test_id.name,
            "note": _(
                "Lab order %s (%s) has been completed. "
                "Please review the results."
            ) % (self.name, self.test_id.name),
        })
