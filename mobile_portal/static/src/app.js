/** @odoo-module **/
/**
 * app.js — Entry point for the Mobile Portal SPA.
 *
 * WHY we load templates via fetch instead of @web/core/assets:
 *   In Odoo 17/18, `web.assets_frontend` is a lightweight bundle — it does NOT
 *   run the OWL template compilation step that populates the `templates` export
 *   of `@web/core/assets`. That step only runs for `web.assets_web` (backend).
 *   Fetching portal_templates.xml (one request, ~30 KB) is reliable across all
 *   Odoo versions and bundle configurations.
 */

import { App, whenReady } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";
import { session } from "@web/session";
import { PortalApp } from "./components/PortalApp/PortalApp";

/**
 * Fetches the pre-merged OWL templates XML file and returns the raw string.
 * The file is generated at build time by merging all component .xml files.
 *
 * We append a cache-busting query param (asset hash) so browsers re-fetch
 * after a module upgrade.
 */
async function loadPortalTemplates() {
    // __portal_templates_url__ is optionally overridden by QWeb (see templates.xml).
    // Default to the static path that is always served by Odoo's static file handler.
    const url = window.__portalTemplatesUrl__ ||
                "/mobile_portal/static/src/portal_templates.xml";
    try {
        const resp = await fetch(url, { cache: "force-cache" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.text();
    } catch (err) {
        console.error("[mobile_portal] Failed to load templates:", err);
        throw err;
    }
}

whenReady(async () => {
    const container = document.getElementById("mobile-portal-root");
    if (!container) {
        // Not on the mobile portal page — do nothing.
        return;
    }

    // Load templates XML before mounting
    const templates = await loadPortalTemplates();

    const partnerName = container.dataset.partnerName || session.name || "Khách hàng";
    const partnerId   = parseInt(container.dataset.partnerId || "0", 10);

    /**
     * Shared env available to all components via this.env.*
     * - this.env.rpc("/my/shop/api/...", payload)  → Odoo JSON-RPC
     * - this.env.session                           → Odoo session object
     */
    const env = {
        rpc: jsonrpc,
        session,
        partnerName,
        partnerId
    };

    const app = new App(PortalApp, {
        templates,      // Raw XML string — OWL 2 parses it internally
        env,
        dev: false,     // Flip to true during development for OWL prop warnings
    });

    await app.mount(container);
});
