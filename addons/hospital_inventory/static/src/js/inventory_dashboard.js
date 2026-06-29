/** @odoo-module **/

import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function animateCount(el, target, duration = 650) {
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

export class InventoryDashboard extends Component {
    static template = "hospital_inventory.InventoryDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            rows: [],
            lowStockCount: 0,
            expiringSoonCount: 0,
        });
        onWillStart(() => this.loadDashboard());
        onMounted(() => { if (!this.state.loading) this._animateKpis(); });
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const rows = await this.orm.searchRead(
                "hospital.inventory.dashboard", [],
                ["product_id","qty_available","reorder_threshold","is_low_stock",
                 "nearest_expiry_date","is_expiring_soon","is_expired"],
                { order: "is_low_stock desc, is_expiring_soon desc", limit: 200 }
            );
            this.state.rows = rows;
            this.state.lowStockCount     = rows.filter((r) => r.is_low_stock).length;
            this.state.expiringSoonCount = rows.filter((r) => r.is_expiring_soon || r.is_expired).length;
        } catch {
            this.state.error = true;
        } finally {
            this.state.loading = false;
            Promise.resolve().then(() => this._animateKpis());
        }
    }

    _animateKpis() {
        const sel = (attr) => this.el && this.el.querySelector(`[data-kpi="${attr}"]`);
        animateCount(sel("low_stock"),      this.state.lowStockCount,     700);
        animateCount(sel("expiring_soon"),  this.state.expiringSoonCount, 750);
    }

    onRetry() { this.loadDashboard(); }

    openMedicine(productId) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "product.product",
            res_id: productId, view_mode: "form", views: [[false,"form"]], target: "current",
        });
    }

    async openAdjustStock()    { await this.action.doAction("stock.action_view_inventory_tree"); }
    async openLowStockAlerts() { await this.action.doAction("hospital_inventory.hospital_inventory_dashboard_action_low_stock"); }
    async openExpiryAlerts()   { await this.action.doAction("hospital_inventory.hospital_medicine_batch_action_expiring"); }
}

registry.category("actions").add("hospital_inventory.inventory_dashboard", InventoryDashboard);
