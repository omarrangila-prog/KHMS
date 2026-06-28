# -*- coding: utf-8 -*-
import json

from odoo import api, models


class HospitalAuditMixin(models.AbstractModel):
    """Reusable mixin emitting ``hospital.audit.log`` rows.

    Concrete models opt in by inheriting this mixin (``_inherit =
    ["hospital.audit.mixin"]``) and optionally overriding
    :meth:`_get_audit_tracked_fields` to restrict which fields are recorded
    in the before/after payload. Tracking everything by default keeps the
    mixin useful out of the box for new models added by later modules.
    """

    _name = "hospital.audit.mixin"
    _description = "Hospital Audit Mixin"

    def _get_audit_tracked_fields(self):
        """Return the list of field names to capture on write.

        Models with large/binary fields should override this to avoid
        bloating the audit log with irrelevant payloads.
        """
        return list(self._fields.keys())

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        audit_log = self.env["hospital.audit.log"].sudo()
        for record in records:
            audit_log.create(
                {
                    "res_model": record._name,
                    "res_id": record.id,
                    "user_id": self.env.uid,
                    "action": "create",
                    "field_changes": json.dumps(
                        self._audit_serialize_vals(
                            {
                                key: value
                                for key, value in record._cache.items()
                                if key in self._get_audit_tracked_fields()
                            }
                        )
                    ),
                }
            )
        return records

    def write(self, vals):
        tracked = self._get_audit_tracked_fields()
        relevant_vals = {
            key: value for key, value in vals.items() if key in tracked
        }
        before = {}
        if relevant_vals:
            for record in self:
                before[record.id] = {
                    key: record[key] for key in relevant_vals if key in record
                }
        result = super().write(vals)
        if relevant_vals:
            audit_log = self.env["hospital.audit.log"].sudo()
            for record in self:
                changes = {
                    key: {
                        "before": self._audit_serialize_value(before[record.id].get(key)),
                        "after": self._audit_serialize_value(record[key]),
                    }
                    for key in relevant_vals
                    if key in before.get(record.id, {})
                }
                audit_log.create(
                    {
                        "res_model": record._name,
                        "res_id": record.id,
                        "user_id": self.env.uid,
                        "action": "write",
                        "field_changes": json.dumps(changes),
                    }
                )
        return result

    def unlink(self):
        audit_log = self.env["hospital.audit.log"].sudo()
        payload = [
            {"res_model": record._name, "res_id": record.id}
            for record in self
        ]
        result = super().unlink()
        for entry in payload:
            audit_log.create(
                {
                    "res_model": entry["res_model"],
                    "res_id": entry["res_id"],
                    "user_id": self.env.uid,
                    "action": "unlink",
                    "field_changes": False,
                }
            )
        return result

    def _audit_serialize_value(self, value):
        """Best-effort JSON-safe conversion for a single field value."""
        if isinstance(value, models.BaseModel):
            return value.ids
        if isinstance(value, (list, tuple, set)):
            return list(value)
        try:
            json.dumps(value)
        except TypeError:
            return str(value)
        return value

    def _audit_serialize_vals(self, vals):
        return {key: self._audit_serialize_value(value) for key, value in vals.items()}
