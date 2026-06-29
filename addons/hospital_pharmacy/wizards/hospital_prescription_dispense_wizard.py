# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalPrescriptionDispenseWizardLine(models.TransientModel):
    """One row in the dispense wizard per prescription line (Phase 8 §12).

    Carries the per-line dispense parameters (quantity to dispense, allergy
    override flag + reason) alongside display-only fields the pharmacist
    needs to make the decision (stock on hand, allergy conflict flag).
    """

    _name = "hospital.prescription.dispense.wizard.line"
    _description = "Dispense Wizard Line"

    wizard_id = fields.Many2one(
        comodel_name="hospital.prescription.dispense.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    prescription_line_id = fields.Many2one(
        comodel_name="hospital.prescription.line",
        string="Prescription Line",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    medicine_id = fields.Many2one(
        comodel_name="product.product",
        string="Medicine",
        related="prescription_line_id.medicine_id",
        readonly=True,
    )
    qty_prescribed = fields.Float(
        string="Qty Prescribed",
        related="prescription_line_id.qty_prescribed",
        readonly=True,
    )
    qty_dispensed_so_far = fields.Float(
        string="Already Dispensed",
        related="prescription_line_id.qty_dispensed",
        readonly=True,
    )
    qty_to_dispense = fields.Float(
        string="Qty to Dispense",
        default=0.0,
        help="How many units to dispense in this wizard call. Defaults to "
             "the remaining outstanding quantity.",
    )
    qty_on_hand = fields.Float(
        string="Stock on Hand",
        compute="_compute_qty_on_hand",
        help="Current quantity available at the Pharmacy stock location.",
    )
    line_state = fields.Selection(
        related="prescription_line_id.state",
        readonly=True,
    )
    has_allergy_conflict = fields.Boolean(
        related="prescription_line_id.has_allergy_conflict",
        readonly=True,
    )
    override_allergy = fields.Boolean(
        string="Override Allergy Warning",
        default=False,
    )
    override_reason = fields.Text(
        string="Override Reason",
        help="Mandatory justification when overriding an allergy conflict.",
    )

    @api.depends("medicine_id")
    def _compute_qty_on_hand(self):
        pharmacy_location = self.env.ref(
            "hospital_inventory.stock_location_pharmacy_store",
            raise_if_not_found=False,
        )
        for wline in self:
            if not wline.medicine_id or not pharmacy_location:
                wline.qty_on_hand = 0.0
            else:
                wline.qty_on_hand = (
                    wline.medicine_id.with_context(
                        location=pharmacy_location.id
                    ).qty_available
                )

    @api.model
    def default_get(self, field_list):
        defaults = super().default_get(field_list)
        return defaults


class HospitalPrescriptionDispenseWizard(models.TransientModel):
    """Batch-dispense wizard (Phase 8 §12, Phase 3 §5).

    Opened from the prescription form (or the Pharmacy Dashboard OWL
    action) with ``active_id`` pointing at a ``hospital.prescription``.
    Pre-populates one wizard line per non-cancelled, not-yet-fully-
    dispensed prescription line with the outstanding quantity defaulted in
    ``qty_to_dispense``.

    Handles the allergy-conflict override flow: if any line has a
    conflict, a warning banner is shown (via ``has_any_allergy_conflict``);
    per-line ``override_allergy`` + ``override_reason`` let the
    pharmacist approve each conflicting line individually before confirming.
    """

    _name = "hospital.prescription.dispense.wizard"
    _description = "Dispense Prescription Wizard"

    prescription_id = fields.Many2one(
        comodel_name="hospital.prescription",
        string="Prescription",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        related="prescription_id.patient_id",
        readonly=True,
    )
    wizard_line_ids = fields.One2many(
        comodel_name="hospital.prescription.dispense.wizard.line",
        inverse_name="wizard_id",
        string="Lines",
    )
    has_any_allergy_conflict = fields.Boolean(
        string="Allergy Conflict(s) Present",
        compute="_compute_has_any_allergy_conflict",
    )

    @api.depends("wizard_line_ids.has_allergy_conflict")
    def _compute_has_any_allergy_conflict(self):
        for wizard in self:
            wizard.has_any_allergy_conflict = any(
                wl.has_allergy_conflict for wl in wizard.wizard_line_ids
            )

    @api.model
    def default_get(self, field_list):
        defaults = super().default_get(field_list)
        active_id = self.env.context.get("active_id")
        if active_id and "prescription_id" in field_list:
            defaults["prescription_id"] = active_id
        return defaults

    def _compute_default_wizard_lines(self):
        """Build wizard lines for all actionable prescription lines."""
        self.ensure_one()
        if not self.prescription_id:
            return []
        lines = self.prescription_id.line_ids.filtered(
            lambda l: l.state not in ("dispensed", "cancelled")
        )
        return [
            (
                0,
                0,
                {
                    "prescription_line_id": line.id,
                    "qty_to_dispense": max(
                        0.0, line.qty_prescribed - line.qty_dispensed
                    ),
                },
            )
            for line in lines
        ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for wizard in records:
            if not wizard.wizard_line_ids and wizard.prescription_id:
                wizard.wizard_line_ids = wizard._compute_default_wizard_lines()
        return records

    def action_dispense(self):
        """Execute the dispense for all wizard lines.

        Validates that any conflicting line with ``override_allergy``
        checked also has a non-empty ``override_reason``, then calls
        :meth:`hospital.prescription.line.dispense` on each line.
        """
        self.ensure_one()
        if not self.wizard_line_ids:
            raise UserError(_("Nothing to dispense -- add at least one line."))
        for wline in self.wizard_line_ids:
            if wline.line_state in ("dispensed", "cancelled"):
                continue
            if wline.qty_to_dispense <= 0:
                continue
            if wline.has_allergy_conflict and wline.override_allergy:
                if not wline.override_reason or not wline.override_reason.strip():
                    raise UserError(
                        _("An override reason is required for %(medicine)s "
                          "because it conflicts with the patient's recorded "
                          "allergies.")
                        % {"medicine": wline.medicine_id.display_name}
                    )
            wline.prescription_line_id.dispense(
                qty=wline.qty_to_dispense,
                override_allergy=wline.override_allergy,
                override_reason=wline.override_reason,
            )
        return {"type": "ir.actions.act_window_close"}

    def action_dispense_all(self):
        """Set every pending line's ``qty_to_dispense`` to its full
        outstanding quantity, then call :meth:`action_dispense`. This is
        the backend equivalent of the "A" shortcut on the Pharmacy
        Dashboard (Phase 8 §12).
        """
        self.ensure_one()
        for wline in self.wizard_line_ids:
            if wline.line_state not in ("dispensed", "cancelled"):
                wline.qty_to_dispense = max(
                    0.0,
                    wline.qty_prescribed - wline.qty_dispensed_so_far,
                )
        return self.action_dispense()
