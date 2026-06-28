# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HospitalPrescription(models.Model):
    """Prescription header (Phase 5 §3.4, Phase 6 §4).

    DESIGN NOTE -- ``admission_id`` intentionally omitted: Phase 5 §3.4
    lists an ``admission_id`` (Many2one -> ``hospital.ipd.admission``) for
    IPD linkage, but that target model does not exist yet (``hospital_ipd``
    is not built). Adding the field now would either dangle a reference to
    a non-existent model or force a dependency this module must not take
    (Phase 4 §2's dependency graph has ``hospital_ipd`` depending on
    ``hospital_nurse``, not the other way around, and ``hospital_doctor``
    must stay a dependency of ``hospital_ipd``, never the reverse). Per the
    same pattern ``hospital_base.hospital_visit`` already uses for
    ``prescription_ids``/``lab_order_ids``/etc., ``hospital_ipd`` will add
    ``admission_id`` back onto this model via ``_inherit`` once
    ``hospital.ipd.admission`` exists.
    """

    _name = "hospital.prescription"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Hospital Prescription"
    _order = "create_date desc"

    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    consultation_id = fields.Many2one(
        comodel_name="hospital.consultation",
        string="Consultation",
        ondelete="cascade",
        index=True,
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        related="visit_id.patient_id",
        store=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Doctor",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("partially_dispensed", "Partially Dispensed"),
            ("dispensed", "Dispensed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name="hospital.prescription.line",
        inverse_name="prescription_id",
        string="Lines",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        index=True,
    )

    def action_cancel(self):
        """Cancel the prescription.

        Per Phase 3 §3's "If a lab/radiology order is cancelled ... it's
        excluded from the all-branches-completed check" (the same rule
        applies symmetrically to prescriptions): once cancelled, this
        prescription no longer counts as a pending branch in
        ``hospital.visit._compute_pending_branches()``, so re-routing the
        visit afterwards is the caller's responsibility (mirrors how
        ``hospital.consultation.action_done()`` is the one place routing
        is triggered, keeping this method a simple state transition).
        """
        for prescription in self:
            if prescription.state == "dispensed":
                raise UserError(
                    _("A fully dispensed prescription cannot be cancelled."))
            prescription.state = "cancelled"
            prescription.line_ids.filtered(
                lambda line: line.state not in ("dispensed", "cancelled")
            ).write({"state": "cancelled"})
        return True

    def _recompute_state_from_lines(self):
        """Not wired as an ``@api.depends`` compute -- ``state`` remains a
        plain, tracked, manually-driven field per Phase 5 §3.4.
        Dispense-driven transitions are owned by ``hospital_pharmacy``,
        which will add the real dispense methods later via ``_inherit``.
        Kept as a private helper any future ``_inherit`` can call
        explicitly after dispensing a line, rather than a silent
        automatic compute that would fight with ``hospital_pharmacy``'s
        own transition logic.
        """
        for prescription in self:
            states = prescription.line_ids.mapped("state")
            if not states or all(s == "cancelled" for s in states):
                continue
            relevant = [s for s in states if s != "cancelled"]
            if not relevant:
                continue
            if all(s == "dispensed" for s in relevant):
                prescription.state = "dispensed"
            elif any(s in ("dispensed", "partial") for s in relevant):
                prescription.state = "partially_dispensed"
