/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

const BED_STATE_COLORS = {
    vacant: "#30D158",
    occupied: "#FF453A",
    reserved: "#FF9F0A",
    cleaning: "#5AC8FA",
};
const BED_STATE_LABELS = {
    vacant: "Vacant",
    occupied: "Occupied",
    reserved: "Reserved",
    cleaning: "Cleaning",
};

/**
 * Ward Dashboard (Phase 8 §14): bed occupancy grid grouped by ward,
 * color-coded by bed status (vacant/occupied/reserved/cleaning).
 *
 * Clicking a vacant bed opens the Admission wizard pre-filled with that
 * bed/ward; clicking an occupied bed opens the Discharge wizard for its
 * current admission. Business logic (bed assignment, the DB-level
 * partial unique index race-safety) lives entirely in
 * hospital.ipd.admission's Python methods (Phase 11 §1) -- this
 * component only reads data and delegates to the wizard actions, then
 * reloads on wizard close (same pattern as hospital_pharmacy's
 * PharmacyDashboard).
 */
export class WardDashboard extends Component {
    static template = "hospital_ipd.WardDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            wards: [],
        });
        this.occupancyChartRef = useRef("occupancyChart");
        this._occupancyChart = null;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboard();
        });
        useEffect(
            () => this._renderChart(),
            () => [this.occupancyChartRef.el, this.state.loading]
        );
        onWillUnmount(() => {
            if (this._occupancyChart) this._occupancyChart.destroy();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            await this._loadWards();
        } catch (error) {
            this.state.error = true;
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    _renderChart() {
        if (typeof Chart === "undefined") return;
        if (this._occupancyChart) {
            this._occupancyChart.destroy();
            this._occupancyChart = null;
        }
        if (!this.occupancyChartRef.el || !this.state.wards.length) return;

        const labels = this.state.wards.map((w) => w.name);
        const states = ["vacant", "occupied", "reserved", "cleaning"];
        const datasets = states.map((stateKey) => ({
            label: BED_STATE_LABELS[stateKey],
            data: this.state.wards.map(
                (w) => w.beds.filter((b) => b.state === stateKey).length
            ),
            backgroundColor: BED_STATE_COLORS[stateKey],
            borderRadius: 4,
        }));

        this._occupancyChart = new Chart(this.occupancyChartRef.el, {
            type: "bar",
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 10, font: { size: 11 }, usePointStyle: true },
                    },
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    async _loadWards() {
        const wards = await this.orm.searchRead(
            "hospital.ward",
            [["active", "=", true]],
            ["name", "code", "ward_type", "bed_count", "occupied_bed_count"],
            { order: "name asc" }
        );
        const beds = await this.orm.searchRead(
            "hospital.bed",
            [["ward_id", "in", wards.map((w) => w.id)]],
            ["ward_id", "bed_number", "state", "current_patient_id", "current_admission_id"],
            { order: "ward_id asc, bed_number asc" }
        );
        this.state.wards = wards.map((ward) => ({
            ...ward,
            beds: beds.filter((bed) => bed.ward_id[0] === ward.id),
        }));
    }

    onRetry() {
        this.loadDashboard();
    }

    getBedStatusClass(bed) {
        return {
            vacant: "o_hospital_bed_vacant",
            occupied: "o_hospital_bed_occupied",
            reserved: "o_hospital_bed_reserved",
            cleaning: "o_hospital_bed_cleaning",
        }[bed.state] || "";
    }

    async onBedClick(bed) {
        if (bed.state === "vacant") {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "hospital.admission.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: { default_ward_id: bed.ward_id[0], default_bed_id: bed.id },
            }, { onClose: () => this.loadDashboard() });
        } else if (bed.state === "occupied" && bed.current_admission_id) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "hospital.discharge.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: { active_model: "hospital.ipd.admission", active_id: bed.current_admission_id[0] },
            }, { onClose: () => this.loadDashboard() });
        }
    }

}

registry.category("actions").add("hospital_ipd.ward_dashboard", WardDashboard);
