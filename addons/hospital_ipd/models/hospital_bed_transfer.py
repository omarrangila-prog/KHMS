# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HospitalBedTransfer(models.Model):
    """Mid-stay ward/bed transfer (Phase 5 §5.4, Phase 3 §4).

    Always a child row of a single, continuous ``hospital.ipd.admission``
    -- a transfer never creates a new admission record. ``action_confirm``
    is the only place that mutates bed states, so the full transfer audit
    trail (old bed freed, new bed occupied, who/when/why) is captured in
    one transactional method.
    """

    _name = "hospital.bed.transfer"
    _inherit = ["hospital.audit.mixin"]
    _description = "Hospital Bed Transfer"
    _order = "transfer_datetime desc"

    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Admission",
        required=True,
        ondelete="cascade",
        index=True,
    )
    from_bed_id = fields.Many2one(
        comodel_name="hospital.bed",
        string="From Bed",
        ondelete="restrict",
        index=True,
    )
    to_bed_id = fields.Many2one(
        comodel_name="hospital.bed",
        string="To Bed",
        required=True,
        ondelete="restrict",
        index=True,
    )
    transfer_datetime = fields.Datetime(
        string="Transfer Date/Time",
        required=True,
        default=fields.Datetime.now,
    )
    reason = fields.Text(string="Reason", required=True)
    transferred_by = fields.Many2one(
        comodel_name="res.users",
        string="Transferred By",
        default=lambda self: self.env.user,
        ondelete="set null",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="admission_id.company_id",
        store=True,
        index=True,
    )

    def action_confirm(self):
        """Apply the transfer: free the old bed, occupy the new one.

        Relies on the same partial unique index (Phase 5 §5.2) to reject
        a transfer into a bed that is concurrently being admitted into
        by someone else -- ``to_bed_id`` must be vacant at the Python
        check, and the database is the final backstop against a race.
        """
        for transfer in self:
            admission = transfer.admission_id
            if admission.state != "admitted":
                raise UserError(
                    _("Only an admitted patient can be transferred."))
            if transfer.to_bed_id.state != "vacant":
                raise UserError(
                    _("Bed %s is not vacant.") % transfer.to_bed_id.display_name
                )
            old_bed = admission.bed_id
            if old_bed:
                old_bed.write({"state": "cleaning", "current_admission_id": False})
            transfer.to_bed_id.write({
                "state": "occupied",
                "current_admission_id": admission.id,
            })
            admission.write({"bed_id": transfer.to_bed_id.id})
            if not transfer.from_bed_id:
                transfer.from_bed_id = old_bed
        return True
