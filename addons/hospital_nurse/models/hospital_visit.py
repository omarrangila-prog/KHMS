# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HospitalVisit(models.Model):
    """Nurse-specific addition to the ``hospital_base`` visit spine.

    ``hospital_base``'s visit model has no knowledge of vitals (that model
    lives in this module), so the nurse->doctor transition triggered by
    recording vitals (Phase 3 §2) is added here rather than in
    ``hospital_base``.
    """

    _inherit = "hospital.visit"

    vitals_ids = fields.One2many(
        comodel_name="hospital.vitals",
        inverse_name="visit_id",
        string="Vitals",
    )
    nurse_task_ids = fields.One2many(
        comodel_name="hospital.nurse.task",
        inverse_name="visit_id",
        string="Nurse Tasks",
    )

    def action_vitals_recorded(self):
        """Move the visit from the nurse queue to the doctor queue.

        Called by ``hospital.vitals._check_abnormal_and_escalate()``
        right after a vitals record is created. Kept as its own action
        method (rather than inlined) so it carries the same state-guard
        discipline as ``hospital_base``'s other ``action_*`` transitions
        and can be called directly (e.g. from a future "skip vitals"
        admin override) without going through vitals creation.
        """
        for visit in self:
            if visit.state != "waiting_nurse":
                raise UserError(
                    _("Vitals can only be recorded while the visit is "
                      "waiting for the nurse.")
                )
            visit.state = "waiting_doctor"
        return True
