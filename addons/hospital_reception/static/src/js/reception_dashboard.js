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

export class ReceptionDashboard extends Component {
    static template = "hospital_reception.ReceptionDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            kpi: { waiting: 0, in_consult: 0, completed_today: 0 },
            queueByDoctor: [],
            appointments: [],
        });
        onWillStart(() => this.loadDashboard());
        onMounted(() => { if (!this.state.loading) this._animateKpis(); });
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            await Promise.all([
                this._loadKpis(),
                this._loadQueue(),
                this._loadAppointments(),
            ]);
        } catch {
            this.state.error = true;
        } finally {
            this.state.loading = false;
            Promise.resolve().then(() => this._animateKpis());
        }
    }

    _animateKpis() {
        const sel = (attr) =>
            this.el && this.el.querySelector(`[data-kpi="${attr}"]`);
        animateCount(sel("waiting"),         this.state.kpi.waiting,         650);
        animateCount(sel("in_consult"),      this.state.kpi.in_consult,      700);
        animateCount(sel("completed_today"), this.state.kpi.completed_today, 750);
    }

    async _loadKpis() {
        const [w, c, d] = await Promise.all([
            this.orm.formattedReadGroup("hospital.visit", [["state","=","waiting_nurse"]], [], ["__count"]),
            this.orm.formattedReadGroup("hospital.visit", [["state","in",["waiting_doctor","in_progress_multi"]]], [], ["__count"]),
            this.orm.formattedReadGroup("hospital.visit", [["state","=","done"],["checkin_datetime",">=",this._todayStart()]], [], ["__count"]),
        ]);
        this.state.kpi.waiting         = w[0] ? w[0].__count : 0;
        this.state.kpi.in_consult      = c[0] ? c[0].__count : 0;
        this.state.kpi.completed_today = d[0] ? d[0].__count : 0;
    }

    async _loadQueue() {
        const groups = await this.orm.formattedReadGroup(
            "hospital.visit",
            [["state","in",["waiting_nurse","waiting_doctor","in_progress_multi"]]],
            ["doctor_id"], ["__count"]
        );
        const queueByDoctor = [];
        for (const group of groups) {
            const visits = await this.orm.searchRead(
                "hospital.visit", group.__domain,
                ["visit_code","patient_id","priority","checkin_datetime"],
                { order: "checkin_datetime asc", limit: 8 }
            );
            queueByDoctor.push({
                doctorName: group.doctor_id ? group.doctor_id[1] : "Unassigned",
                doctorId:   group.doctor_id ? group.doctor_id[0] : false,
                count: group.__count,
                visits,
            });
        }
        this.state.queueByDoctor = queueByDoctor;
    }

    async _loadAppointments() {
        this.state.appointments = await this.orm.searchRead(
            "hospital.appointment",
            [["scheduled_datetime",">=",this._todayStart()],["scheduled_datetime","<=",this._todayEnd()]],
            ["name","patient_id","doctor_id","scheduled_datetime","state"],
            { order: "scheduled_datetime asc", limit: 20 }
        );
    }

    _todayStart() { return new Date().toISOString().slice(0,10) + " 00:00:00"; }
    _todayEnd()   { return new Date().toISOString().slice(0,10) + " 23:59:59"; }

    onRetry() { this.loadDashboard(); }

    openNewRegistration() {
        this.action.doAction("hospital_reception.hospital_patient_registration_wizard_action");
    }
    openSearchPatients() {
        this.action.doAction("hospital_base.hospital_patient_action");
    }
    openVisit(visitId) {
        this.action.doAction({ type:"ir.actions.act_window", res_model:"hospital.visit", res_id:visitId, view_mode:"form", views:[[false,"form"]], target:"current" });
    }
    openAppointment(apptId) {
        this.action.doAction({ type:"ir.actions.act_window", res_model:"hospital.appointment", res_id:apptId, view_mode:"form", views:[[false,"form"]], target:"current" });
    }
    async checkInAppointment(apptId) {
        await this.orm.call("hospital.appointment","action_check_in",[[apptId]]);
        await this.loadDashboard();
    }
}

registry.category("actions").add("hospital_reception.reception_dashboard", ReceptionDashboard);
