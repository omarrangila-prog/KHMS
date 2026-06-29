/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Executive Dashboard (Phase 6 §10): admin-level KPI card grid rolling
 * up patient volume, bed occupancy, average doctor wait time, and ward
 * revenue across the whole hospital.
 *
 * All KPI numbers are computed in PostgreSQL by the
 * hospital.dashboard.kpi SQL-view model (Phase 5 §10) - this component
 * only reads the one row for the current company and renders it.
 */
export class ExecutiveDashboard extends Component {
    static template = "hospital_dashboard.ExecutiveDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: false,
            kpi: null,
        });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const rows = await this.orm.searchRead(
                "hospital.dashboard.kpi",
                [],
                [
                    "patients_today",
                    "patients_this_week",
                    "bed_occupancy_pct",
                    "avg_wait_minutes",
                    "ward_revenue_total",
                ],
                { limit: 1 }
            );
            this.state.kpi = rows[0] || null;
        } catch (error) {
            this.state.error = true;
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    onRetry() {
        this.loadDashboard();
    }

    formatPercent(value) {
        return value !== undefined && value !== null ? value.toFixed(1) + "%" : "-";
    }

    formatMinutes(value) {
        return value !== undefined && value !== null ? value.toFixed(0) + " min" : "-";
    }
}

registry.category("actions").add(
    "hospital_dashboard.executive_dashboard",
    ExecutiveDashboard
);
