# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class HospitalLabResult(models.Model):
    """A single parameter result line for a lab order.

    One ``hospital.lab.order`` typically produces multiple result rows
    (e.g. a CBC produces Haemoglobin, WBC, Platelets, etc. — each as
    its own ``hospital.lab.result`` record). This keeps the result grid
    extensible and queryable without parsing comma fields.

    ``is_abnormal`` is a stored computed Boolean: True when ``value``
    parses as a float and lies outside ``[normal_range_min, normal_range_max]``.
    After compute, if abnormal, a message is posted on the record so it
    appears in the chatter (AbnormalResultFlagService per Phase 6 §7).
    """

    _name = "hospital.lab.result"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Lab Result"
    _order = "order_id, id"

    order_id = fields.Many2one(
        comodel_name="hospital.lab.order",
        string="Lab Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    parameter_name = fields.Char(
        string="Parameter",
        required=True,
    )
    value = fields.Char(
        string="Result Value",
        help="Numeric or text result. Numeric values are compared "
             "against the normal range to auto-set is_abnormal.",
    )
    unit = fields.Char(string="Unit")
    normal_range_min = fields.Float(
        string="Normal Min",
        help="Copied from the test catalog on order creation.",
    )
    normal_range_max = fields.Float(
        string="Normal Max",
        help="Copied from the test catalog on order creation.",
    )
    is_abnormal = fields.Boolean(
        string="Abnormal",
        compute="_compute_is_abnormal",
        store=True,
        tracking=True,
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="hospital_lab_result_attachment_rel",
        column1="result_id",
        column2="attachment_id",
        string="Attachments",
    )
    entered_by = fields.Many2one(
        comodel_name="res.users",
        string="Entered By",
        default=lambda self: self.env.uid,
        ondelete="set null",
    )
    entered_at = fields.Datetime(
        string="Entered At",
        default=fields.Datetime.now,
    )
    verified_by = fields.Many2one(
        comodel_name="res.users",
        string="Verified By",
        ondelete="set null",
        help="Optional second-check: the user who verified the result.",
    )

    @api.depends("value", "normal_range_min", "normal_range_max")
    def _compute_is_abnormal(self):
        for result in self:
            result.is_abnormal = self._check_abnormal(
                result.value,
                result.normal_range_min,
                result.normal_range_max,
            )

    @staticmethod
    def _check_abnormal(value, range_min, range_max):
        """Return True if value is numeric and outside [range_min, range_max].

        Returns False for non-numeric values (text results cannot be
        range-checked automatically).
        """
        if not value:
            return False
        # Both bounds must be set (non-zero) to perform a range check.
        if not range_min and not range_max:
            return False
        try:
            numeric = float(value.replace(",", "."))
        except (ValueError, AttributeError):
            return False
        if range_min and numeric < range_min:
            return True
        if range_max and numeric > range_max:
            return True
        return False

    def write(self, vals):
        result = super().write(vals)
        # AbnormalResultFlagService: post a chatter message when a result
        # transitions to abnormal so it's visible in the audit trail.
        for record in self:
            if record.is_abnormal:
                record._post_abnormal_notification()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.is_abnormal:
                record._post_abnormal_notification()
        return records

    def _post_abnormal_notification(self):
        """Post a chatter note for an abnormal result (AbnormalResultFlagService).

        Guards against duplicate notes by checking for an existing ABNORMAL
        message on this record before posting.
        """
        self.ensure_one()
        # Avoid duplicate notes — check existing messages for the ABNORMAL tag.
        if any("ABNORMAL" in (msg.body or "") for msg in self.message_ids):
            return
        self.message_post(
            body=_(
                "<b>ABNORMAL RESULT:</b> %(param)s = %(val)s %(unit)s "
                "(normal range: %(lo)s – %(hi)s)"
            ) % {
                "param": self.parameter_name,
                "val": self.value,
                "unit": self.unit or "",
                "lo": self.normal_range_min,
                "hi": self.normal_range_max,
            },
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
