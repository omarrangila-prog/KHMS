/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

/**
 * Doctor Dashboard (Phase 8 §8): 3-pane layout -- queue (left, narrow),
 * active consultation context (center), collapsible patient-history panel
 * (right). Collapses to tabs on tablet (handled purely in SCSS via a
 * media query + the `activeMobileTab` state below, no separate template).
 * Pure read/aggregate display + "Call Next"/"Open" navigation -- it never
 * mutates a record itself; opening a patient hands off to the real
 * hospital.consultation form (and from there, hospital.visit's own
 * action_* methods), per Phase 11 §1 "no business logic in views".
 */
export class DoctorDashboard extends Component {
    static template = "hospital_doctor.DoctorDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.user = useService("user");
        this.state = useState({
            loading: true,
            error: false,
            queue: [],
            seenToday: 0,
            activeMobileTab: "queue",
            outcomeBreakdown: [],
        });
        this.outcomeChartRef = useRef("outcomeChart");
        this._outcomeChart = null;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboard();
        });
        useEffect(
            () => this._renderChart(),
            () => [this.outcomeChartRef.el, this.state.loading]
        );
        onWillUnmount(() => {
            if (this._outcomeChart) this._outcomeChart.destroy();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            await Promise.all([
                this._loadQueue(),
                this._loadSeenToday(),
                this._loadOutcomeBreakdown(),
            ]);
        } catch (error) {
            this.state.error = true;
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    async _loadOutcomeBreakdown() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayStr = today.toISOString().slice(0, 19).replace("T", " ");
        const baseDomain = [
            ["doctor_id.user_id", "=", this.user.userId],
            ["create_date", ">=", todayStr],
        ];
        const fields = [
            ["outcome_prescribe", "Prescribed"],
            ["outcome_lab_requested", "Lab"],
            ["outcome_radiology_requested", "Radiology"],
            ["outcome_admit_requested", "Admit"],
            ["outcome_discharge", "Discharge"],
        ];
        const counts = await Promise.all(
            fields.map(([field]) =>
                this.orm.searchCount("hospital.consultation", [...baseDomain, [field, "=", true]])
            )
        );
        this.state.outcomeBreakdown = fields
            .map(([, label], i) => ({ label, value: counts[i] }))
            .filter((r) => r.value > 0);
    }

    _renderChart() {
        if (typeof Chart === "undefined") return;
        if (this._outcomeChart) {
            this._outcomeChart.destroy();
            this._outcomeChart = null;
        }
        if (!this.outcomeChartRef.el || !this.state.outcomeBreakdown.length) return;

        this._outcomeChart = new Chart(this.outcomeChartRef.el, {
            type: "bar",
            data: {
                labels: this.state.outcomeBreakdown.map((r) => r.label),
                datasets: [
                    {
                        label: "Consultations Today",
                        data: this.state.outcomeBreakdown.map((r) => r.value),
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
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }

    async _loadQueue() {
        const PRIORITY_ORDER = { emergency: 0, urgent: 1, normal: 2 };
        const visits = await this.orm.searchRead(
            "hospital.visit",
            [
                ["doctor_id.user_id", "=", this.user.userId],
                ["state", "in", ["waiting_doctor", "in_progress_multi"]],
            ],
            ["visit_code", "patient_id", "priority", "checkin_datetime", "state"],
            { order: "checkin_datetime asc", limit: 100 }
        );
        const ordered = [...visits].sort((a, b) => {
            const pa = PRIORITY_ORDER[a.priority] ?? 99;
            const pb = PRIORITY_ORDER[b.priority] ?? 99;
            if (pa !== pb) {
                return pa - pb;
            }
            return a.checkin_datetime < b.checkin_datetime ? -1 : 1;
        });
        this.state.queue = ordered;
    }

    async _loadSeenToday() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const count = await this.orm.searchCount("hospital.consultation", [
            ["doctor_id.user_id", "=", this.user.userId],
            ["state", "=", "done"],
            ["create_date", ">=", today.toISOString().slice(0, 19).replace("T", " ")],
        ]);
        this.state.seenToday = count;
    }

    onRetry() {
        this.loadDashboard();
    }

    setMobileTab(tab) {
        this.state.activeMobileTab = tab;
    }

    async callNext() {
        if (!this.state.queue.length) {
            return;
        }
        await this.openConsultation(this.state.queue[0].id);
    }

    async openConsultation(visitId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hospital.consultation",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: { default_visit_id: visitId },
        });
        await this.loadDashboard();
    }

    openVisit(visitId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hospital.visit",
            res_id: visitId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("hospital_doctor.doctor_dashboard", DoctorDashboard);
