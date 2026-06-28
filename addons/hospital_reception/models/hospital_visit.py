# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalVisit(models.Model):
    """Reception-specific additions to the ``hospital_base`` visit spine.

    Only a single computed, non-stored field is added here: the visit's
    1-based position within its own doctor's live queue, sorted the same
    way the composite DB index in ``hospital_base`` already backs --
    ``(priority desc-ish via selection order, checkin_datetime)`` -- per
    Phase 3 §2 ("Doctor Queue, sorted by priority then check-in time").
    Deliberately not stored: it is purely a reception-dashboard display
    aid and must always reflect the live queue, never a stale snapshot.
    """

    _inherit = "hospital.visit"

    queue_position = fields.Integer(
        string="Queue Position",
        compute="_compute_queue_position",
    )

    _QUEUE_STATES = ("waiting_nurse", "waiting_doctor", "in_progress_multi")
    _PRIORITY_ORDER = {"emergency": 0, "urgent": 1, "normal": 2}

    @api.depends("doctor_id", "state", "priority", "checkin_datetime")
    def _compute_queue_position(self):
        queued = self.filtered(lambda v: v.state in self._QUEUE_STATES)
        (queued or self).queue_position = 0
        if not queued:
            return
        doctor_ids = queued.mapped("doctor_id").ids
        all_queued = self.search(
            [
                ("doctor_id", "in", doctor_ids or [False]),
                ("state", "in", list(self._QUEUE_STATES)),
            ]
        )
        by_doctor = {}
        for visit in all_queued:
            by_doctor.setdefault(visit.doctor_id.id, []).append(visit)
        for doctor_id, visits in by_doctor.items():
            ordered = sorted(
                visits,
                key=lambda v: (
                    self._PRIORITY_ORDER.get(v.priority, 99),
                    v.checkin_datetime or fields.Datetime.now(),
                ),
            )
            for index, visit in enumerate(ordered, start=1):
                if visit in queued:
                    visit.queue_position = index
