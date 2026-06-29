/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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
        onWillStart(() => this.loadDashboard());
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
