# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HospitalPrescriptionLine(models.Model):
    """Prescription line (Phase 5 §3.5).

    DESIGN NOTE -- ``medicine_id`` references ``product.product``
    directly rather than a ``hospital.medicine`` extension model: Phase 5
    §3.3 defines ``hospital.medicine`` as a ``product.template``
    extension (generic_name/dosage_form/strength/etc.), but per Phase 6
    §6 that extension is owned by ``hospital_inventory`` (not yet built),
    and per Phase 4 §2's dependency graph ``hospital_inventory`` depends
    on ``hospital_base`` + ``stock`` -- NOT on ``hospital_doctor`` --
    while ``hospital_pharmacy`` depends on both ``hospital_doctor`` AND
    ``hospital_inventory``. If this module depended on
    ``hospital_inventory`` to get the clinical medicine fields, it would
    invert that graph. Depending on bare ``product`` (a lightweight,
    always-available Odoo base app, not the full ``stock`` app) lets this
    module reference ``product.product`` today; ``hospital_inventory``
    will layer the clinical fields onto ``product.template`` later via
    ``_inherit``, and ``hospital_pharmacy``/``hospital_inventory`` view
    inheritance will add stock-availability badges onto this same line
    view once ``stock`` is actually in the dependency graph (see README).

    ``qty_dispensed`` and ``state`` define the fields/states
    ``hospital_pharmacy`` will drive via its own dispense methods added
    through ``_inherit`` -- no dispense business logic is implemented
    here, only the data shape it will operate on.
    """

    _name = "hospital.prescription.line"
    _description = "Hospital Prescription Line"
    _order = "id"

    prescription_id = fields.Many2one(
        comodel_name="hospital.prescription",
        string="Prescription",
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
    route = fields.Selection(
        selection=[
            ("oral", "Oral"),
            ("iv", "IV"),
            ("im", "IM"),
            ("topical", "Topical"),
            ("other", "Other"),
        ],
        string="Route",
        default="oral",
    )
    qty_prescribed = fields.Float(string="Qty Prescribed", default=1.0)
    qty_dispensed = fields.Float(
        string="Qty Dispensed",
        default=0.0,
        readonly=True,
        help="Driven by hospital_pharmacy's dispense methods (added via "
             "_inherit) -- not editable here.",
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("dispensed", "Dispensed"),
            ("partial", "Partial"),
            ("backordered", "Backordered"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        index=True,
    )
    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        related="prescription_id.visit_id",
        store=True,
        index=True,
    )

    @api.constrains("qty_dispensed", "qty_prescribed")
    def _check_qty_dispensed_not_exceed_prescribed(self):
        for line in self:
            if line.qty_dispensed > line.qty_prescribed:
                raise ValidationError(
                    _("Dispensed quantity (%(dispensed)s) cannot exceed "
                      "the prescribed quantity (%(prescribed)s) for %(medicine)s.")
                    % {
                        "dispensed": line.qty_dispensed,
                        "prescribed": line.qty_prescribed,
                        "medicine": line.medicine_id.display_name,
                    }
                )

    @api.constrains("qty_prescribed")
    def _check_qty_prescribed_positive(self):
        for line in self:
            if line.qty_prescribed <= 0:
                raise ValidationError(
                    _("Prescribed quantity must be greater than zero."))
