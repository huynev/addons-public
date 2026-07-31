/** @odoo-module **/
/**
 * app.js — Mobile Portal SPA entry point.
 * - JSON-RPC via native fetch (Odoo 17 + 18 compatible)
 * - Service Worker registration (caching + background sync)
 * - IndexedDB helpers for offline order queuing
 */

import { App, whenReady } from "@odoo/owl";
import { PortalApp } from "./components/PortalApp/PortalApp";

// ── JSON-RPC via fetch ────────────────────────────────────────────────────────
let _rpcSeq = 1;
async function rpc(url, params = {}) {
    const resp = await fetch(url, {
        method:      'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type':     'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: _rpcSeq++, params }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.error) {
        const msg = data.error.data?.message || data.error.message || 'RPC Error';
        const err = new Error(msg);
        err.data  = data.error;
        throw err;
    }
    return data.result;
}

// ── Template loader ───────────────────────────────────────────────────────────
async function loadPortalTemplates() {
    const url  = window.__portalTemplatesUrl__ || '/mobile_portal/static/src/portal_templates.xml';
    const resp = await fetch(url, { cache: 'no-cache' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.text();
}

// ── IndexedDB helpers (pending orders for background sync) ────────────────────
const IDB_NAME  = 'mobile-portal';
const IDB_VER   = 1;
const IDB_STORE = 'pending-orders';

function _openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(IDB_NAME, IDB_VER);
        req.onupgradeneeded = e => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(IDB_STORE))
                db.createObjectStore(IDB_STORE, { autoIncrement: true });
        };
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

async function savePendingOrder(cartItems) {
    const db = await _openDB();
    return new Promise((resolve, reject) => {
        const req = db.transaction(IDB_STORE, 'readwrite')
                      .objectStore(IDB_STORE)
                      .add({ cart_items: cartItems, ts: Date.now() });
        req.onsuccess = () => resolve(req.result);
        req.onerror   = e => reject(e.target.error);
    });
}

async function getPendingOrderCount() {
    const db = await _openDB();
    return new Promise(resolve => {
        const req = db.transaction(IDB_STORE, 'readonly').objectStore(IDB_STORE).count();
        req.onsuccess = () => resolve(req.result);
        req.onerror   = () => resolve(0);
    });
}

async function getAllPendingOrders() {
    const db    = await _openDB();
    const items = [];
    return new Promise((resolve, reject) => {
        const req = db.transaction(IDB_STORE, 'readonly').objectStore(IDB_STORE).openCursor();
        req.onsuccess = e => {
            const c = e.target.result;
            if (c) { items.push({ key: c.key, value: c.value }); c.continue(); }
            else   resolve(items);
        };
        req.onerror = e => reject(e.target.error);
    });
}

async function deletePendingOrder(key) {
    const db = await _openDB();
    return new Promise((resolve, reject) => {
        const req = db.transaction(IDB_STORE, 'readwrite').objectStore(IDB_STORE).delete(key);
        req.onsuccess = () => resolve();
        req.onerror   = e => reject(e.target.error);
    });
}

// ── Service Worker registration ────────────────────────────────────────────────
function registerSW() {
    if (!('serviceWorker' in navigator)) return Promise.resolve(null);
    return navigator.serviceWorker
        .register('/my/shop/sw.js', { scope: '/my/shop/', updateViaCache: 'none' })
        .then(reg => {
            navigator.serviceWorker.addEventListener('message', e => {
                window.dispatchEvent(new CustomEvent('sw-message', { detail: e.data }));
            });
            return reg;
        })
        .catch(err => {
            console.warn('[SW] Registration failed:', err);
            return null;
        });
}

// ── Boot ──────────────────────────────────────────────────────────────────────
whenReady(async () => {
    const container = document.getElementById('mobile-portal-root');
    if (!container) return;

    const templates   = await loadPortalTemplates();
    const partnerName = container.dataset.partnerName || '';
    const partnerId   = parseInt(container.dataset.partnerId || '0', 10);

    const swRegPromise = registerSW();

    const env = {
        rpc,
        partnerName,
        partnerId,
        swRegPromise,
        savePendingOrder,
        getPendingOrderCount,
        getAllPendingOrders,
        deletePendingOrder,
    };

    const app = new App(PortalApp, { templates, env, dev: false });
    await app.mount(container);
});
