# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class HospitalDashboardKpi(models.Model):
    """Read-only SQL-view aggregate backing the Executive Dashboard.

    Per Phase 5 §10 ("dashboard aggregates ... implemented as PostgreSQL
    SQL views ... computed in the database, not pulled into Python and
    looped"), this is an ``_auto = False`` model, following the exact
    pattern ``hospital_inventory.hospital_inventory_dashboard`` already
    established: ``init()`` creates a SQL ``VIEW``, every field maps 1:1
    onto a view column, and the model is inherently read-only (no
    ``create``/``write`` override, no unlink access in
    ``ir.model.access.csv``).

    One row per company (``res_company``), computing:

    - ``patients_today`` / ``patients_this_week``: distinct patients with
      a visit checked in within the window, from ``hospital_visit``.
    - ``bed_occupancy_pct``: occupied beds / total beds * 100, from
      ``hospital_bed`` (0 when a company has no beds at all, to avoid a
      divide-by-zero rather than a NULL that would render as a blank
      KPI card).
    - ``avg_wait_minutes``: average minutes between a visit's
      ``checkin_datetime`` and its first ``hospital_consultation``
      ``create_date``, for visits with at least one consultation -- the
      only "doctor wait time" signal that exists anywhere in the schema
      today (Phase 8 §4's "Avg Wait Time" KPI card).
    - ``ward_revenue_total``: sum of confirmed discharges' length-of-stay
      ward charge (``admission.length_of_stay_days * ward.daily_rate``)
      -- the only real billing-shaped number in the suite until a future
      billing module exists; deliberately not invented/estimated beyond
      that. Recomputed here directly from the stored
      ``length_of_stay_days``/``daily_rate`` columns rather than
      ``hospital.discharge.ward_charge_amount``, which is a non-stored
      compute field with no backing column a raw SQL view could join.
    """

    _name = "hospital.dashboard.kpi"
    _description = "Hospital Executive Dashboard KPI"
    _auto = False
    _order = "company_id"

    company_id = fields.Many2one(comodel_name="res.company", string="Company", readonly=True)
    patients_today = fields.Integer(string="Patients Today", readonly=True)
    patients_this_week = fields.Integer(string="Patients This Week", readonly=True)
    bed_occupancy_pct = fields.Float(string="Bed Occupancy %", readonly=True)
    avg_wait_minutes = fields.Float(string="Avg. Doctor Wait (minutes)", readonly=True)
    ward_revenue_total = fields.Monetary(
        string="Ward Revenue (confirmed discharges)",
        currency_field="currency_id",
        readonly=True,
    )
    currency_id = fields.Many2one(comodel_name="res.currency", string="Currency", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # NOTE on SQL safety (Phase 11 §1 "no raw SQL string
        # interpolation -- ever"): the only value interpolated via Python
        # string formatting is ``self._table``, this view's own table
        # name derived from ``_name`` -- a fixed, developer-controlled
        # identifier, never user input (placeholders bind *values*, not
        # identifiers, so this could not be parameterized even if it were
        # user input). There are no runtime-variable values in this
        # query at all, so no ``%s`` bound parameters are needed, unlike
        # hospital_inventory's dashboard view.
        #
        # One row per company via a CROSS JOIN of res_company with each
        # pre-aggregated sub-select (each already GROUP BY company_id),
        # LEFT JOINed so a company with zero visits/beds/discharges still
        # gets a row with zeroed KPIs rather than vanishing from the
        # dashboard entirely.
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    rc.id AS id,
                    rc.id AS company_id,
                    COALESCE(visits_today.cnt, 0) AS patients_today,
                    COALESCE(visits_week.cnt, 0) AS patients_this_week,
                    CASE
                        WHEN COALESCE(beds.total_beds, 0) = 0 THEN 0.0
                        ELSE (COALESCE(beds.occupied_beds, 0)::float
                              / beds.total_beds::float) * 100.0
                    END AS bed_occupancy_pct,
                    COALESCE(wait.avg_minutes, 0.0) AS avg_wait_minutes,
                    COALESCE(revenue.total, 0.0) AS ward_revenue_total,
                    rc.currency_id AS currency_id
                FROM res_company rc
                LEFT JOIN (
                    SELECT
                        v.company_id AS company_id,
                        COUNT(DISTINCT v.patient_id) AS cnt
                    FROM hospital_visit v
                    WHERE v.checkin_datetime >= CURRENT_DATE
                        AND v.checkin_datetime < (CURRENT_DATE + INTERVAL '1 day')
                    GROUP BY v.company_id
                ) visits_today ON visits_today.company_id = rc.id
                LEFT JOIN (
                    SELECT
                        v.company_id AS company_id,
                        COUNT(DISTINCT v.patient_id) AS cnt
                    FROM hospital_visit v
                    WHERE v.checkin_datetime >= (CURRENT_DATE - INTERVAL '6 days')
                        AND v.checkin_datetime < (CURRENT_DATE + INTERVAL '1 day')
                    GROUP BY v.company_id
                ) visits_week ON visits_week.company_id = rc.id
                LEFT JOIN (
                    SELECT
                        b.company_id AS company_id,
                        COUNT(*) AS total_beds,
                        COUNT(*) FILTER (WHERE b.state = 'occupied') AS occupied_beds
                    FROM hospital_bed b
                    GROUP BY b.company_id
                ) beds ON beds.company_id = rc.id
                LEFT JOIN (
                    SELECT
                        v.company_id AS company_id,
                        AVG(
                            EXTRACT(
                                EPOCH FROM (first_consult.first_create_date - v.checkin_datetime)
                            ) / 60.0
                        ) AS avg_minutes
                    FROM hospital_visit v
                    JOIN (
                        SELECT
                            c.visit_id AS visit_id,
                            MIN(c.create_date) AS first_create_date
                        FROM hospital_consultation c
                        GROUP BY c.visit_id
                    ) first_consult ON first_consult.visit_id = v.id
                    WHERE first_consult.first_create_date >= v.checkin_datetime
                    GROUP BY v.company_id
                ) wait ON wait.company_id = rc.id
                LEFT JOIN (
                    SELECT
                        d.company_id AS company_id,
                        SUM(a.length_of_stay_days * w.daily_rate) AS total
                    FROM hospital_discharge d
                    JOIN hospital_ipd_admission a ON a.id = d.admission_id
                    JOIN hospital_ward w ON w.id = a.ward_id
                    WHERE d.state = 'confirmed'
                    GROUP BY d.company_id
                ) revenue ON revenue.company_id = rc.id
            )
            """ % self._table
        )
