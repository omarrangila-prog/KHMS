/** @odoo-module **/

import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function animateCount(el, target, duration = 600) {
    if (!el) return;
    const start = parseFloat(el.dataset.rawValue || "0") || 0;
    const delta = target - start;
    if (delta === 0) return;
    const t0 = performance.now();
    (function step(now) {
        const p = Math.min((now - t0) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(start + delta * eased);
        if (p < 1) requestAnimationFrame(step);
        else el.dataset.rawValue = target;
    })(performance.now());
}

export class NurseDashboard extends Component {
    static template = "hospital_nurse.NurseDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            nextPatient: false,
            waitingCount: 0,
            tasks: [],
        });
        onWillStart(() => this.loadDashboard());
        onMounted(() => { if (!this.state.loading) this._animateKpis(); });
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            await Promise.all([this._loadNextPatient(), this._loadTasks()]);
        } catch {
            this.state.error = true;
        } finally {
            this.state.loading = false;
            Promise.resolve().then(() => this._animateKpis());
        }
    }

    _animateKpis() {
        const el = this.el && this.el.querySelector('[data-kpi="waiting_count"]');
        animateCount(el, this.state.waitingCount, 650);
    }

    async _loadNextPatient() {
        const PRIORITY_ORDER = { emergency: 0, urgent: 1, normal: 2 };
        const visits = await this.orm.searchRead(
            "hospital.visit", [["state","=","waiting_nurse"]],
            ["visit_code","patient_id","priority","checkin_datetime"],
            { order: "checkin_datetime asc", limit: 50 }
        );
        this.state.waitingCount = visits.length;
        if (!visits.length) { this.state.nextPatient = false; return; }
        const ordered = [...visits].sort((a, b) => {
            const pa = PRIORITY_ORDER[a.priority] ?? 99;
            const pb = PRIORITY_ORDER[b.priority] ?? 99;
            return pa !== pb ? pa - pb : a.checkin_datetime < b.checkin_datetime ? -1 : 1;
        });
        const next = ordered[0];
        let age = false;
        if (next.patient_id) {
            const [patient] = await this.orm.read(
                "hospital.patient", [next.patient_id[0]], ["age","gender"]
            );
            age = patient ? patient.age : false;
        }
        this.state.nextPatient = { ...next, age };
    }

    async _loadTasks() {
        this.state.tasks = await this.orm.searchRead(
            "hospital.nurse.task", [["state","=","pending"]],
            ["name","visit_id","sequence"],
            { order: "sequence asc, id asc", limit: 20 }
        );
    }

    onRetry() { this.loadDashboard(); }

    async openVitalsEntry() {
        if (!this.state.nextPatient) return;
        await this.action.doAction("hospital_nurse.hospital_vitals_quick_entry_action", {
            additionalContext: { default_visit_id: this.state.nextPatient.id },
        });
        await this.loadDashboard();
    }

    async markTaskDone(taskId) {
        await this.orm.call("hospital.nurse.task","action_mark_done",[[taskId]]);
        await this._loadTasks();
    }

    openVisit(visitId) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hospital.visit",
            res_id: visitId, view_mode: "form", views: [[false,"form"]], target: "current",
        });
    }
}

registry.category("actions").add("hospital_nurse.nurse_dashboard", NurseDashboard);
