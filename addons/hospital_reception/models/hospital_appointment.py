# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalAppointment(models.Model):
    """Pre-booked OPD appointment.

    An appointment is a lightweight scheduling record that pre-fills the
    doctor/department for a future visit. It only becomes a real
    ``hospital.visit`` (the spine record owned by ``hospital_base``) when
    the patient actually checks in -- per Phase 3 §2, "Walk-in with no
    appointment vs. pre-booked appointment ... both converge to the same
    ``waiting_nurse`` state; appointment just pre-fills ``doctor_id``."
    """

    _name = "hospital.appointment"
    _description = "Hospital Appointment"
    _order = "scheduled_datetime"

    name = fields.Char(
        string="Appointment Reference",
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
    )
    doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Doctor",
        ondelete="restrict",
        index=True,
    )
    department_id = fields.Many2one(
        comodel_name="hospital.department",
        string="Department",
        ondelete="restrict",
        index=True,
    )
    scheduled_datetime = fields.Datetime(
        string="Scheduled Date/Time",
        required=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("checked_in", "Checked In"),
            ("no_show", "No Show"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="draft",
        index=True,
    )
    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        copy=False,
        readonly=True,
        help="Set automatically when the patient checks in.",
    )
    notes = fields.Text(string="Notes")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hospital.appointment"
                ) or _("New")
        return super().create(vals_list)

    def action_confirm(self):
        for appointment in self:
            if appointment.state != "draft":
                raise UserError(
                    _("Only draft appointments can be confirmed.")
                )
            appointment.state = "confirmed"
        return True

    def action_check_in(self):
        """Check the patient in: create the ``hospital.visit`` and move it
        straight to ``waiting_nurse`` via its own ``action_confirm`` (Phase
        3 §2 -- appointments and walk-ins converge on the same nurse queue
        state), then link it back onto the appointment.
        """
        Visit = self.env["hospital.visit"]
        for appointment in self:
            if appointment.state not in ("draft", "confirmed"):
                raise UserError(
                    _("Only a draft or confirmed appointment can be "
                      "checked in.")
                )
            visit = Visit.create(
                {
                    "patient_id": appointment.patient_id.id,
                    "visit_type": "opd",
                    "doctor_id": appointment.doctor_id.id,
                    "department_id": appointment.department_id.id,
                }
            )
            visit.action_confirm()
            appointment.write(
                {
                    "visit_id": visit.id,
                    "state": "checked_in",
                }
            )
        return True

    def action_no_show(self):
        for appointment in self:
            if appointment.state not in ("draft", "confirmed"):
                raise UserError(
                    _("Only a draft or confirmed appointment can be "
                      "marked as a no-show.")
                )
            appointment.state = "no_show"
        return True

    def action_cancel(self):
        for appointment in self:
            if appointment.state == "checked_in":
                raise UserError(
                    _("A checked-in appointment cannot be cancelled; "
                      "cancel the linked visit instead.")
                )
            appointment.state = "cancelled"
        return True
