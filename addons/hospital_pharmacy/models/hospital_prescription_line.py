# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

PHARMACY_LOCATION_XMLID = "hospital_inventory.stock_location_pharmacy_store"
CONSUMPTION_LOCATION_XMLID = "hospital_pharmacy.stock_location_patient_consumption"


class HospitalPrescriptionLine(models.Model):
    """Dispense methods for the prescription line (Phase 3 §5, Phase 6 §5).

    ``hospital_doctor`` deliberately left ``qty_dispensed`` readonly and
    every dispense-driven ``state`` transition undriven, documenting that
    "hospital_pharmacy will add the dispense methods via _inherit later".
    This is that extension: :meth:`dispense` is the single entry point a
    pharmacist (directly, or via
    ``hospital.prescription.dispense.wizard``) calls to action a line.

    DISPENSE CONTRACT (read this before any future module touches a
    prescription line's stock/state fields):

    1. **Allergy safety check** (``DispensingSafetyService``, Phase 3 §5
       step C): :meth:`_check_allergy_conflict` compares the medicine's
       name/generic name against the patient's
       ``hospital.patient.allergy_ids`` using a simple case-insensitive
       substring match -- the PRD explicitly scopes out a formal
       drug-allergy ontology, so this is the documented, intentional
       level of sophistication. A conflict raises ``UserError`` unless
       ``override_allergy=True`` is passed, in which case the override and
       its mandatory ``override_reason`` are persisted on the line (for
       traceability on this exact dispense event) and separately
       audit-logged via ``hospital.audit.log`` (the line's own
       ``hospital.audit.mixin`` "write" entry already covers normal field
       changes, but the override is significant enough -- a clinical
       safety gate being bypassed -- to also get its own explicit,
       human-readable audit row).
    2. **Stock check** (``StockMoveCreationService``): reads on-hand
       quantity at the Pharmacy stock location
       (``hospital_inventory.stock_location_pharmacy_store``). The
       quantity actually dispensable this call is
       ``min(qty requested, qty on hand)``.
    3. **Stock move**: a real ``stock.move`` is created, confirmed,
       assigned, and validated moving the dispensable quantity from the
       Pharmacy location to the "Patient Consumption" virtual location
       added by this module's data file
       (``hospital_pharmacy.stock_location_patient_consumption``) --
       dispensing a medicine is a real, auditable stock decrement, not a
       cosmetic field update.
    4. **State**: ``qty_dispensed`` accumulates; line ``state`` becomes
       ``dispensed`` once ``qty_dispensed == qty_prescribed``, ``partial``
       if some but not all of the *current* request was fulfillable
       (leaving a real shortfall against ``qty_prescribed``), or
       ``backordered`` if nothing could be dispensed at all this call.
    5. **Aggregate state propagation**: after the line is updated, the
       owning ``hospital.prescription`` recomputes its own ``state`` via
       the (pre-existing) ``_recompute_state_from_lines()`` helper, then
       ``hospital.visit.action_route_from_consultation()`` is called on
       the visit so the aggregate routing re-evaluates whether the
       prescription branch is now resolved. This is the exact mechanism
       ``hospital_doctor``'s ``hospital.visit._compute_pending_branches()``
       docstring says ``hospital_pharmacy`` does **not** need to extend --
       the prescription-branch pending check already queries
       ``hospital.prescription.state`` directly, so simply driving that
       state correctly and re-running the existing routing method is the
       whole integration; no new hook needed on ``hospital.visit`` itself.
    """

    _inherit = "hospital.prescription.line"

    override_reason = fields.Text(
        string="Allergy Override Reason",
        readonly=True,
        help="Mandatory justification captured when a pharmacist dispenses "
             "this line despite a detected allergy conflict. Kept on the "
             "line (in addition to the audit log entry) so the override is "
             "visible at a glance from the prescription itself.",
    )
    stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        string="Stock Move",
        readonly=True,
        copy=False,
        help="The stock.move created by the most recent dispense call on "
             "this line. A line dispensed across multiple partial calls "
             "only keeps the latest move reference here; the full stock "
             "history remains queryable on stock.move itself via "
             "product_id + the Pharmacy/Patient Consumption locations.",
    )
    has_allergy_conflict = fields.Boolean(
        string="Allergy Conflict",
        compute="_compute_has_allergy_conflict",
        help="True when the medicine's name/generic name matches one of "
             "the patient's recorded allergies (simple case-insensitive "
             "substring match, per PRD scope). Drives the warning banner "
             "on the dispense wizard and pharmacy dashboard.",
    )
    qty_on_hand_at_pharmacy = fields.Float(
        string="Stock at Pharmacy",
        compute="_compute_qty_on_hand_at_pharmacy",
        help="Current quantity on hand at the Pharmacy stock location "
             "(hospital_inventory.stock_location_pharmacy_store). "
             "Non-stored compute: always fresh from stock.quant.",
    )

    @api.depends("medicine_id")
    def _compute_qty_on_hand_at_pharmacy(self):
        pharmacy_location = self.env.ref(
            PHARMACY_LOCATION_XMLID, raise_if_not_found=False
        )
        for line in self:
            if not line.medicine_id or not pharmacy_location:
                line.qty_on_hand_at_pharmacy = 0.0
            else:
                line.qty_on_hand_at_pharmacy = (
                    line.medicine_id.with_context(
                        location=pharmacy_location.id
                    ).qty_available
                )

    def _compute_has_allergy_conflict(self):
        for line in self:
            line.has_allergy_conflict = bool(line._find_allergy_conflicts())

    def _find_allergy_conflicts(self):
        """Return the ``hospital.patient.allergy`` records that conflict
        with this line's medicine.

        Matching is deliberately simple (case-insensitive substring, both
        directions) since there is no formal drug-allergy ontology in this
        product's scope -- see the class docstring.
        """
        self.ensure_one()
        patient = self.prescription_id.visit_id.patient_id
        if not patient or not self.medicine_id:
            return self.env["hospital.patient.allergy"].browse()
        medicine_terms = [
            term.strip().lower()
            for term in (self.medicine_id.name, self.medicine_id.generic_name)
            if term
        ]
        if not medicine_terms:
            return self.env["hospital.patient.allergy"].browse()
        conflicts = self.env["hospital.patient.allergy"].browse()
        for allergy in patient.allergy_ids:
            allergy_term = (allergy.name or "").strip().lower()
            if not allergy_term:
                continue
            for medicine_term in medicine_terms:
                if allergy_term in medicine_term or medicine_term in allergy_term:
                    conflicts |= allergy
                    break
        return conflicts

    def _get_pharmacy_location(self):
        return self.env.ref(PHARMACY_LOCATION_XMLID)

    def _get_consumption_location(self):
        return self.env.ref(CONSUMPTION_LOCATION_XMLID)

    def _get_qty_on_hand(self):
        self.ensure_one()
        location = self._get_pharmacy_location()
        return self.medicine_id.with_context(location=location.id).qty_available

    def dispense(self, qty=None, override_allergy=False, override_reason=None):
        """Dispense up to ``qty`` units of this line (Phase 3 §5).

        :param qty: quantity to attempt to dispense this call. Defaults to
            the line's full outstanding quantity
            (``qty_prescribed - qty_dispensed``).
        :param override_allergy: if an allergy conflict is found, the call
            is blocked with ``UserError`` unless this is ``True``.
        :param override_reason: mandatory free-text justification when
            ``override_allergy`` is used; stored on the line and
            audit-logged.
        :return: ``True``.
        """
        for line in self:
            line._dispense_one(
                qty=qty,
                override_allergy=override_allergy,
                override_reason=override_reason,
            )
        return True

    def _dispense_one(self, qty, override_allergy, override_reason):
        self.ensure_one()
        if self.state in ("dispensed", "cancelled"):
            raise UserError(
                _("%(medicine)s is already %(state)s and cannot be "
                  "dispensed again.")
                % {
                    "medicine": self.medicine_id.display_name,
                    "state": self.state,
                }
            )

        outstanding = self.qty_prescribed - self.qty_dispensed
        if outstanding <= 0:
            raise UserError(
                _("Nothing left to dispense for %(medicine)s.")
                % {"medicine": self.medicine_id.display_name}
            )
        requested = outstanding if qty is None else min(qty, outstanding)
        if requested <= 0:
            raise UserError(_("Quantity to dispense must be greater than zero."))

        self._apply_allergy_safety_check(override_allergy, override_reason)

        qty_on_hand = self._get_qty_on_hand()
        qty_to_move = min(requested, qty_on_hand)

        if qty_to_move > 0:
            move = self._create_dispense_stock_move(qty_to_move)
            self.stock_move_id = move.id
            self.qty_dispensed += qty_to_move

        if self.qty_dispensed >= self.qty_prescribed:
            self.state = "dispensed"
        elif qty_to_move > 0:
            self.state = "partial"
        else:
            self.state = "backordered"

        if qty_to_move < requested:
            # Per Phase 3 §5: a shortfall (full or partial) triggers a
            # low/out-of-stock alert to the Inventory Manager, reusing
            # hospital_inventory's own LowStockAlertService activity
            # mechanism rather than inventing a parallel notification
            # channel (Phase 11 §1 "no duplicated business logic").
            self._notify_low_stock()

        if qty_to_move > 0:
            self._create_billing_line(qty_to_move)

        self.prescription_id._recompute_state_from_lines()
        self.visit_id.action_route_from_consultation()
        return True

    def _apply_allergy_safety_check(self, override_allergy, override_reason):
        self.ensure_one()
        conflicts = self._find_allergy_conflicts()
        if not conflicts:
            return
        if not override_allergy:
            raise UserError(
                _("%(medicine)s conflicts with a recorded allergy "
                  "(%(allergies)s) for this patient. Dispensing is "
                  "blocked unless a pharmacist explicitly overrides this "
                  "warning with a reason.")
                % {
                    "medicine": self.medicine_id.display_name,
                    "allergies": ", ".join(conflicts.mapped("name")),
                }
            )
        if not override_reason or not override_reason.strip():
            raise UserError(
                _("A reason is required to override the allergy conflict "
                  "for %(medicine)s.") % {"medicine": self.medicine_id.display_name}
            )
        self.override_reason = override_reason
        self._log_allergy_override(conflicts, override_reason)

    def _log_allergy_override(self, conflicts, override_reason):
        """Explicit, human-readable audit row for the override decision
        itself (on top of the field-level audit trail
        ``hospital.audit.mixin`` already produces on the ``write`` to
        ``override_reason``) -- a clinical safety gate being bypassed
        deserves its own clearly-labelled entry rather than being buried
        in a generic before/after field diff.
        """
        self.ensure_one()
        self.env["hospital.audit.log"].sudo().create(
            {
                "res_model": self._name,
                "res_id": self.id,
                "user_id": self.env.uid,
                "action": "write",
                "field_changes": (
                    '{"event": "allergy_override", "medicine": "%s", '
                    '"allergies": "%s", "reason": "%s"}'
                )
                % (
                    self.medicine_id.display_name,
                    ", ".join(conflicts.mapped("name")),
                    (override_reason or "").replace('"', "'"),
                ),
            }
        )

    def _create_dispense_stock_move(self, qty):
        self.ensure_one()
        pharmacy_location = self._get_pharmacy_location()
        consumption_location = self._get_consumption_location()
        move = self.env["stock.move"].create(
            {
                "name": _("Dispense: %(medicine)s for %(patient)s")
                % {
                    "medicine": self.medicine_id.display_name,
                    "patient": self.prescription_id.patient_id.display_name,
                },
                "product_id": self.medicine_id.id,
                "product_uom_qty": qty,
                "product_uom": self.medicine_id.uom_id.id,
                "location_id": pharmacy_location.id,
                "location_dest_id": consumption_location.id,
                "company_id": self.prescription_id.company_id.id
                or self.env.company.id,
                "origin": self.prescription_id.display_name,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.write({"quantity": qty, "picked": True})
        move._action_done()
        return move

    def _notify_low_stock(self):
        """Create a low-stock mail.activity for the inventory manager group
        when a dispense results in a shortfall (Phase 3 §5).

        Creates one activity per affected product, skipping products that
        already have a pending "Medicine Stock Below Reorder Threshold"
        activity (idempotent, consistent with the cron in
        ``hospital_inventory``). Only fires when the product has a
        ``reorder_threshold`` field (i.e. ``hospital_inventory`` is
        installed and has extended ``product.template`` with that field).
        """
        self.ensure_one()
        template = self.medicine_id.product_tmpl_id
        reorder_threshold = getattr(template, "reorder_threshold", None)
        qty_now = self._get_qty_on_hand()
        if reorder_threshold is None or qty_now > reorder_threshold:
            return
        existing = self.env["mail.activity"].search(
            [
                ("res_model", "=", "product.template"),
                ("res_id", "=", template.id),
                ("summary", "=", "Medicine Stock Below Reorder Threshold"),
            ],
            limit=1,
        )
        if existing:
            return
        managers = self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager",
            raise_if_not_found=False,
        )
        users = managers.users if managers else self.env["res.users"]
        if not users:
            return
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        product_model_id = self.env["ir.model"]._get_id("product.template")
        for user in users:
            self.env["mail.activity"].create(
                {
                    "res_model_id": product_model_id,
                    "res_id": template.id,
                    "activity_type_id": activity_type.id if activity_type else False,
                    "summary": "Medicine Stock Below Reorder Threshold",
                    "note": (
                        "%(medicine)s is at %(qty).2f on hand (below reorder "
                        "threshold of %(threshold).2f) after dispensing for "
                        "patient %(patient)s."
                    )
                    % {
                        "medicine": self.medicine_id.display_name,
                        "qty": qty_now,
                        "threshold": reorder_threshold,
                        "patient": self.prescription_id.patient_id.display_name,
                    },
                    "user_id": user.id,
                }
            )

    def _create_billing_line(self, qty):
        """Extension point for the billing line Phase 3 §5 (FR-25 region)
        expects on every successful dispense.

        DELIBERATELY A NO-OP TODAY. Per Phase 5 §1.3, ``hospital.visit``
        will eventually carry an ``invoice_id`` (Many2one ->
        ``account.move``), and Phase 5 §6 says every billable event writes
        an ``account.move.line`` onto a draft ``account.move`` keyed by
        the visit/admission -- but no module in the build order so far
        (``hospital_base`` through ``hospital_inventory``) has built that
        ``account.move`` integration, and Phase 6's module breakdown does
        not assign it to ``hospital_pharmacy`` either (billing/invoicing
        ownership is not yet assigned to a specific module). Inventing
        invoicing logic here -- before the module that actually owns
        ``hospital.visit.invoice_id`` exists -- would mean guessing a
        contract that module hasn't defined yet, and likely conflicting
        with it later. Instead, this method is called at exactly the
        right point in the dispense flow (after a successful stock move,
        with the real dispensed quantity), is clearly named/documented as
        the billing extension point, and does nothing yet. Whichever
        future module (most likely ``hospital_reports`` or a dedicated
        billing module) adds real ``account.move``/``account.move.line``
        creation should override this method via ``_inherit`` and call
        ``super()`` first.
        """
        return True
