/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

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

const DONUT_COLORS = ["#0A84FF", "#30D158", "#FF9F0A", "#BF5AF2", "#5AC8FA", "#FF453A", "#5E5CE6"];

export class ExecutiveDashboard extends Component {
    static template = "hospital_dashboard.ExecutiveDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: false,
            kpi: null,
            visitsByDept: [],
            bedsByWard: [],
        });
        this.deptChartRef = useRef("deptChart");
        this.wardChartRef = useRef("wardChart");
        this._deptChart = null;
        this._wardChart = null;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this._fetchKpi();
        });
        // useEffect re-runs after every DOM patch where the canvas refs
        // become available (e.g. once loading flips false and OWL renders
        // the chart cards), matching the pattern used by Odoo's own
        // graph_renderer.js.
        useEffect(
            () => this._renderCharts(),
            () => [this.deptChartRef.el, this.wardChartRef.el, this.state.loading]
        );
        onWillUnmount(() => {
            if (this._deptChart) this._deptChart.destroy();
            if (this._wardChart) this._wardChart.destroy();
        });
    }

    async _fetchKpi() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const [kpiRows, deptGroups, wardGroups] = await Promise.all([
                this.orm.searchRead(
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
                ),
                this.orm.formattedReadGroup(
                    "hospital.visit",
                    [["checkin_datetime", ">=", this._todayStart()]],
                    ["department_id"],
                    ["__count"]
                ),
                this.orm.formattedReadGroup("hospital.bed", [], ["ward_id"], ["__count"]),
            ]);
            this.state.kpi = kpiRows[0] || null;
            this.state.visitsByDept = deptGroups
                .filter((g) => g.department_id)
                .map((g) => ({ label: g.department_id[1], value: g.__count }));
            this.state.bedsByWard = wardGroups
                .filter((g) => g.ward_id)
                .map((g) => ({ label: g.ward_id[1], value: g.__count }));
        } catch {
            this.state.error = true;
        } finally {
            this.state.loading = false;
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

    _renderCharts() {
        if (typeof Chart === "undefined") return;

        if (this._deptChart) {
            this._deptChart.destroy();
            this._deptChart = null;
        }
        if (this._wardChart) {
            this._wardChart.destroy();
            this._wardChart = null;
        }

        if (this.deptChartRef.el && this.state.visitsByDept.length) {
            this._deptChart = new Chart(this.deptChartRef.el, {
                type: "doughnut",
                data: {
                    labels: this.state.visitsByDept.map((r) => r.label),
                    datasets: [
                        {
                            data: this.state.visitsByDept.map((r) => r.value),
                            backgroundColor: DONUT_COLORS,
                            borderWidth: 2,
                            borderColor: "#ffffff",
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "68%",
                    plugins: {
                        legend: {
                            position: "right",
                            labels: { boxWidth: 10, font: { size: 11 }, usePointStyle: true },
                        },
                    },
                },
            });
        }

        if (this.wardChartRef.el && this.state.bedsByWard.length) {
            this._wardChart = new Chart(this.wardChartRef.el, {
                type: "bar",
                data: {
                    labels: this.state.bedsByWard.map((r) => r.label),
                    datasets: [
                        {
                            label: "Beds",
                            data: this.state.bedsByWard.map((r) => r.value),
                            backgroundColor: "#0A84FF",
                            borderRadius: 6,
                            maxBarThickness: 28,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                    },
                },
            });
        }
    }

    _todayStart() {
        return new Date().toISOString().slice(0, 10) + " 00:00:00";
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
