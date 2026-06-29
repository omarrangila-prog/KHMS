# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalVisit(models.Model):
    """Extend hospital.visit to add admission_id and make
    _compute_pending_branches aware of real admission completion.

    EXTENSION CONTRACT IMPLEMENTATION (same pattern as hospital_lab's and
    hospital_radiology's extensions -- see hospital_doctor's
    hospital_visit.py architecture note for the full contract):

    - Calls ``super()._compute_pending_branches()`` first to get the dict
      built by hospital_doctor (and, if installed, hospital_lab's and
      hospital_radiology's extensions).
    - An admission is "pending" (still open) while its state is
      ``requested`` or ``waiting_for_bed`` -- the patient has been
      ordered admitted but is not yet actually in a bed. Once
      ``admitted``, Phase 3 §3's own rule kicks in ("No, admitted ->
      Visit.state = admitted, removed from OPD queues entirely") --
      handled in ``action_route_from_consultation`` override below,
      not via the pending-branches list (an admitted patient is not
      "pending admission", they ARE admitted).
    - ``discharged``/``cancelled`` admissions are resolved: removed from
      the pending list, same as a completed/cancelled lab order.
    """

    _inherit = "hospital.visit"

    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Admission",
        ondelete="set null",
        index=True,
        copy=False,
        help="Set once this visit is escalated to an IPD admission "
             "(Phase 5 §1.3).",
    )
    admission_ids = fields.One2many(
        comodel_name="hospital.ipd.admission",
        inverse_name="visit_id",
        string="Admissions",
    )

    def _compute_pending_branches(self):
        """Extend the base pending-branch computation with the
        admission branch.

        Calls super() and then replaces the intent-only "admission"
        placeholder from hospital_doctor with a real check against
        hospital.ipd.admission: pending while requested/waiting_for_bed,
        resolved once admitted/discharged/cancelled (an admitted stay is
        handled by the visit's own admitted state, not by blocking
        billing -- see action_route_from_consultation below).
        """
        pending = super()._compute_pending_branches()

        open_admissions = self.env["hospital.ipd.admission"].search([
            ("visit_id", "in", self.ids),
            ("state", "in", ["requested", "waiting_for_bed"]),
        ])
        open_visit_ids = set(open_admissions.mapped("visit_id").ids)

        for visit in self:
            if visit.id in open_visit_ids:
                if "admission" not in pending[visit.id]:
                    pending[visit.id].append("admission")
            else:
                pending[visit.id] = [
                    b for b in pending[visit.id] if b != "admission"
                ]

        return pending

    def action_route_from_consultation(self):
        """Extend the base routing with the "admitted removes the visit
        from OPD queues entirely" rule (Phase 3 §3), which hospital_doctor
        explicitly left unimplemented pending this module.

        If the visit has a currently-admitted admission, the visit is
        moved straight to ``admitted`` and routing stops there -- it does
        not matter whether prescription/lab/radiology branches are still
        open, because an admitted patient's remaining orders are tracked
        against the admission/ward stay, not the OPD queue. Discharge
        (handled entirely by ``hospital.discharge.action_confirm()``) is
        what eventually moves the visit on to billing/done.
        """
        admitted = self.env["hospital.ipd.admission"].search([
            ("visit_id", "in", self.ids),
            ("state", "=", "admitted"),
        ])
        admitted_visit_ids = set(admitted.mapped("visit_id").ids)
        still_to_route = self.browse(
            [v.id for v in self if v.id not in admitted_visit_ids]
        )
        for visit in self:
            if visit.id in admitted_visit_ids and visit.state not in (
                "cancelled", "void", "done", "admitted"
            ):
                visit.state = "admitted"
        if still_to_route:
            return super(HospitalVisit, still_to_route).action_route_from_consultation()
        return True
