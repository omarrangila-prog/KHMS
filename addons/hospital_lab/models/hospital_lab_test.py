# -*- coding: utf-8 -*-
from odoo import _, fields, models


class HospitalLabTest(models.Model):
    """Catalog of laboratory tests offered by the hospital.

    Each test carries its own normal-range reference values (min/max).
    On order creation the range is copied to the result lines so results
    remain interpretable even if the catalog entry is later updated.

    The optional ``product_id`` link to a ``product.product`` service
    record follows the same billing-hook-stub pattern used in
    ``hospital_pharmacy``: the product exists for future consolidated
    invoicing by ``hospital_billing``; no financial logic lives here.
    """

    _name = "hospital.lab.test"
    _description = "Lab Test Catalog"
    _order = "name"

    name = fields.Char(
        string="Test Name",
        required=True,
        index=True,
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
    )
    sample_type = fields.Selection(
        selection=[
            ("blood", "Blood"),
            ("urine", "Urine"),
            ("stool", "Stool"),
            ("swab", "Swab"),
            ("other", "Other"),
        ],
        string="Sample Type",
        required=True,
        default="blood",
    )
    price = fields.Float(
        string="Price",
        digits=(10, 2),
    )
    normal_range_min = fields.Float(
        string="Normal Range Min",
        help="Lower bound of the normal reference range (inclusive).",
    )
    normal_range_max = fields.Float(
        string="Normal Range Max",
        help="Upper bound of the normal reference range (inclusive).",
    )
    description = fields.Text(string="Description / Instructions")
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Billing Product",
        ondelete="set null",
        domain=[("type", "=", "service")],
        help="Service product used for consolidated billing (stub — "
             "actual invoicing logic belongs in hospital_billing).",
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
            "A lab test with this code already exists for this company.",
        ),
    ]
