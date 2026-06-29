# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalWard(models.Model):
    """Ward master data (Phase 5 §5.1).

    ``daily_rate`` is the per-night room charge used by
    ``hospital.discharge``'s length-of-stay billing computation
    (Phase 6 §9 LengthOfStayBillingService).
    """

    _name = "hospital.ward"
    _description = "Hospital Ward"
    _order = "name"

    name = fields.Char(string="Ward Name", required=True, index=True)
    code = fields.Char(string="Code", required=True, index=True)
    ward_type = fields.Selection(
        selection=[
            ("general", "General"),
            ("icu", "ICU"),
            ("maternity", "Maternity"),
            ("pediatric", "Pediatric"),
            ("isolation", "Isolation"),
        ],
        string="Ward Type",
        required=True,
        default="general",
        index=True,
    )
    daily_rate = fields.Monetary(
        string="Daily Rate",
        required=True,
        currency_field="currency_id",
        help="Per-night room charge billed against the admission's "
             "length of stay on discharge.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    bed_ids = fields.One2many(
        comodel_name="hospital.bed",
        inverse_name="ward_id",
        string="Beds",
    )
    bed_count = fields.Integer(
        string="Total Beds",
        compute="_compute_bed_stats",
    )
    occupied_bed_count = fields.Integer(
        string="Occupied Beds",
        compute="_compute_bed_stats",
    )
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            "hospital_ward_code_uniq",
            "unique(code)",
            "Ward code must be unique.",
        ),
    ]

    def _compute_bed_stats(self):
        for ward in self:
            ward.bed_count = len(ward.bed_ids)
            ward.occupied_bed_count = len(
                ward.bed_ids.filtered(lambda bed: bed.state == "occupied")
            )

    def _compute_display_name(self):
        for ward in self:
            ward.display_name = (
                "%s (%s)" % (ward.name, ward.code) if ward.code else ward.name
            )
