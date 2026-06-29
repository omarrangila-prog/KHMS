# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalCensusWizard(models.TransientModel):
    """Wizard that selects a date range and triggers the Daily Census report."""

    _name = "hospital.census.wizard"
    _description = "Daily Census Report Wizard"

    date_from = fields.Date(
        string="From",
        required=True,
        default=fields.Date.today,
    )
    date_to = fields.Date(
        string="To",
        required=True,
        default=fields.Date.today,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                from odoo import _
                from odoo.exceptions import ValidationError
                raise ValidationError(_("'From' date must be on or before 'To' date."))

    def action_print_census(self):
        self.ensure_one()
        visits = self.env["hospital.visit"].search([
            ("company_id", "=", self.company_id.id),
            ("checkin_datetime", ">=", fields.Datetime.to_datetime(self.date_from)),
            ("checkin_datetime", "<", fields.Datetime.to_datetime(self.date_to) + __import__("datetime").timedelta(days=1)),
        ], order="checkin_datetime asc")
        return self.env.ref(
            "hospital_reports.action_hospital_daily_census_report"
        ).report_action(visits, data={
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
        })
