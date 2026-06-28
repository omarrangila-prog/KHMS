# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HospitalVisit(models.Model):
    """The spine record of the whole system.

    NOTE: ``prescription_ids``, ``lab_order_ids``, ``radiology_order_ids``,
    ``admission_id`` and ``invoice_id`` (Phase 5 §1.3) are intentionally NOT
    defined here. Those target models (``hospital.prescription``,
    ``hospital.lab.order``, ``hospital.radiology.order``,
    ``hospital.ipd.admission``, ``account.move``) belong to later modules
    (``hospital_doctor``, ``hospital_pharmacy``, ``hospital_lab``,
    ``hospital_radiology``, ``hospital_ipd``) in the build order (Phase 12).
    Those modules will add the fields back onto this model via
    ``_inherit`` once their target models exist, per Phase 6 §1 scope.
    """

    _name = "hospital.visit"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Hospital Visit"
    _order = "checkin_datetime desc"

    visit_code = fields.Char(
        string="Visit Code",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    visit_type = fields.Selection(
        selection=[
            ("opd", "Outpatient (OPD)"),
            ("ipd", "Inpatient (IPD)"),
        ],
        string="Visit Type",
        required=True,
        default="opd",
    )
    doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Doctor",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    department_id = fields.Many2one(
        comodel_name="hospital.department",
        string="Department",
        ondelete="restrict",
        index=True,
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
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("waiting_nurse", "Waiting for Nurse"),
            ("waiting_doctor", "Waiting for Doctor"),
            ("in_progress_multi", "In Progress (Multi-Department)"),
            ("admitted", "Admitted"),
            ("billing", "Billing"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("void", "Void"),
        ],
        string="Status",
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    checkin_datetime = fields.Datetime(
        string="Check-in Date/Time",
        required=True,
        default=fields.Datetime.now,
    )
    payer_type = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("insurance", "Insurance"),
        ],
        string="Payer Type",
        default="cash",
    )
    cancel_reason = fields.Text(string="Cancellation Reason")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            "hospital_visit_code_uniq",
            "unique(visit_code)",
            "Visit code must be unique.",
        ),
    ]

    def init(self):
        """Composite index backing the literal queue-sort query
        (state, priority, checkin_datetime) per Phase 5 §1.3.
        """
        self.env.cr.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = %s",
            ("hospital_visit_state_priority_checkin_idx",),
        )
        if not self.env.cr.fetchone():
            self.env.cr.execute(
                "CREATE INDEX hospital_visit_state_priority_checkin_idx "
                "ON hospital_visit (state, priority, checkin_datetime)"
            )

    @api.constrains("state", "cancel_reason")
    def _check_cancel_reason(self):
        for visit in self:
            if visit.state == "cancelled" and not visit.cancel_reason:
                raise ValidationError(
                    _("A cancellation reason is required to cancel a visit.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("visit_code") or vals.get("visit_code") == _("New"):
                vals["visit_code"] = self.env["ir.sequence"].next_by_code(
                    "hospital.visit"
                ) or _("New")
        return super().create(vals_list)

    def action_confirm(self):
        """Move a draft visit into the front-line nurse/doctor queue."""
        for visit in self:
            if visit.state != "draft":
                raise UserError(
                    _("Only draft visits can be confirmed.")
                )
            visit.state = "waiting_nurse"
        return True

    def action_send_to_doctor(self):
        for visit in self:
            if visit.state not in ("waiting_nurse", "in_progress_multi"):
                raise UserError(
                    _("The visit must be waiting on the nurse queue before "
                      "it can be sent to the doctor.")
                )
            visit.state = "waiting_doctor"
        return True

    def action_admit(self):
        for visit in self:
            if visit.visit_type != "ipd":
                raise UserError(
                    _("Only inpatient (IPD) visits can be admitted."))
            visit.state = "admitted"
        return True

    def action_to_billing(self):
        for visit in self:
            if visit.state in ("cancelled", "void"):
                raise UserError(
                    _("A cancelled or void visit cannot move to billing."))
            visit.state = "billing"
        return True

    def action_done(self):
        for visit in self:
            visit.state = "done"
        return True

    def action_cancel(self):
        for visit in self:
            if not visit.cancel_reason:
                raise UserError(
                    _("Please provide a cancellation reason before "
                      "cancelling the visit.")
                )
            visit.state = "cancelled"
        return True

    def action_void(self):
        for visit in self:
            visit.state = "void"
        return True
