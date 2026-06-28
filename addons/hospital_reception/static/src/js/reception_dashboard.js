/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Reception Dashboard (Phase 8 §1): KPI strip (waiting / in-consult /
 * completed today), a live queue grouped by doctor, and today's
 * appointments. Pure read/aggregate display -- every action (check-in,
 * cancel, register) delegates to the existing model methods/wizards via
 * the action service, per Phase 11 §1 "no business logic in views or
 * controllers".
 */
export class ReceptionDashboard extends Component {
    static template = "hospital_reception.ReceptionDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            kpi: {
                waiting: 0,
                in_consult: 0,
                completed_today: 0,
            },
            queueByDoctor: [],
            appointments: [],
        });
        onWillStart(() => this.loadDashboard());
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
        } catch (error) {
            this.state.error = true;
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    async _loadKpis() {
        const [waitingGroups, inConsultGroups, completedGroups] = await Promise.all([
            this.orm.readGroup(
                "hospital.visit",
                [["state", "=", "waiting_nurse"]],
                ["id"],
                []
            ),
            this.orm.readGroup(
                "hospital.visit",
                [["state", "in", ["waiting_doctor", "in_progress_multi"]]],
                ["id"],
                []
            ),
            this.orm.readGroup(
                "hospital.visit",
                [
                    ["state", "=", "done"],
                    ["checkin_datetime", ">=", this._todayStart()],
                ],
                ["id"],
                []
            ),
        ]);
        this.state.kpi.waiting = waitingGroups[0] ? waitingGroups[0].__count : 0;
        this.state.kpi.in_consult = inConsultGroups[0] ? inConsultGroups[0].__count : 0;
        this.state.kpi.completed_today = completedGroups[0] ? completedGroups[0].__count : 0;
    }

    async _loadQueue() {
        const groups = await this.orm.readGroup(
            "hospital.visit",
            [["state", "in", ["waiting_nurse", "waiting_doctor", "in_progress_multi"]]],
            ["id"],
            ["doctor_id"]
        );
        const queueByDoctor = [];
        for (const group of groups) {
            const domain = group.__domain;
            const visits = await this.orm.searchRead(
                "hospital.visit",
                domain,
                ["visit_code", "patient_id", "priority", "checkin_datetime"],
                { order: "checkin_datetime asc", limit: 8 }
            );
            queueByDoctor.push({
                doctorName: group.doctor_id ? group.doctor_id[1] : "Unassigned",
                doctorId: group.doctor_id ? group.doctor_id[0] : false,
                count: group.__count,
                visits,
            });
        }
        this.state.queueByDoctor = queueByDoctor;
    }

    async _loadAppointments() {
        const appointments = await this.orm.searchRead(
            "hospital.appointment",
            [
                ["scheduled_datetime", ">=", this._todayStart()],
                ["scheduled_datetime", "<=", this._todayEnd()],
            ],
            ["name", "patient_id", "doctor_id", "scheduled_datetime", "state"],
            { order: "scheduled_datetime asc", limit: 20 }
        );
        this.state.appointments = appointments;
    }

    _todayStart() {
        const now = new Date();
        return `${now.toISOString().slice(0, 10)} 00:00:00`;
    }

    _todayEnd() {
        const now = new Date();
        return `${now.toISOString().slice(0, 10)} 23:59:59`;
    }

    onRetry() {
        this.loadDashboard();
    }

    openNewRegistration() {
        this.action.doAction("hospital_reception.hospital_patient_registration_wizard_action");
    }

    openSearchPatients() {
        this.action.doAction("hospital_base.hospital_patient_action");
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

    openAppointment(appointmentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hospital.appointment",
            res_id: appointmentId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    async checkInAppointment(appointmentId) {
        await this.orm.call("hospital.appointment", "action_check_in", [[appointmentId]]);
        await this.loadDashboard();
    }
}

registry.category("actions").add("hospital_reception.reception_dashboard", ReceptionDashboard);
