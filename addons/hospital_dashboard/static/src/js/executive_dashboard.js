/** @odoo-module **/

import { Component, onMounted, onWillStart, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Animate a numeric DOM element from its current displayed value to `target`
// over `duration` ms using requestAnimationFrame easing.
function animateCount(el, target, duration = 600, formatter = (v) => Math.round(v)) {
    if (!el) return;
    const start = parseFloat(el.dataset.rawValue || "0") || 0;
    const delta = target - start;
    if (delta === 0) return;
    const startTime = performance.now();

    function step(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // ease-out-cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = formatter(start + delta * eased);
        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            el.dataset.rawValue = target;
        }
    }
    requestAnimationFrame(step);
}

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
        this._prevKpi = null;
        onWillStart(() => this._fetchKpi());
        onMounted(() => {
            // If data already loaded before mount (unlikely but safe), animate.
            if (this.state.kpi) this._animateAllKpis();
        });
    }

    async _fetchKpi() {
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
        } catch {
            this.state.error = true;
        } finally {
            this.state.loading = false;
            // Animate after next microtask so DOM is rendered
            Promise.resolve().then(() => this._animateAllKpis());
        }
    }

    _animateAllKpis() {
        if (!this.state.kpi) return;
        const kpi = this.state.kpi;

        const sel = (id) => this.el && this.el.querySelector(`[data-kpi="${id}"]`);

        animateCount(sel("patients_today"), kpi.patients_today, 700);
        animateCount(sel("patients_this_week"), kpi.patients_this_week, 800);
        animateCount(
            sel("bed_occupancy_pct"),
            kpi.bed_occupancy_pct,
            750,
            (v) => v.toFixed(1) + "%"
        );
        animateCount(
            sel("avg_wait_minutes"),
            kpi.avg_wait_minutes,
            700,
            (v) => Math.round(v) + " min"
        );
    }

    onRetry() {
        this._fetchKpi();
    }

    formatPercent(value) {
        return value !== undefined && value !== null ? value.toFixed(1) + "%" : "-";
    }

    formatMinutes(value) {
        return value !== undefined && value !== null
            ? Math.round(value) + " min"
            : "-";
    }
}

registry.category("actions").add(
    "hospital_dashboard.executive_dashboard",
    ExecutiveDashboard
);
