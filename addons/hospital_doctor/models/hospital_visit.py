# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HospitalVisit(models.Model):
    """Doctor-specific additions to the ``hospital_base`` visit spine:
    consultations, prescriptions, and the extensible aggregate-state
    routing contract (Phase 3 §3, Phase 6 §4).

    ARCHITECTURE NOTE -- read this before touching ``_compute_pending_branches``
    ===========================================================================
    A visit can be simultaneously "in" several department queues at once
    (e.g. pharmacy AND lab), per Phase 3 §3: "A visit can be simultaneously
    in the Pharmacy queue and Lab queue -- ``Visit.state = in_progress_multi``
    is a computed/aggregate state; the *real* per-branch status lives on
    each sub-record." The visit only flips to ``billing`` once **every**
    branch the doctor opened reports done/cancelled.

    At the time this module (``hospital_doctor``, module 4 of 12) is built,
    only two branches actually exist as real sub-records:

    - the prescription branch (``hospital.prescription``, built in this
      module) -- a real model with a real ``state`` field.
    - lab / radiology / admission, which are only **intent flags**
      (``outcome_lab_requested`` / ``outcome_radiology_requested`` /
      ``outcome_admit_requested``) on ``hospital.consultation`` right now,
      because ``hospital.lab.order``, ``hospital.radiology.order``, and
      ``hospital.ipd.admission`` don't exist until ``hospital_lab``,
      ``hospital_radiology``, and ``hospital_ipd`` are built later in the
      Phase 12 build order.

    ``_compute_pending_branches()`` is the extension point those three
    future modules MUST extend via ``_inherit`` (calling ``super()`` and
    adding their own branch to the returned list) rather than overriding
    wholesale, so each module only ever has to reason about its own
    branch. See the method's docstring for the exact contract (return
    shape, what "pending" means) -- it will not change when those modules
    are added, only grow via ``super()`` chaining.
    """

    _inherit = "hospital.visit"

    consultation_ids = fields.One2many(
        comodel_name="hospital.consultation",
        inverse_name="visit_id",
        string="Consultations",
    )
    prescription_ids = fields.One2many(
        comodel_name="hospital.prescription",
        inverse_name="visit_id",
        string="Prescriptions",
    )

    def _compute_pending_branches(self):
        """Return, per visit, the list of outcome branches still open.

        EXTENSION CONTRACT (read this before extending in hospital_lab /
        hospital_radiology / hospital_ipd):

        Returns a ``dict`` mapping ``visit.id -> list[str]``, where each
        string is a short, human-readable branch label (e.g.
        ``"prescription"``, ``"lab"``, ``"radiology"``, ``"admission"``)
        that is still pending for that visit. An **empty list** for a
        visit means every branch that visit's consultation(s) opened has
        been resolved (done/dispensed/cancelled) -- i.e. the visit is
        eligible to move to ``billing``.

        This module (``hospital_doctor``) only knows about:

        1. The **prescription** branch: pending if any
           ``hospital.prescription`` linked to the visit is in state
           ``draft`` or ``partially_dispensed`` (``cancelled`` and
           ``dispensed`` are resolved).
        2. The **intent-only** lab/radiology/admission flags on the
           visit's consultations: since the real order/admission models
           do not exist yet in this module's dependency graph, a visit
           whose latest consultation has ``outcome_lab_requested``,
           ``outcome_radiology_requested``, or ``outcome_admit_requested``
           set is treated as having a permanently-pending branch for that
           flag -- there is no way to resolve it from within this module.
           This is intentional and documented: it prevents
           ``action_route_from_consultation()`` from incorrectly fast-
           forwarding a visit to ``billing`` just because the module that
           would track real completion isn't installed yet.

        ``hospital_lab`` MUST override this method as follows once it
        exists (illustrative, not binding code -- adapt to its own
        field/model names)::

            def _compute_pending_branches(self):
                pending = super()._compute_pending_branches()
                lab_data = self.env["hospital.lab.order"].read_group(
                    domain=[
                        ("visit_id", "in", self.ids),
                        ("state", "not in", ["completed", "cancelled"]),
                    ],
                    fields=["visit_id"],
                    groupby=["visit_id"],
                )
                open_visit_ids = {d["visit_id"][0] for d in lab_data}
                for visit in self:
                    if visit.id in open_visit_ids:
                        pending[visit.id].append("lab")
                    else:
                        # Remove the permanently-pending placeholder this
                        # module's base implementation adds for the
                        # intent flag, now that real completion can be
                        # checked.
                        pending[visit.id] = [
                            b for b in pending[visit.id] if b != "lab"
                        ]
                return pending

        ``hospital_radiology`` and ``hospital_ipd`` follow the identical
        pattern for their own branch label (``"radiology"``,
        ``"admission"``). ``hospital_pharmacy`` does NOT need to extend
        this method -- it only adds dispense behavior to
        ``hospital.prescription.line``, and the prescription-branch check
        already lives here since ``hospital.prescription`` itself is
        owned by this module.

        DESIGN NOTE on the intent-flag check: only the visit's **latest**
        consultation's flags are consulted, not the union of every
        consultation ever logged against the visit. A same-day amendment
        is expected to restate every outcome that is still relevant (see
        the amend wizard / demo data), so the latest consultation is
        always the authoritative statement of "what is still open" for
        the intent-only branches. This avoids a stale flag from an old,
        already-amended consultation permanently pinning a visit in
        ``in_progress_multi``. The prescription branch does not have this
        problem since it is checked against real ``hospital.prescription``
        records (which accumulate and resolve independently of which
        consultation created them), not against consultation flags.
        """
        pending = {visit.id: [] for visit in self}

        open_prescriptions = self.env["hospital.prescription"].search(
            [
                ("visit_id", "in", self.ids),
                ("state", "in", ["draft", "partially_dispensed"]),
            ]
        )
        for prescription in open_prescriptions:
            pending[prescription.visit_id.id].append("prescription")

        for visit in self:
            latest_consultation = visit.consultation_ids.sorted(
                key=lambda c: c.create_date or fields.Datetime.now(),
                reverse=True,
            )[:1]
            if not latest_consultation:
                continue
            consultation = latest_consultation[0]
            if consultation.outcome_lab_requested:
                pending[visit.id].append("lab")
            if consultation.outcome_radiology_requested:
                pending[visit.id].append("radiology")
            if consultation.outcome_admit_requested:
                pending[visit.id].append("admission")

        return pending

    def action_route_from_consultation(self):
        """Re-derive the visit's aggregate state from its open branches.

        Called by ``hospital.consultation.action_done()`` right after a
        consultation is marked done (Phase 3 §3). Never called directly
        from the UI -- it is the routing half of the consultation
        contract, kept on ``hospital.visit`` (rather than inlined in the
        consultation model) so future modules extending
        ``_compute_pending_branches()`` only ever need to touch one
        method on one model to make the routing "fully real" once their
        own order/admission model exists.

        Rules implemented now (Phase 3 §3):

        - No pending branches at all -> ``billing`` (the discharge-only,
          or "every branch already resolved", case).
        - Any pending branch -> ``in_progress_multi`` (visible in every
          relevant queue simultaneously; per-branch status lives on the
          sub-records themselves, not on the visit).
        - ``hospital_ipd`` will eventually add an extra rule here too
          (an *admitted* admission removes the visit from OPD queues
          entirely per Phase 3 §3's "No, admitted -> Visit.state =
          admitted" branch) -- not implemented in this module since
          ``hospital.ipd.admission`` doesn't exist yet; today an
          admit-requested flag simply keeps the visit in
          ``in_progress_multi`` like any other open branch.
        """
        pending_map = self._compute_pending_branches()
        for visit in self:
            if visit.state in ("cancelled", "void", "done"):
                continue
            if pending_map.get(visit.id):
                if visit.state != "in_progress_multi":
                    visit.state = "in_progress_multi"
            else:
                visit.action_to_billing()
        return True

    def action_reopen_from_billing(self):
        """Reopen a visit from ``billing`` back to ``in_progress_multi``.

        Used exclusively by ``hospital.consultation.amend.wizard`` for the
        same-day amendment edge case (Phase 3 §3: "Doctor can re-open a
        'done' consultation same-day to add a forgotten order ... re-opens
        the visit aggregate state ... from billing back to
        in_progress_multi"). Kept as its own guarded action method (rather
        than a raw ``write``) for the same state-guard discipline as
        ``hospital_base``'s other ``action_*`` transitions.
        """
        for visit in self:
            if visit.state != "billing":
                raise UserError(
                    _("Only a visit currently in Billing can be reopened "
                      "by a same-day consultation amendment.")
                )
            visit.state = "in_progress_multi"
        return True
