# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalVisit(models.Model):
    """Extend hospital.visit to add radiology_order_ids and make
    _compute_pending_branches aware of real radiology completion.

    EXTENSION CONTRACT IMPLEMENTATION (identical pattern to hospital_lab's
    extension, but for the "radiology" branch label):

    - Calls ``super()._compute_pending_branches()`` first to get the dict
      built by hospital_doctor (and, if installed, hospital_lab's extension).
    - Uses read_group on hospital.radiology.order to find which visits have
      any order NOT in completed/cancelled.
    - For visits WITH open radiology orders: appends "radiology" to the
      pending list.
    - For visits WITHOUT open radiology orders: removes the "radiology"
      placeholder that hospital_doctor's base implementation adds for the
      intent flag, since real completion can now be checked.
    """

    _inherit = "hospital.visit"

    radiology_order_ids = fields.One2many(
        comodel_name="hospital.radiology.order",
        inverse_name="visit_id",
        string="Radiology Orders",
    )

    def _compute_pending_branches(self):
        """Extend the base pending-branch computation with the radiology branch.

        Calls super() and then replaces the intent-only "radiology" placeholder
        from hospital_doctor with a real check against hospital.radiology.order.
        """
        pending = super()._compute_pending_branches()

        radiology_data = self.env["hospital.radiology.order"].read_group(
            domain=[
                ("visit_id", "in", self.ids),
                ("state", "not in", ["completed", "cancelled"]),
            ],
            fields=["visit_id"],
            groupby=["visit_id"],
        )
        open_visit_ids = {d["visit_id"][0] for d in radiology_data}

        for visit in self:
            if visit.id in open_visit_ids:
                # Real open radiology orders exist: branch is pending.
                if "radiology" not in pending[visit.id]:
                    pending[visit.id].append("radiology")
            else:
                # No open radiology orders: remove the intent-flag placeholder
                # so this visit is no longer blocked by radiology.
                pending[visit.id] = [
                    b for b in pending[visit.id] if b != "radiology"
                ]

        return pending
