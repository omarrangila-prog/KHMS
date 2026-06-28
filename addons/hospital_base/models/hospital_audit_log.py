# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalAuditLog(models.Model):
    """Append-only audit trail.

    No group, including the hospital administrator, is ever granted
    ``unlink`` on this model (see security/ir.model.access.csv) -- this is a
    deliberate "even the admin can't tamper" design decision (Phase 9 §6).
    """

    _name = "hospital.audit.log"
    _description = "Hospital Audit Log"
    _order = "timestamp desc, id desc"
    _log_access = False

    res_model = fields.Char(
        string="Document Model",
        required=True,
        index=True,
        readonly=True,
    )
    res_id = fields.Integer(
        string="Document ID",
        required=True,
        index=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        index=True,
        readonly=True,
        ondelete="restrict",
    )
    action = fields.Selection(
        selection=[
            ("create", "Create"),
            ("write", "Write"),
            ("unlink", "Unlink"),
            ("read_sensitive", "Read (Sensitive)"),
        ],
        string="Action",
        required=True,
        index=True,
        readonly=True,
    )
    field_changes = fields.Text(
        string="Field Changes",
        readonly=True,
        help="JSON-encoded before/after payload for the tracked fields.",
    )
    timestamp = fields.Datetime(
        string="Timestamp",
        required=True,
        default=fields.Datetime.now,
        index=True,
        readonly=True,
    )

    def init(self):
        """Composite index supporting the audit-log review screen filters."""
        self.env.cr.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = %s",
            ("hospital_audit_log_model_res_id_idx",),
        )
        if not self.env.cr.fetchone():
            self.env.cr.execute(
                "CREATE INDEX hospital_audit_log_model_res_id_idx "
                "ON hospital_audit_log (res_model, res_id, timestamp DESC)"
            )
