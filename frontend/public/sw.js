/* Kain Nusantara — service worker HP gudang.
   App shell: cache-first (build hash di nama berkas → aman). Data tugas/roll: network-first,
   fallback cache terakhir saat offline (respons ditandai header X-From-Cache). Aksi tulis TIDAK
   pernah di-cache — antre lewat offlineQueue di aplikasi. */
const VERSION = "kn-sw-v3";
const SHELL = `${VERSION}-shell`;
const DATA = `${VERSION}-data`;
const DATA_PATHS = ["/api/wms/tasks", "/api/rfid/untagged-rolls", "/api/rfid/printer-status", "/api/auth/me", "/api/entities", "/api/home/", "/api/dashboard", "/api/products", "/api/customers", "/api/hr/visits/me", "/api/payment-terms",
  // HP sales / Admin Sales — baca terakhir saat offline
  "/api/sales-orders", "/api/sales-admin/desk", "/api/special-orders", "/api/sales-returns", "/api/internal-requests", "/api/price-approvals", "/api/crm/leads"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/index.html"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

const isData = (url) => DATA_PATHS.some((p) => url.pathname.startsWith(p));

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    if (!isData(url)) return;
    e.respondWith((async () => {
      const cache = await caches.open(DATA);
      try {
        const res = await fetch(req);
        if (res.ok) cache.put(req, res.clone());
        return res;
      } catch (_) {
        const hit = await cache.match(req);
        if (hit) {
          const h = new Headers(hit.headers); h.set("X-From-Cache", "true");
          return new Response(await hit.blob(), { status: 200, headers: h });
        }
        return new Response(JSON.stringify({ detail: { code: "OFFLINE", message: "Offline dan belum ada data tersimpan." } }), { status: 503, headers: { "Content-Type": "application/json" } });
      }
    })());
    return;
  }
  // Navigasi / index.html: network-first (bundle baru langsung terpakai setelah rebuild);
  // aset ber-hash di /static: cache-first (aman karena nama berkas berubah tiap build).
  e.respondWith((async () => {
    const cache = await caches.open(SHELL);
    const isShell = req.mode === "navigate" || url.pathname === "/" || url.pathname === "/index.html";
    if (isShell) {
      try {
        const res = await fetch(req);
        if (res.ok) cache.put("/index.html", res.clone());
        return res;
      } catch (_) {
        return (await cache.match("/index.html")) || Response.error();
      }
    }
    const hit = await cache.match(req);
    if (hit) return hit;
    const res = await fetch(req);
    if (res.ok && (url.pathname.startsWith("/static/") || /\.(js|css|png|svg|woff2?)$/.test(url.pathname))) cache.put(req, res.clone());
    return res;
  })());
});


/* Web Push (PWA) — notifikasi lonceng tetap sampai walau aplikasi HP ditutup. */
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data ? e.data.text() : "" }; }
  const title = d.title || "Kain Nusantara";
  e.waitUntil((async () => {
    await self.registration.showNotification(title, {
      body: d.body || "",
      icon: "/icon-192.png",
      badge: "/favicon.png",
      tag: d.tag || undefined,
      renotify: !!d.tag,
      requireInteraction: d.severity === "critical",
      data: { link: d.link || "", notification_id: d.notification_id || "" },
    });
    // Beri tahu tab yang terbuka supaya lencana lonceng langsung diperbarui.
    const tabs = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    tabs.forEach((c) => c.postMessage({ type: "kn-push", payload: d }));
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const nid = (e.notification.data || {}).notification_id || "";
  const target = `/?source=push${nid ? `&notif=${encodeURIComponent(nid)}` : ""}`;
  e.waitUntil((async () => {
    const tabs = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const tab = tabs.find((c) => new URL(c.url).origin === self.location.origin);
    if (tab) { await tab.focus(); tab.postMessage({ type: "kn-push-open", notification_id: nid }); return; }
    await self.clients.openWindow(target);
  })());
});
