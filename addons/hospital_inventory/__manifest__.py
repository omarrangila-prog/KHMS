# -*- coding: utf-8 -*-
{
    "name": "Hospital Inventory",
    "summary": "Medicine catalog and stock visibility: a thin clinical "
               "layer over Odoo's native Inventory app.",
    "description": """
Hospital Inventory
====================
Fifth addon of the Hospital Management System suite, built on top of
``hospital_base`` and Odoo's native ``stock`` app. Gives pharmacy/inventory
staff:

- Clinical fields on the product catalog (``generic_name``,
  ``dosage_form``, ``strength``, ``requires_prescription``,
  ``controlled_substance``, ``reorder_threshold``) added to
  ``product.template`` via ``_inherit`` -- a medicine *is* a
  ``product.product``, so stock, valuation, and purchasing stay 100%
  native Odoo Inventory (Phase 5 §6, Phase 6 §6).
- Expiry-date tracking on stock lots/serials (``hospital.medicine.batch``,
  ``_inherit = "stock.lot"``) -- no duplicate lot/batch model.
- An Inventory Dashboard (OWL KPI cards + a SQL-view-backed list/graph)
  showing on-hand quantity, reorder threshold, low-stock flag, nearest
  batch expiry, and an expiring-soon flag per medicine -- aggregated in
  PostgreSQL via a ``hospital.inventory.dashboard`` SQL view model
  (``_auto = False``), not looped in Python (Phase 5 §10).
- Two daily ``ir.cron`` jobs: an expiry alert (creates ``mail.activity``
  reminders for batches expiring within 30 days) and a low-stock alert
  (same, for products under their reorder threshold).
- A Pharmacy warehouse/location and a "Hospital Medicines" product
  category, plus a Low-Stock QWeb report.

**Important dependency note:** this module depends on ``hospital_base``
and ``stock`` only -- **not** ``hospital_doctor``. Per the Phase 4/6
module dependency graph, ``hospital_pharmacy`` is the module that later
depends on **both** ``hospital_doctor`` and ``hospital_inventory``
together; inverting that here would create a cycle. See the README
"Product/Stock dependency decision" section.
""",
    "version": "19.0.1.0.0",
    "category": "Hospital",
    "license": "LGPL-3",
    "author": "Hospital Management System Project",
    "website": "https://www.example.com",
    "depends": [
        "hospital_base",
        "stock",
    ],
    "data": [
        # security
        "security/hospital_inventory_security.xml",
        "security/ir.model.access.csv",
        # data
        "data/hospital_inventory_data.xml",
        "data/hospital_inventory_cron.xml",
        # views
        "views/product_template_views.xml",
        "views/hospital_medicine_batch_views.xml",
        "views/hospital_inventory_dashboard_views.xml",
        "views/hospital_inventory_menus.xml",
        # report
        "report/hospital_low_stock_report.xml",
        "report/hospital_low_stock_templates.xml",
    ],
    "demo": [
        "demo/hospital_inventory_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hospital_inventory/static/src/js/**/*",
            "hospital_inventory/static/src/xml/**/*",
            "hospital_inventory/static/src/scss/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
}
