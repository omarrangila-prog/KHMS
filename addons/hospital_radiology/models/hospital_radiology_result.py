# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalRadiologyResult(models.Model):
    """Findings and impression for a radiology order.

    Unlike lab results (which are parameter rows), radiology results are
    narrative: free-text ``findings_text`` (what the radiologist observed)
    and optional ``impression_text`` (clinical summary / conclusion).
    Images and PDF reports are attached via ``attachment_ids``.
    """

    _name = "hospital.radiology.result"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Radiology Result"
    _order = "order_id, id"

    order_id = fields.Many2one(
        comodel_name="hospital.radiology.order",
        string="Radiology Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    findings_text = fields.Text(
        string="Findings",
        help="Detailed radiologist observations.",
    )
    impression_text = fields.Text(
        string="Impression",
        help="Clinical summary / conclusion (optional).",
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="hospital_radiology_result_attachment_rel",
        column1="result_id",
        column2="attachment_id",
        string="Images / Reports",
    )
    reported_by = fields.Many2one(
        comodel_name="res.users",
        string="Reported By",
        default=lambda self: self.env.uid,
        ondelete="set null",
    )
    reported_at = fields.Datetime(
        string="Reported At",
        default=fields.Datetime.now,
    )
    verified_by = fields.Many2one(
        comodel_name="res.users",
        string="Verified By",
        ondelete="set null",
        help="Optional second-check: the user who verified/countersigned the report.",
    )
