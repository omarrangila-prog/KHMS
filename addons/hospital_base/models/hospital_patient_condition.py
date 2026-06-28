# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalPatientCondition(models.Model):
    _name = "hospital.patient.condition"
    _description = "Hospital Patient Chronic Condition"
    _order = "diagnosed_date desc, name"

    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(string="Condition", required=True)
    diagnosed_date = fields.Date(string="Diagnosed Date")
    notes = fields.Text(string="Notes")
