'use strict';
/**
 * sw.js — Mobile Portal Service Worker
 * - App-shell caching (offline support)
 * - Push Notifications
 * - Background Sync (pending orders when offline)
 */

const CACHE_SHELL  = 'mp-shell-v1';
const CACHE_STATIC = 'mp-static-v2';
const IDB_NAME     = 'mobile-portal';
const IDB_VER      = 1;
const IDB_STORE    = 'pending-orders';

// ─── Install: cache app shell ─────────────────────────────────────────────────
self.addEventListener('install', ev => {
    ev.waitUntil(
        caches.open(CACHE_SHELL)
            .then(c => c.addAll(['/my/shop']))
            .then(() => self.skipWaiting())
            .catch(err => console.warn('[SW] install error:', err))
    );
});

// ─── Activate: remove old caches ──────────────────────────────────────────────
self.addEventListener('activate', ev => {
    const keep = [CACHE_SHELL, CACHE_STATIC];
    ev.waitUntil(
        caches.keys()
            .then(keys => Promise.all(
                keys.filter(k => !keep.includes(k)).map(k => caches.delete(k))
            ))
            .then(() => self.clients.claim())
    );
});

// ─── Fetch: cache strategies ──────────────────────────────────────────────────
self.addEventListener('fetch', ev => {
    const req = ev.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    // API calls → pass-through (never cache)
    if (url.pathname.startsWith('/my/shop/api/') ||
        url.pathname === '/my/shop/sw.js') return;

    // Portal templates XML → luôn lấy bản mới nhất từ server, KHÔNG cache.
    // Đây là mã nguồn giao diện (OWL templates) được app.js fetch trực tiếp
    // (ngoài luồng bundle web.assets_frontend) — nếu Cache First như các static
    // asset khác thì thay đổi UI mới sẽ không bao giờ tới được trình duyệt
    // dù đã bump version/restart server, chỉ hết khi người dùng tự xoá cache.
    if (url.pathname.endsWith('/portal_templates.xml')) return;

    // Static assets → Cache First
    if (url.pathname.startsWith('/mobile_portal/static/') ||
        url.pathname.startsWith('/web/static/')) {
        ev.respondWith(
            caches.match(req, { cacheName: CACHE_STATIC }).then(hit => {
                if (hit) return hit;
                return fetch(req).then(resp => {
                    if (resp.ok) {
                        const clone = resp.clone();
                        caches.open(CACHE_STATIC).then(c => c.put(req, clone));
                    }
                    return resp;
                });
            })
        );
        return;
    }

    // App shell → Network First, fallback to cache
    if (url.pathname.startsWith('/my/shop')) {
        ev.respondWith(
            fetch(req)
                .then(resp => {
                    if (resp.ok) {
                        const clone = resp.clone();
                        caches.open(CACHE_SHELL).then(c => c.put(req, clone));
                    }
                    return resp;
                })
                .catch(() => caches.match('/my/shop', { cacheName: CACHE_SHELL }))
        );
    }
});

// ─── Push Notification ────────────────────────────────────────────────────────
self.addEventListener('push', ev => {
    let data = { title: 'Cổng Khách Hàng', body: '' };
    if (ev.data) {
        try   { Object.assign(data, ev.data.json()); }
        catch { data.body = ev.data.text(); }
    }

    ev.waitUntil(
        self.registration.showNotification(data.title, {
            body:     data.body,
            icon:     '/my/shop/icon/192',
            badge:    '/my/shop/icon/96',
            tag:      data.tag || 'mp-notif',
            renotify: true,
            vibrate:  [100, 50, 100],
            data:     { url: data.url || '/my/shop' },
            actions:  data.actions || [],
        })
    );
});

self.addEventListener('notificationclick', ev => {
    ev.notification.close();
    const targetUrl = ev.notification.data?.url || '/my/shop';

    ev.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(list => {
                for (const c of list) {
                    if (c.url.startsWith(self.location.origin + '/my/') && 'focus' in c)
                        return c.navigate(targetUrl).then(wc => wc.focus());
                }
                return clients.openWindow(targetUrl);
            })
    );
});

// ─── Background Sync ──────────────────────────────────────────────────────────
self.addEventListener('sync', ev => {
    if (ev.tag === 'sync-orders') {
        ev.waitUntil(flushPendingOrders());
    }
});

// IndexedDB helpers (service worker context)
function openDB() {
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

function getAllPending(db) {
    return new Promise((resolve, reject) => {
        const items = [];
        const tx  = db.transaction(IDB_STORE, 'readonly');
        const req = tx.objectStore(IDB_STORE).openCursor();
        req.onsuccess = e => {
            const c = e.target.result;
            if (c) { items.push({ key: c.key, value: c.value }); c.continue(); }
            else   resolve(items);
        };
        req.onerror = e => reject(e.target.error);
    });
}

function deletePending(db, key) {
    return new Promise((resolve, reject) => {
        const req = db.transaction(IDB_STORE, 'readwrite').objectStore(IDB_STORE).delete(key);
        req.onsuccess = () => resolve();
        req.onerror   = e => reject(e.target.error);
    });
}

async function flushPendingOrders() {
    let db;
    try { db = await openDB(); } catch { return; }

    const items = await getAllPending(db);
    for (const { key, value } of items) {
        try {
            const resp = await fetch('/my/shop/api/place_order', {
                method:  'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type':     'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0', method: 'call', id: Date.now(),
                    params: { cart_items: value.cart_items },
                }),
            });

            if (!resp.ok) continue;
            const json = await resp.json();
            if (json.error) continue;

            await deletePending(db, key);

            // Notify open app tabs
            const allClients = await clients.matchAll({ type: 'window' });
            allClients.forEach(c => c.postMessage({
                type:      'ORDER_SYNCED',
                order_ref: json.result?.order_ref || '',
            }));
        } catch {
            // Still offline — will retry on next sync event
        }
    }
}
