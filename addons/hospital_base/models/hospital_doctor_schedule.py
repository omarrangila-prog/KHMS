# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HospitalDoctorSchedule(models.Model):
    _name = "hospital.doctor.schedule"
    _description = "Hospital Doctor Weekly Schedule"
    _order = "doctor_id, weekday, start_time"

    doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Doctor",
        required=True,
        ondelete="cascade",
        index=True,
    )
    weekday = fields.Selection(
        selection=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
    )
    start_time = fields.Float(string="Start Time", required=True)
    end_time = fields.Float(string="End Time", required=True)
    max_patients = fields.Integer(string="Max Patients", default=0)

    @api.constrains("start_time", "end_time")
    def _check_time_range(self):
        for schedule in self:
            if schedule.start_time >= schedule.end_time:
                raise ValidationError(
                    _("Start time must be earlier than end time.")
                )

    @api.constrains("max_patients")
    def _check_max_patients(self):
        for schedule in self:
            if schedule.max_patients < 0:
                raise ValidationError(
                    _("Max patients cannot be negative.")
                )
