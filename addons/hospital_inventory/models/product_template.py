# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Clinical medicine fields layered onto Odoo's product catalog.

    Per Phase 5 §3.3 / Phase 6 §6, ``hospital.medicine`` is *not* a new,
    disconnected model -- it is ``product.template`` itself, extended via
    ``_inherit``. This is the decision that makes pharmacy stock,
    valuation, and purchasing "free": dispensing later creates a real
    ``stock.move`` against a real ``product.product``, with no parallel
    catalog to keep in sync. ``is_hospital_medicine`` is the flag that
    lets views/domains/menus filter "which products are actually
    medicines" out of the full product catalog (a hospital may also sell
    non-medicine products, e.g. consumables or services).

    ``reorder_threshold`` is intentionally a plain ``Float`` rather than a
    stored computed ``is_low_stock`` Boolean: comparing it against
    ``qty_available`` per-product in Python would mean looping every
    product on every dashboard refresh, and a stored compute keyed off
    ``qty_available`` is itself awkward (quantity changes via stock moves,
    not writes on the template, so the compute would rarely invalidate
    correctly). Per Phase 5 §10's stated approach, the low-stock
    comparison is instead done once, in SQL, by the
    ``hospital.inventory.dashboard`` view model's ``init()`` query.
    """

    _inherit = "product.template"

    is_hospital_medicine = fields.Boolean(
        string="Is Hospital Medicine",
        default=False,
        index=True,
        help="Flags this product as a hospital medicine so medicine-only "
             "views, domains, and dashboards can filter the catalog.",
    )
    generic_name = fields.Char(
        string="Generic Name",
        help="INN / generic drug name, e.g. 'Paracetamol'.",
    )
    dosage_form = fields.Selection(
        selection=[
            ("tablet", "Tablet"),
            ("capsule", "Capsule"),
            ("syrup", "Syrup"),
            ("injection", "Injection"),
            ("cream", "Cream"),
            ("drops", "Drops"),
            ("inhaler", "Inhaler"),
            ("other", "Other"),
        ],
        string="Dosage Form",
    )
    strength = fields.Char(
        string="Strength",
        help='e.g. "500mg".',
    )
    requires_prescription = fields.Boolean(
        string="Requires Prescription",
        default=True,
    )
    controlled_substance = fields.Boolean(
        string="Controlled Substance",
        default=False,
        help="Narcotics / controlled drugs requiring extra dispensing "
             "safeguards (enforced by hospital_pharmacy, not this module).",
    )
    reorder_threshold = fields.Float(
        string="Reorder Threshold",
        default=0.0,
        help="Quantity below which this medicine is considered low stock "
             "on the Inventory Dashboard. Compared against on-hand "
             "quantity in SQL by hospital.inventory.dashboard, not a "
             "stored compute on this model.",
    )

    @api.model
    def _cron_check_low_stock(self):
        """LowStockAlertService (Phase 6 §6): daily ``ir.cron`` entry point.

        Reads the already-computed ``hospital.inventory.dashboard`` SQL
        view (no duplicate Python-side qty/threshold comparison) and
        creates one ``mail.activity`` reminder per low-stock medicine for
        the inventory manager group, skipping products that already have
        a pending low-stock activity so re-runs stay idempotent.
        """
        dashboard = self.env["hospital.inventory.dashboard"].sudo().search(
            [("is_low_stock", "=", True)]
        )
        if not dashboard:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        managers = self.env.ref(
            "hospital_inventory.group_hospital_inventory_manager",
            raise_if_not_found=False,
        )
        users = managers.users if managers else self.env["res.users"]
        product_model_id = self.env["ir.model"]._get_id("product.template")
        for row in dashboard:
            template = row.product_id.product_tmpl_id
            existing = self.env["mail.activity"].search([
                ("res_model", "=", "product.template"),
                ("res_id", "=", template.id),
                ("summary", "=", "Medicine Stock Below Reorder Threshold"),
            ], limit=1)
            if existing:
                continue
            for user in users:
                self.env["mail.activity"].create({
                    "res_model_id": product_model_id,
                    "res_id": template.id,
                    "activity_type_id": activity_type.id if activity_type else False,
                    "summary": "Medicine Stock Below Reorder Threshold",
                    "note": (
                        "%s is at %.2f on hand, at or below its reorder "
                        "threshold of %.2f."
                        % (row.product_name, row.qty_available, row.reorder_threshold)
                    ),
                    "user_id": user.id,
                })
