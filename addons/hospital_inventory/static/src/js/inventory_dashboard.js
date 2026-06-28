/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Inventory Dashboard (Phase 8 §13): KPI cards ("Low Stock", "Expiring
 * Soon") plus the stock-level/expiry-alert/low-stock-alert lists, all
 * read from the hospital.inventory.dashboard SQL view (no Python
 * aggregation here -- the view already did it, per Phase 5 §10).
 * "Adjust stock" and "Trigger purchase" intentionally just open Odoo's
 * native Inventory/Purchase actions rather than reinventing them.
 */
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
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const rows = await this.orm.searchRead(
                "hospital.inventory.dashboard",
                [],
                [
                    "product_id",
                    "qty_available",
                    "reorder_threshold",
                    "is_low_stock",
                    "nearest_expiry_date",
                    "is_expiring_soon",
                    "is_expired",
                ],
                { order: "is_low_stock desc, is_expiring_soon desc", limit: 200 }
            );
            this.state.rows = rows;
            this.state.lowStockCount = rows.filter((r) => r.is_low_stock).length;
            this.state.expiringSoonCount = rows.filter(
                (r) => r.is_expiring_soon || r.is_expired
            ).length;
        } catch (error) {
            this.state.error = true;
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    onRetry() {
        this.loadDashboard();
    }

    openMedicine(productId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openAdjustStock() {
        await this.action.doAction("stock.action_view_inventory_tree");
    }

    async openLowStockAlerts() {
        await this.action.doAction("hospital_inventory.hospital_inventory_dashboard_action_low_stock");
    }

    async openExpiryAlerts() {
        await this.action.doAction("hospital_inventory.hospital_medicine_batch_action_expiring");
    }
}

registry.category("actions").add("hospital_inventory.inventory_dashboard", InventoryDashboard);
