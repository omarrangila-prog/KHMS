# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalDischargeMedication(models.Model):
    """Discharge medication line (Phase 5 §5.5: "discharge_medication_ids
    (One2many, reuses prescription-line-like structure)").

    Kept as its own small model rather than reusing
    ``hospital.prescription.line`` directly: a discharge medication is a
    "take this at home" instruction printed on the summary, not a
    pharmacy-dispensable order tied to stock -- it does not need
    ``qty_dispensed``/``stock_move_id``/dispense state. This mirrors the
    same "small child table, not a comma-field" reasoning Phase 5 §1.2
    uses for patient allergies/conditions.
    """

    _name = "hospital.discharge.medication"
    _description = "Hospital Discharge Medication"
    _order = "id"

    discharge_id = fields.Many2one(
        comodel_name="hospital.discharge",
        string="Discharge",
        required=True,
        ondelete="cascade",
        index=True,
    )
    medicine_id = fields.Many2one(
        comodel_name="product.product",
        string="Medicine",
        required=True,
        ondelete="restrict",
        index=True,
    )
    dosage = fields.Char(string="Dosage", help='e.g. "500mg"')
    frequency = fields.Char(string="Frequency", help='e.g. "TID"')
    duration_days = fields.Integer(string="Duration (days)")
    instructions = fields.Char(string="Instructions")
