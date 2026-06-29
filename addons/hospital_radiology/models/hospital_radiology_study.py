# -*- coding: utf-8 -*-
from odoo import _, fields, models


class HospitalRadiologyStudy(models.Model):
    """Catalog of radiology imaging studies offered by the hospital.

    Each study has a modality, price, and optional product link for billing.
    The ``product_id`` billing-hook-stub pattern mirrors hospital_lab's
    ``hospital.lab.test.product_id``.
    """

    _name = "hospital.radiology.study"
    _description = "Radiology Study Catalog"
    _order = "name"

    name = fields.Char(
        string="Study Name",
        required=True,
        index=True,
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
    )
    modality = fields.Selection(
        selection=[
            ("xray", "X-Ray"),
            ("ct", "CT Scan"),
            ("mri", "MRI"),
            ("ultrasound", "Ultrasound"),
            ("mammography", "Mammography"),
            ("other", "Other"),
        ],
        string="Modality",
        required=True,
        default="xray",
    )
    price = fields.Float(
        string="Price",
        digits=(10, 2),
    )
    description = fields.Text(string="Description / Preparation Instructions")
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Billing Product",
        ondelete="set null",
        domain=[("type", "=", "service")],
        help="Service product for consolidated billing (stub — actual "
             "invoicing logic belongs in hospital_billing).",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            "code_company_uniq",
            "UNIQUE(code, company_id)",
            "A radiology study with this code already exists for this company.",
        ),
    ]
