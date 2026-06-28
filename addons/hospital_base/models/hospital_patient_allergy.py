# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalPatientAllergy(models.Model):
    _name = "hospital.patient.allergy"
    _description = "Hospital Patient Allergy"
    _order = "severity desc, name"

    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(string="Allergy", required=True)
    severity = fields.Selection(
        selection=[
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
        ],
        string="Severity",
        required=True,
        default="mild",
    )
    notes = fields.Text(string="Notes")
