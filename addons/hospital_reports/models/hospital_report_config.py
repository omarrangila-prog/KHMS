# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalReportConfig(models.Model):
    """Per-company report branding configuration.

    Singleton per company: the data XML seeds one row for the default company
    via ``ensure_one_per_company()``.  Admin users reach it via
    Settings > Report Branding.
    """

    _name = "hospital.report.config"
    _description = "Hospital Report Branding Configuration"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.company,
        index=True,
    )
    logo = fields.Binary(
        string="Report Logo",
        attachment=True,
        help="Override the company logo used on printed reports. "
             "Leave blank to fall back to the company's default logo.",
    )
    header_text = fields.Char(
        string="Report Header",
        default="Hospital Management System",
        help="Short text printed in the header of every hospital report.",
    )
    footer_text = fields.Char(
        string="Report Footer",
        default="Thank you for choosing our hospital.",
        help="Text printed in the footer of every hospital report.",
    )
    primary_color = fields.Char(
        string="Primary Colour (hex)",
        default="#2c7be5",
        help="CSS hex colour used as the accent colour in printed reports.",
    )
    show_company_address = fields.Boolean(
        string="Show Company Address",
        default=True,
    )
    show_patient_photo = fields.Boolean(
        string="Show Patient Photo",
        default=False,
        help="Include the patient's avatar in per-patient reports when available.",
    )

    _sql_constraints = [
        (
            "company_uniq",
            "UNIQUE(company_id)",
            "A report branding configuration already exists for this company.",
        ),
    ]

    @api.model
    def get_config(self, company_id=None):
        """Return the config record for *company_id* (or the current company).

        Creates a default row if none exists yet (safe for demo/test runs that
        don't load the seed data file).
        """
        company_id = company_id or self.env.company.id
        config = self.search([("company_id", "=", company_id)], limit=1)
        if not config:
            config = self.create({"company_id": company_id})
        return config
