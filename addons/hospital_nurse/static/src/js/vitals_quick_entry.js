/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Vitals Quick-Entry (Phase 8 §7): tablet-optimized structured vitals
 * capture -- numeric steppers rather than bare text inputs, an
 * auto-computed/color-flagged BMI as values change, and a single
 * "Save & Send to Doctor" action. All business logic (range validation,
 * abnormal-vitals escalation, the waiting_nurse -> waiting_doctor
 * transition) lives in `hospital.vitals.create()` (Phase 11 §1) -- this
 * component only collects the fields and calls `create`.
 *
 * Opened as a dialog (target "new") from the Nurse Dashboard or the visit
 * form's "Record Vitals" button, with `default_visit_id` in the action
 * context (see hospital_nurse_dashboard_views.xml / nurse_dashboard.js).
 */
export class VitalsQuickEntry extends Component {
    static template = "hospital_nurse.VitalsQuickEntry";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        const context = this.props.action?.context || {};
        this.visitId = context.default_visit_id || false;
        this.state = useState({
            saving: false,
            error: false,
            values: {
                blood_pressure_systolic: 120,
                blood_pressure_diastolic: 80,
                pulse_rate: 72,
                temperature: 36.8,
                spo2: 98,
                respiratory_rate: 16,
                height_cm: 170,
                weight_kg: 70,
                notes: "",
            },
        });
    }

    get bmi() {
        const { height_cm, weight_kg } = this.state.values;
        if (!height_cm || !weight_kg) {
            return 0;
        }
        const heightM = height_cm / 100;
        return weight_kg / (heightM * heightM);
    }

    get bmiStatus() {
        const bmi = this.bmi;
        if (!bmi) {
            return { label: "-", cssClass: "" };
        }
        if (bmi < 18.5) {
            return { label: "Underweight", cssClass: "o_hospital_bmi_warning" };
        }
        if (bmi < 25) {
            return { label: "Normal", cssClass: "o_hospital_bmi_success" };
        }
        if (bmi < 30) {
            return { label: "Overweight", cssClass: "o_hospital_bmi_warning" };
        }
        return { label: "Obese", cssClass: "o_hospital_bmi_danger" };
    }

    isAbnormal(field) {
        const v = this.state.values[field];
        if (!v) {
            return false;
        }
        switch (field) {
            case "blood_pressure_systolic":
                return v > 180 || v < 90;
            case "temperature":
                return v > 39 || v < 35;
            case "spo2":
                return v < 92;
            case "pulse_rate":
                return v > 120 || v < 50;
            default:
                return false;
        }
    }

    step(field, delta) {
        const current = this.state.values[field] || 0;
        const next = Math.round((current + delta) * 10) / 10;
        this.state.values[field] = Math.max(0, next);
    }

    onFieldInput(field, ev) {
        const parsed = parseFloat(ev.target.value);
        this.state.values[field] = Number.isFinite(parsed) ? parsed : 0;
    }

    onNotesInput(ev) {
        this.state.values.notes = ev.target.value;
    }

    async onSaveAndSendToDoctor() {
        this.state.saving = true;
        this.state.error = false;
        try {
            await this.orm.create("hospital.vitals", [
                { visit_id: this.visitId, ...this.state.values },
            ]);
            this.action.doAction({ type: "ir.actions.act_window_close" });
        } catch (error) {
            this.state.error = error.data ? error.data.message : error.message;
        } finally {
            this.state.saving = false;
        }
    }

    onCancel() {
        this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("hospital_nurse.vitals_quick_entry", VitalsQuickEntry);
