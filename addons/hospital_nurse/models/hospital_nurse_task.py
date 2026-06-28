# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalNurseTask(models.Model):
    """OPD-style nurse task checklist item.

    NOTE: ``admission_id`` (a Many2one to ``hospital.ipd.admission``) is
    intentionally NOT defined here -- that model doesn't exist yet
    (``hospital_ipd`` is module 9 of 12, depends on ``hospital_nurse``
    per Phase 6 §9). A Many2one to a not-yet-existing model fails module
    load validation, so ``hospital_ipd`` will add ``admission_id`` back
    onto this model via ``_inherit`` once its target model exists, the
    same pattern ``hospital_base``'s visit model already documents for
    ``admission_id``/``prescription_ids``/etc. For now this model only
    supports OPD-style tasks linked to a ``visit_id``.
    """

    _name = "hospital.nurse.task"
    _inherit = ["hospital.audit.mixin"]
    _description = "Hospital Nurse Task"
    _order = "sequence, id"

    name = fields.Char(string="Task", required=True)
    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("done", "Done"),
        ],
        string="Status",
        required=True,
        default="pending",
        index=True,
    )
    done_by = fields.Many2one(comodel_name="res.users", string="Done By")
    done_at = fields.Datetime(string="Done At")
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        index=True,
    )

    def action_mark_done(self):
        for task in self:
            if task.state == "done":
                raise UserError(_("This task is already marked done."))
            task.write(
                {
                    "state": "done",
                    "done_by": self.env.user.id,
                    "done_at": fields.Datetime.now(),
                }
            )
        return True

    @api.onchange("state")
    def _onchange_state_reset_done(self):
        if self.state == "pending":
            self.done_by = False
            self.done_at = False
