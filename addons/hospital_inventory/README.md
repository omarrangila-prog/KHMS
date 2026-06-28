# Hospital Inventory

## Purpose

`hospital_inventory` is the pharmacy/stock-visibility addon of the
Hospital Management System suite for Odoo 19. It is a thin clinical
layer over Odoo's native `stock` app: it adds medicine-specific fields
to the product catalog, expiry tracking to stock lots/serials, and a
dashboard that aggregates on-hand quantity, reorder thresholds, and
batch expiry — all without introducing a parallel inventory system.

This module is **module 5 of 12** in the project's build order.

## Dependencies

- `hospital_base`
- `stock` (Odoo's native Inventory app)

**Why not `hospital_doctor`:** per the Phase 4/6 module dependency
graph, `hospital_inventory` depends on `hospital_base` + `stock` only.
`hospital_pharmacy` (a later module, not yet built) is the one that
depends on **both** `hospital_doctor` and `hospital_inventory` together,
wiring dispensing against `hospital.prescription.line` to real stock
moves. If this module depended on `hospital_doctor` to read
`hospital.prescription.line.medicine_id`, it would invert that graph and
create a cycle once `hospital_pharmacy` is added. `hospital_doctor`
already references `product.product` directly (it depends on bare
`product`, not `stock`), so no coupling back to it is needed here.

## Key Models

| Model | Purpose |
|---|---|
| `product.template` (`_inherit`) | Adds clinical/pharmacy fields: `is_hospital_medicine`, `generic_name`, `dosage_form`, `strength`, `requires_prescription`, `controlled_substance`, `reorder_threshold`. A medicine *is* a `product.product` — stock, valuation, and purchasing stay 100% native Odoo Inventory. |
| `hospital.medicine.batch` (`_inherit = "stock.lot"`) | Adds `expiry_date` plus non-stored `is_expiring_soon`/`is_expired` computed+searchable fields. No new batch/lot model — `stock.lot` already is the per-batch tracking record. |
| `hospital.inventory.dashboard` (`_auto = False`) | Read-only SQL-view model aggregating on-hand quantity, reorder threshold, low-stock flag, nearest batch expiry, and expiring-soon/expired flags, one row per hospital-medicine product variant. Built via a `CREATE OR REPLACE VIEW` in `init()`, not a Python loop. |

## Design Decisions

### Why `stock.lot` is extended instead of a new batch model

A standalone `hospital.medicine.batch` model would duplicate everything
`stock.lot` already provides (batch/serial number, `product_id`,
`quant_ids` for on-hand-by-location) and would need its own stock-move
wiring to stay in sync with real inventory transactions. Extending
`stock.lot` via `_inherit` means this module only adds the one field
`stock.lot` doesn't already have: `expiry_date`. Odoo also ships an
optional `product_expiry` module with its own `expiration_date` field,
but this module does not depend on it, so `expiry_date` is non-colliding
and the module's dependency footprint stays at `hospital_base` + `stock`
only.

`is_expiring_soon`/`is_expired` are deliberately **not stored** fields:
a stored boolean keyed off "now" would go stale the instant the clock
ticks past midnight without a write on the record. They are computed
live (a single cheap date comparison per record) with `search()`
implementations so list-view filters and domains still work efficiently
without ever being stored. The dashboard SQL view performs the
equivalent comparison directly in SQL against `CURRENT_DATE`, which is
the only place per-row Python looping would actually be a performance
concern (aggregate reporting across the whole catalog).

### Why the dashboard is a SQL view, not a stored compute

Per the project's database design principle that dashboard aggregates
should be "computed in the database, not pulled into Python and
looped," `hospital.inventory.dashboard` is `_auto = False`: Odoo never
creates a table for it, and `init()` issues a `CREATE OR REPLACE VIEW`
instead. Low-stock and expiring-soon/expired flags are plain SQL boolean
expressions evaluated against `CURRENT_DATE`/on-hand quantity. This
avoids a stored `is_low_stock` field on `product.template` that would
require comparing `qty_available` (which changes via stock moves, not
writes on the template) against `reorder_threshold` in a recompute that
would rarely invalidate correctly.

The exact SQL used in `models/hospital_inventory_dashboard.py`'s
`init()`:

```sql
CREATE OR REPLACE VIEW hospital_inventory_dashboard AS (
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
            AND lot.nearest_expiry_date <= (CURRENT_DATE + ('30' || ' days')::interval)
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
```

(`30` above is the real, bound query parameter value at runtime — the
expiry window is passed via `cr.execute(query, (params,))`, not
string-formatted, even though the table name itself is interpolated via
Python `%`, since placeholders can only bind values, not identifiers —
the same convention Odoo core uses for its own SQL-view `init()` hooks.)

Join logic:
- `product_product`/`product_template` — one row per medicine variant,
  filtered to `is_hospital_medicine = true` so the dashboard never
  surfaces unrelated catalog products.
- `stock_quant` — `LEFT JOIN` pre-aggregated (`SUM`) per product across
  *internal* locations only (`usage = 'internal'`), so customer/
  supplier/virtual locations never inflate on-hand counts; `COALESCE`
  to `0` for medicines with no quants yet.
- `stock_lot` — `LEFT JOIN` pre-aggregated (`MIN`) per product to find
  the single soonest non-expired `expiry_date`. Already-expired batches
  are reported separately via the `is_expired` `EXISTS` sub-select, so
  an old expired batch never hides a newer, still-valid one from the
  "nearest expiry" column.

## Security / ACL Decision

`group_hospital_inventory_manager` (category: Hospital) uses
`implied_ids` to automatically grant **both**:

1. `hospital_base.group_hospital_user` — the established hospital-suite
   pattern every other `hospital_*` group follows.
2. `stock.group_stock_manager` — Odoo's own native Inventory manager
   group.

This was the chosen alternative to manual per-user dual-group
assignment at the user-record level. Implying `stock.group_stock_manager`
means assigning a user the **Hospital Inventory Manager** group is
sufficient on its own to unlock the native Inventory app (adjust stock,
view the Pharmacy warehouse, manage `stock.lot` expiry dates, run
inventory adjustments, etc.) — there is no separate, easy-to-forget step
of also manually checking an Odoo-native group on the user form.

Odoo's native ACLs on `product.template`/`stock.lot`/`stock.quant` are
already broad and stock-group gated; this module does not re-declare or
override them, to avoid duplicated permission configuration that could
drift from upstream. The only new ACL this module declares is on its own
`hospital.inventory.dashboard` SQL-view model (read-only for
manager/admin/user groups — there is nothing to write back to since the
model has no underlying table). No `ir.rule` is declared for the
dashboard model: it has no stored `company_id` written by the ORM (its
`company_id` column is read straight off `product_template` in the view
query), and it already only ever surfaces `is_hospital_medicine`
products, so `product.template`'s own multi-company behavior is
inherited as-is.

## Services (as `ir.cron`)

Per the project's services-as-cron convention (no literal Python service
classes), two daily `ir.cron` jobs implement the spec's
`ExpiryAlertService` and `LowStockAlertService`:

- **ExpiryAlertService** → `hospital.medicine.batch._cron_check_expiring_batches()`
  — creates a `mail.activity` reminder (assigned to every
  Hospital Inventory Manager user) for each batch whose `expiry_date`
  falls within the next 30 days, skipping batches that already have a
  pending reminder so re-runs stay idempotent.
- **LowStockAlertService** → `product.template._cron_check_low_stock()`
  — reads the already-computed `hospital.inventory.dashboard` view (no
  duplicate Python-side qty/threshold comparison) and creates a
  `mail.activity` reminder for each low-stock medicine, with the same
  idempotency guard.

## Data

- **Hospital Medicines** (`product.category`), a standalone top-level
  category (Odoo 19 ships no single catch-all "All" root to nest under,
  matching the convention of its own Goods/Services/Expenses
  categories).
- **Pharmacy** (`stock.warehouse`, code `PHM`) — creating a warehouse
  automatically creates its own view/input/output/stock locations.
- **Pharmacy Store** (`stock.location`), a named sub-location under the
  Pharmacy warehouse's internal stock location, for a specific
  dispensing/receiving shelf distinct from the warehouse's generic
  top-level internal location.

## Demo Data

50 demo medicines as `product.product` records (varied `dosage_form`/
`strength`), each with one `hospital.medicine.batch` (`stock.lot`)
batch. Expiry dates cycle through three buckets: already expired,
expiring within 30 days, and safely far out, so the Expiry Alerts screen
has a realistic mixed set out of the box. Stock is seeded via
`stock.quant.inventory_quantity` (44 of the 50 medicines have stock —
every 7th medicine is deliberately left at zero, and several others sit
at or below their `reorder_threshold`) so the Inventory Dashboard's
low-stock list is non-trivial on a fresh demo install.

## Views & Menus

`Hospital -> Inventory` (visible to `group_hospital_inventory_manager`):

- **Dashboard** — OWL KPI-card client action (Low Stock / Expiring Soon
  counts, "Adjust Stock" linking to the native Inventory app, a
  drill-down table), falling back gracefully to an empty state when all
  stock levels are healthy.
- **Medicines** — filtered list/kanban/form action
  (`is_hospital_medicine = True`) extending the standard product form
  with a "Hospital Medicine" tab.
- **Stock Levels** — list+graph view directly on the
  `hospital.inventory.dashboard` SQL-view model, for export, grouping,
  and filtering beyond what the KPI-card view replicates.
- **Expiry Alerts** — filtered view on `stock.lot` for hospital medicines
  that are expiring soon or already expired.

## Reports

**Low Stock Report** (QWeb, bound to `hospital.inventory.dashboard`) —
lists every medicine at or below its reorder threshold.

## Install / Configuration

1. Install `hospital_base` and `stock` first (the latter ships with
   Odoo; no extra setup beyond enabling the Inventory app).
2. Install `hospital_inventory` from the Apps menu.
3. Assign the **Hospital Inventory Manager** group to pharmacy/inventory
   staff. This single group also grants native Inventory app access (see
   the ACL decision above) — no separate manual group assignment is
   needed.
4. Go to **Hospital -> Inventory -> Dashboard** to review stock levels
   and expiry alerts.

## Documented Limitations

- This module does not implement dispensing against a prescription —
  that wiring (and the `controlled_substance` dispensing safeguards) is
  `hospital_pharmacy`'s responsibility once it exists.
- The Inventory Dashboard's KPI-card OWL component reads up to 200 rows
  client-side for the drill-down table; very large catalogs should use
  the **Stock Levels** list+graph action instead, which supports normal
  Odoo pagination/grouping/export.
