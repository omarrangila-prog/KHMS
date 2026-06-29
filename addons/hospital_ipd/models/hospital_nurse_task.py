# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalNurseTask(models.Model):
    """Add ``admission_id`` to ``hospital.nurse.task`` for IPD ward-round
    / MAR checklist items, per the extension point ``hospital_nurse``
    documented on this model (its ``hospital_nurse_task.py`` docstring:
    "hospital_ipd will add admission_id back onto this model via
    _inherit once its target model exists").

    A task may now be linked to either a ``visit_id`` (OPD-style, the
    original use case) or an ``admission_id`` (IPD ward rounds) -- both
    are optional Many2one fields, not mutually exclusive at the schema
    level, but the Ward Dashboard only ever creates ward-round tasks
    with ``admission_id`` set.
    """

    _inherit = "hospital.nurse.task"

    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Admission",
        ondelete="cascade",
        index=True,
        help="Set for IPD ward-round / MAR checklist tasks, as opposed "
             "to the OPD-style visit_id tasks hospital_nurse already "
             "supports.",
    )
