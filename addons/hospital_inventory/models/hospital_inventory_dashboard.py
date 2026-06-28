# -*- coding: utf-8 -*-
from odoo import fields, models, tools

EXPIRING_SOON_WINDOW_DAYS = 30


class HospitalInventoryDashboard(models.Model):
    """Read-only SQL-view aggregate backing the Inventory Dashboard.

    Per Phase 5 §10 ("dashboard aggregates ... implemented as PostgreSQL
    SQL views ... computed in the database, not pulled into Python and
    looped"), this is an ``_auto = False`` model: Odoo never creates a
    table for it, ``init()`` creates a SQL ``VIEW`` instead, and every
    field maps 1:1 onto a view column. The model is inherently read-only
    (there is nothing to write back to -- see security/ir.model.access.csv
    and the absence of any ``create``/``write`` override).

    One row per hospital-medicine product variant (``product.product``),
    joining:

    - ``product_product``/``product_template`` for identity, the
      ``reorder_threshold``, and the ``is_hospital_medicine`` filter.
    - ``stock_quant`` (aggregated) for on-hand quantity across all
      internal locations.
    - ``stock_lot`` (aggregated) for the nearest (soonest) non-expired
      batch expiry date, used to derive the expiring-soon flag.

    Low-stock and expiring-soon flags are both plain SQL boolean
    expressions evaluated against ``CURRENT_DATE``/the on-hand quantity,
    exactly the kind of date/threshold comparison Phase 5 §10 wants done
    in the database rather than as a stored per-product compute (which
    would go stale the moment stock moves or the clock changes without a
    write on the product).
    """

    _name = "hospital.inventory.dashboard"
    _description = "Hospital Inventory Dashboard"
    _auto = False
    _order = "is_low_stock desc, is_expiring_soon desc, product_name"

    product_id = fields.Many2one(comodel_name="product.product", string="Medicine", readonly=True)
    product_name = fields.Char(string="Name", readonly=True)
    default_code = fields.Char(string="Internal Reference", readonly=True)
    categ_id = fields.Many2one(comodel_name="product.category", string="Category", readonly=True)
    qty_available = fields.Float(string="On Hand Qty", readonly=True)
    reorder_threshold = fields.Float(string="Reorder Threshold", readonly=True)
    is_low_stock = fields.Boolean(string="Low Stock", readonly=True)
    nearest_expiry_date = fields.Date(string="Nearest Batch Expiry", readonly=True)
    is_expiring_soon = fields.Boolean(string="Expiring Soon", readonly=True)
    is_expired = fields.Boolean(string="Has Expired Batch", readonly=True)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # NOTE on SQL safety (Phase 11 §1 "no raw SQL string
        # interpolation -- ever"): the only value interpolated below via
        # Python string formatting is ``self._table``, the view's own
        # table name derived from this model's ``_name`` -- a fixed,
        # developer-controlled identifier, never user input, and not
        # something `cr.execute`'s ``%s`` placeholders can bind anyway
        # (placeholders bind *values*, not identifiers/table names).
        # This mirrors Odoo core's own convention for SQL-view ``init()``
        # hooks (e.g. ``stock_quant``, ``sale_report``). The expiry
        # window is passed as a genuine bound query parameter, not
        # string-formatted, even though it is also a constant, to keep
        # the one runtime-variable part of the query unambiguously safe.
        # Join logic:
        #   product_product/product_template -- one row per medicine
        #       variant, filtered to is_hospital_medicine = true so the
        #       dashboard never surfaces unrelated catalog products.
        #   stock_quant -- LEFT JOIN aggregated (SUM) per product across
        #       *internal* locations only (usage = 'internal'), so
        #       customer/supplier/virtual locations never inflate
        #       on-hand counts; COALESCE to 0 for medicines with no
        #       quants yet (e.g. brand-new, never stocked).
        #   stock_lot -- LEFT JOIN aggregated (MIN) per product to find
        #       the single soonest expiry_date among that product's
        #       batches that have not already expired (expiry_date >=
        #       CURRENT_DATE) -- this is the date the dashboard should
        #       warn about next; already-expired batches are reported
        #       separately via the has_expired_batch flag (EXISTS
        #       sub-select) so an old expired batch doesn't hide a
        #       newer, still-valid one from the "nearest expiry" column.
        # Both joins are pre-aggregated in their own sub-selects before
        # joining onto product_product, so the GROUP BY at the
        # product_product/product_template level isn't required and the
        # query stays a simple set of LEFT JOINs (cheap, index-friendly
        # on product_id).
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    pp.id AS id,
                    pp.id AS product_id,
                    pt.name AS product_name,
                    pp.default_code AS default_code,
                    pt.categ_id AS categ_id,
                    COALESCE(quant.qty_available, 0.0) AS qty_available,
                    pt.reorder_threshold AS reorder_threshold,
                    (COALESCE(quant.qty_available, 0.0) <= pt.reorder_threshold)
                        AS is_low_stock,
                    lot.nearest_expiry_date AS nearest_expiry_date,
                    (
                        lot.nearest_expiry_date IS NOT NULL
                        AND lot.nearest_expiry_date >= CURRENT_DATE
                        AND lot.nearest_expiry_date <= (CURRENT_DATE + (%%s || ' days')::interval)
                    ) AS is_expiring_soon,
                    EXISTS (
                        SELECT 1
                        FROM stock_lot expired_lot
                        WHERE expired_lot.product_id = pp.id
                            AND expired_lot.expiry_date IS NOT NULL
                            AND expired_lot.expiry_date < CURRENT_DATE
                    ) AS is_expired,
                    pt.company_id AS company_id
                FROM product_product pp
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN (
                    SELECT
                        sq.product_id AS product_id,
                        SUM(sq.quantity) AS qty_available
                    FROM stock_quant sq
                    JOIN stock_location sl ON sl.id = sq.location_id
                    WHERE sl.usage = 'internal'
                    GROUP BY sq.product_id
                ) quant ON quant.product_id = pp.id
                LEFT JOIN (
                    SELECT
                        sl2.product_id AS product_id,
                        MIN(sl2.expiry_date) AS nearest_expiry_date
                    FROM stock_lot sl2
                    WHERE sl2.expiry_date IS NOT NULL
                        AND sl2.expiry_date >= CURRENT_DATE
                    GROUP BY sl2.product_id
                ) lot ON lot.product_id = pp.id
                WHERE pt.is_hospital_medicine = true
            )
            """ % self._table,
            (str(EXPIRING_SOON_WINDOW_DAYS),),
        )
