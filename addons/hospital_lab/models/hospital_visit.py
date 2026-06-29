# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalVisit(models.Model):
    """Extend hospital.visit to add lab_order_ids and make
    _compute_pending_branches aware of real lab completion.

    EXTENSION CONTRACT IMPLEMENTATION (see hospital_doctor's hospital_visit.py
    architecture note and _compute_pending_branches docstring for the full
    contract; this module implements exactly the illustrative code shown there):

    - Calls ``super()._compute_pending_branches()`` first to get the dict
      built by hospital_doctor (prescription branch + intent-only placeholders).
    - Uses read_group on hospital.lab.order to find which visits have any
      order NOT in completed/cancelled.
    - For visits WITH open lab orders: appends "lab" to the pending list.
    - For visits WITHOUT open lab orders: removes the "lab" placeholder
      that hospital_doctor's base implementation adds for the intent flag,
      since real completion can now be checked.

    This is the exact pattern documented in hospital_doctor's
    _compute_pending_branches() docstring under "hospital_lab MUST override
    this method as follows once it exists."
    """

    _inherit = "hospital.visit"

    lab_order_ids = fields.One2many(
        comodel_name="hospital.lab.order",
        inverse_name="visit_id",
        string="Lab Orders",
    )

    def _compute_pending_branches(self):
        """Extend the base pending-branch computation with the lab branch.

        Calls super() and then replaces the intent-only "lab" placeholder
        from hospital_doctor with a real check against hospital.lab.order.
        """
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
                # Real open lab orders exist: branch is pending.
                if "lab" not in pending[visit.id]:
                    pending[visit.id].append("lab")
            else:
                # No open lab orders: remove the intent-flag placeholder
                # so this visit is no longer blocked by lab.
                pending[visit.id] = [
                    b for b in pending[visit.id] if b != "lab"
                ]

        return pending
