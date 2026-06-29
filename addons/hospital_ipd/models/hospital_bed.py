# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalBed(models.Model):
    """A single bed within a ward (Phase 5 §5.2).

    The critical "no double-booked bed" invariant (Phase 3 FR-33, Phase 5
    §5.2) is enforced at the DATABASE level by a partial unique index on
    ``hospital.ipd.admission`` (``bed_id`` unique where ``state =
    'admitted'``), not here -- see ``hospital_ipd_admission.py``'s
    ``init()`` hook. ``state`` on this model is a denormalized convenience
    field for dashboard/list display and queue filtering; it is kept in
    sync by the admission/transfer/discharge action methods, but the real
    source of truth for "is this bed double-booked" is the partial index.
    """

    _name = "hospital.bed"
    _description = "Hospital Bed"
    _order = "ward_id, bed_number"

    ward_id = fields.Many2one(
        comodel_name="hospital.ward",
        string="Ward",
        required=True,
        ondelete="restrict",
        index=True,
    )
    bed_number = fields.Char(string="Bed Number", required=True)
    state = fields.Selection(
        selection=[
            ("vacant", "Vacant"),
            ("occupied", "Occupied"),
            ("reserved", "Reserved"),
            ("cleaning", "Cleaning"),
        ],
        string="Status",
        required=True,
        default="vacant",
        index=True,
    )
    current_admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Current Admission",
        ondelete="set null",
        index=True,
    )
    current_patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Current Patient",
        related="current_admission_id.patient_id",
        store=False,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="ward_id.company_id",
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            "hospital_bed_ward_number_uniq",
            "unique(ward_id, bed_number)",
            "Bed number must be unique within a ward.",
        ),
    ]

    def _compute_display_name(self):
        for bed in self:
            bed.display_name = "%s - Bed %s" % (bed.ward_id.name, bed.bed_number)
