# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

EXPIRING_SOON_WINDOW_DAYS = 30


class HospitalMedicineBatch(models.Model):
    """Expiry tracking for medicine batches (Phase 6 §6).

    DESIGN NOTE -- ``_inherit = "stock.lot"`` rather than a new model:
    Odoo's ``stock.lot`` already *is* the per-batch/per-serial tracking
    record (``name`` as the lot/batch number, ``product_id`` linking back
    to the medicine, ``quant_ids`` for on-hand quantity by location). A
    standalone ``hospital.medicine.batch`` model would duplicate all of
    that and require its own stock-move wiring to stay in sync with real
    inventory transactions -- exactly the duplication Phase 5 §6 warns
    against ("inventory is 100% native Odoo Inventory; we only add the
    clinical layer on top"). Extending ``stock.lot`` via ``_inherit``
    means this module only adds the one field ``stock.lot`` doesn't
    already have: ``expiry_date``. (Odoo also ships an optional
    ``product_expiry`` module with its own ``expiration_date`` field, but
    this module does not depend on it -- adding ``expiry_date`` here is
    therefore non-colliding and keeps this module's dependency footprint
    at ``hospital_base`` + ``stock`` only, per the Phase 6 §6 dependency
    contract.)

    ``is_expiring_soon``/``is_expired`` are deliberately **not** stored
    fields: a stored Boolean keyed off "now" would go stale the instant
    the clock ticks past midnight without a write on the record. They are
    computed live (cheap -- a single date comparison per record) so list
    views/badges are always correct on read. The dashboard SQL view
    (``hospital.inventory.dashboard``) does the equivalent comparison
    directly in SQL against ``CURRENT_DATE`` for aggregate reporting,
    which is the only place per-row Python looping would actually be a
    performance concern.
    """

    _inherit = "stock.lot"

    expiry_date = fields.Date(
        string="Expiry Date",
        help="Expiry date for this medicine batch/lot. Left empty for "
             "non-medicine products or for lots that do not expire.",
    )
    is_expiring_soon = fields.Boolean(
        string="Expiring Soon",
        compute="_compute_expiry_status",
        search="_search_is_expiring_soon",
        help="True when expiry_date falls within the next 30 days "
             "(and has not already passed).",
    )
    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_expiry_status",
        search="_search_is_expired",
        help="True when expiry_date is in the past.",
    )

    @api.depends("expiry_date")
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        soon_cutoff = today + timedelta(days=EXPIRING_SOON_WINDOW_DAYS)
        for lot in self:
            if not lot.expiry_date:
                lot.is_expired = False
                lot.is_expiring_soon = False
            else:
                lot.is_expired = lot.expiry_date < today
                lot.is_expiring_soon = today <= lot.expiry_date <= soon_cutoff

    def _search_is_expired(self, operator, value):
        today = fields.Date.context_today(self)
        matches_true = (operator == "=" and value) or (operator == "!=" and not value)
        if matches_true:
            return [("expiry_date", "<", today)]
        return [("expiry_date", ">=", today)]

    def _search_is_expiring_soon(self, operator, value):
        today = fields.Date.context_today(self)
        soon_cutoff = today + timedelta(days=EXPIRING_SOON_WINDOW_DAYS)
        matches_true = (operator == "=" and value) or (operator == "!=" and not value)
        if matches_true:
            return [("expiry_date", ">=", today), ("expiry_date", "<=", soon_cutoff)]
        return ["|", ("expiry_date", "<", today), ("expiry_date", ">", soon_cutoff)]

    @api.model
    def _cron_check_expiring_batches(self):
        """ExpiryAlertService (Phase 6 §6): daily ``ir.cron`` entry point.

        Creates one ``mail.activity`` reminder per batch newly within the
        30-day expiry window, addressed to the inventory manager group
        (Phase 8 §13's permission scope), so the alert surfaces on the
        existing Activities/To-do UI rather than a bespoke notification
        model. Re-running the cron does not duplicate activities for a
        batch that already has one pending.
        """
        today = fields.Date.context_today(self)
        soon_cutoff = today + timedelta(days=EXPIRING_SOON_WINDOW_DAYS)
        batches = self.search([
            ("expiry_date", ">=", today),
            ("expiry_date", "<=", soon_cutoff),
        ])
        if not batches:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        managers = self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager",
            raise_if_not_found=False,
        )
        users = managers.users if managers else self.env["res.users"]
        for batch in batches:
            existing = self.env["mail.activity"].search([
                ("res_model", "=", "stock.lot"),
                ("res_id", "=", batch.id),
                ("summary", "=", "Medicine Batch Expiring Soon"),
            ], limit=1)
            if existing:
                continue
            for user in users:
                self.env["mail.activity"].create({
                    "res_model_id": self.env["ir.model"]._get_id("stock.lot"),
                    "res_id": batch.id,
                    "activity_type_id": activity_type.id if activity_type else False,
                    "summary": "Medicine Batch Expiring Soon",
                    "note": (
                        "Batch %s of %s expires on %s."
                        % (batch.name, batch.product_id.display_name, batch.expiry_date)
                    ),
                    "user_id": user.id,
                    "date_deadline": batch.expiry_date,
                })
