# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalConsultationAmendWizard(models.TransientModel):
    """Same-day consultation amendment (Phase 3 §3 edge case):

    "Doctor can re-open a 'done' consultation same-day to add a forgotten
    order (audit-logged amendment), which re-opens the visit aggregate
    state ... from billing back to in_progress_multi."

    Creates a brand-new ``hospital.consultation`` (rather than mutating
    the original) with ``amended_from_id`` pointing back to the original
    -- the original stays untouched and audit-logged exactly as it was
    completed, per the audit-trail expectation; only the new record
    carries whatever additional outcome the doctor forgot. Restricted to
    same-day amendments only (compares ``create_date`` against "today" in
    the user's timezone-aware context date), matching the Phase 3 §3
    wording precisely.
    """

    _name = "hospital.consultation.amend.wizard"
    _description = "Amend Consultation"

    consultation_id = fields.Many2one(
        comodel_name="hospital.consultation",
        string="Original Consultation",
        required=True,
        ondelete="cascade",
    )
    reason = fields.Text(string="Reason for Amendment", required=True)

    @api.model
    def default_get(self, field_list):
        defaults = super().default_get(field_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            defaults["consultation_id"] = active_id
        return defaults

    def action_confirm_amend(self):
        self.ensure_one()
        consultation = self.consultation_id
        if consultation.state != "done":
            raise UserError(
                _("Only a completed consultation can be amended."))
        today = fields.Date.context_today(self)
        created_date = fields.Datetime.context_timestamp(
            self, consultation.create_date
        ).date()
        if created_date != today:
            raise UserError(
                _("This consultation can no longer be amended -- same-day "
                  "amendments are only allowed on the day the consultation "
                  "was created."))
        if not self.reason or not self.reason.strip():
            raise UserError(_("Please provide a reason for this amendment."))

        new_consultation = consultation.copy(
            {
                "amended_from_id": consultation.id,
                "state": "draft",
                "clinical_notes": _(
                    "Amendment of consultation on %(date)s. Reason: %(reason)s\n\n%(notes)s"
                ) % {
                    "date": created_date,
                    "reason": self.reason,
                    "notes": consultation.clinical_notes or "",
                },
            }
        )
        if consultation.visit_id.state == "billing":
            consultation.visit_id.action_reopen_from_billing()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hospital.consultation",
            "res_id": new_consultation.id,
            "view_mode": "form",
            "target": "current",
        }
