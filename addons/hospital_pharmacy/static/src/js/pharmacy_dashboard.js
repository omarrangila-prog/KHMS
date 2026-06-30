/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useState, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

const LINE_STATE_COLORS = {
    pending: "#AEAEB2",
    dispensed: "#30D158",
    partial: "#0A84FF",
    backordered: "#FF9F0A",
    cancelled: "#FF453A",
};
const LINE_STATE_LABELS = {
    pending: "Pending",
    dispensed: "Dispensed",
    partial: "Partial",
    backordered: "Backordered",
    cancelled: "Cancelled",
};

/**
 * Pharmacy Dashboard (Phase 8 §12): split view.
 *
 * Left pane: queue of prescriptions with pending/partial lines.
 * Right pane: dispense detail for the selected prescription, showing
 *   per-line stock badges and actions.
 *
 * Keyboard shortcuts (Phase 8 §12):
 *   D — open Dispense wizard for the focused/selected prescription.
 *   A — open Dispense All wizard for the focused/selected prescription.
 *
 * Business logic (allergy checks, stock moves, state propagation) lives
 * entirely in the Python dispense() method (Phase 11 §1 "no business
 * logic in views"). This component only reads data and delegates to
 * the wizard action, which calls the model method in turn.
 */
export class PharmacyDashboard extends Component {
    static template = "hospital_pharmacy.PharmacyDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            queue: [],
            selectedPrescriptionId: null,
            selectedLines: [],
            lineStatusBreakdown: [],
        });
        this.statusChartRef = useRef("statusChart");
        this._statusChart = null;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboard();
        });
        onMounted(() => this._bindKeyboardShortcuts());
        useEffect(
            () => this._renderChart(),
            () => [this.statusChartRef.el, this.state.loading]
        );
        onWillUnmount(() => {
            if (this._statusChart) this._statusChart.destroy();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            await Promise.all([this._loadQueue(), this._loadLineStatusBreakdown()]);
            if (
                this.state.selectedPrescriptionId &&
                !this.state.queue.find(
                    (p) => p.id === this.state.selectedPrescriptionId
                )
            ) {
                this.state.selectedPrescriptionId = null;
                this.state.selectedLines = [];
            }
        } catch (error) {
            this.state.error = true;
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    async _loadLineStatusBreakdown() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayStr = today.toISOString().slice(0, 19).replace("T", " ");
        const groups = await this.orm.formattedReadGroup(
            "hospital.prescription.line",
            [["create_date", ">=", todayStr]],
            ["state"], ["__count"]
        );
        this.state.lineStatusBreakdown = groups
            .filter((g) => g.__count > 0)
            .map((g) => ({
                label: LINE_STATE_LABELS[g.state] || g.state,
                value: g.__count,
                color: LINE_STATE_COLORS[g.state] || "#8E8E93",
            }));
    }

    _renderChart() {
        if (typeof Chart === "undefined") return;
        if (this._statusChart) {
            this._statusChart.destroy();
            this._statusChart = null;
        }
        if (!this.statusChartRef.el || !this.state.lineStatusBreakdown.length) return;

        this._statusChart = new Chart(this.statusChartRef.el, {
            type: "doughnut",
            data: {
                labels: this.state.lineStatusBreakdown.map((r) => r.label),
                datasets: [
                    {
                        data: this.state.lineStatusBreakdown.map((r) => r.value),
                        backgroundColor: this.state.lineStatusBreakdown.map((r) => r.color),
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
                        position: "bottom",
                        labels: { boxWidth: 10, font: { size: 11 }, usePointStyle: true },
                    },
                },
            },
        });
    }

    async _loadQueue() {
        const prescriptions = await this.orm.searchRead(
            "hospital.prescription",
            [["state", "in", ["draft", "partially_dispensed"]]],
            [
                "patient_id",
                "doctor_id",
                "state",
                "create_date",
                "line_ids",
            ],
            { order: "create_date asc", limit: 100 }
        );
        this.state.queue = prescriptions;
        if (
            !this.state.selectedPrescriptionId &&
            prescriptions.length
        ) {
            await this.selectPrescription(prescriptions[0].id);
        } else if (this.state.selectedPrescriptionId) {
            await this._loadLines(this.state.selectedPrescriptionId);
        }
    }

    async selectPrescription(prescriptionId) {
        this.state.selectedPrescriptionId = prescriptionId;
        await this._loadLines(prescriptionId);
    }

    async _loadLines(prescriptionId) {
        const lines = await this.orm.searchRead(
            "hospital.prescription.line",
            [
                ["prescription_id", "=", prescriptionId],
                ["state", "not in", ["dispensed", "cancelled"]],
            ],
            [
                "medicine_id",
                "qty_prescribed",
                "qty_dispensed",
                "qty_on_hand_at_pharmacy",
                "has_allergy_conflict",
                "state",
            ],
            { order: "id asc" }
        );
        this.state.selectedLines = lines;
    }

    onRetry() {
        this.loadDashboard();
    }

    getStockBadgeClass(line) {
        if (line.qty_on_hand_at_pharmacy === 0) {
            return "badge text-bg-danger";
        }
        const outstanding = line.qty_prescribed - line.qty_dispensed;
        if (line.qty_on_hand_at_pharmacy < outstanding) {
            return "badge text-bg-warning";
        }
        return "badge text-bg-success";
    }

    async openDispenseWizard(prescriptionId) {
        if (!prescriptionId) return;
        await this.action.doAction(
            "hospital_pharmacy.hospital_prescription_dispense_wizard_action",
            {
                additionalContext: { active_id: prescriptionId },
                onClose: () => this.loadDashboard(),
            }
        );
    }

    async openDispenseAllWizard(prescriptionId) {
        if (!prescriptionId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hospital.prescription.dispense.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                active_id: prescriptionId,
                dispense_all_on_open: true,
            },
        }, {
            onClose: () => this.loadDashboard(),
        });
    }

    _bindKeyboardShortcuts() {
        document.addEventListener("keydown", (e) => {
            if (
                !this.state.selectedPrescriptionId ||
                e.target.tagName === "INPUT" ||
                e.target.tagName === "TEXTAREA" ||
                e.target.isContentEditable
            ) {
                return;
            }
            if (e.key === "d" || e.key === "D") {
                e.preventDefault();
                this.openDispenseWizard(this.state.selectedPrescriptionId);
            }
            if (e.key === "a" || e.key === "A") {
                e.preventDefault();
                this.openDispenseAllWizard(this.state.selectedPrescriptionId);
            }
        });
    }
}

registry.category("actions").add(
    "hospital_pharmacy.pharmacy_dashboard",
    PharmacyDashboard
);
