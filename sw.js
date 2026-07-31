/* Hamid Signal Agent — service worker
   Caches the app shell so the panel opens instantly (even offline),
   while always going to the network for live market data and the cloud API. */
const CACHE = "hsa-shell-v16.1";
const ASSETS = [
  "./",
  "./index.html",
  "./lightweight-charts.js",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png"
];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS).catch(() => {})));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }

  // Only ever touch this app's own files. Anything cross-origin — market data,
  // sentiment sources, the cloud API — goes straight to the network: answering
  // those from cache handed callers the app shell instead of their data.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) return;
  // The relayed scan is rewritten every few minutes. Serving it cache-first
  // would pin the panel to whichever scan it saw first — the one thing this
  // file must never do is go stale.
  if (url.pathname.includes("/signals/")) return;

  // App shell: cache-first, then network. Only a navigation may fall back to
  // the cached page; a failed asset must fail, not silently become HTML.
  e.respondWith(
    caches.match(req).then((hit) =>
      hit ||
      fetch(req)
        .then((resp) => {
          if (resp && resp.ok && resp.type === "basic") {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          }
          return resp;
        })
        .catch(() => (req.mode === "navigate" ? caches.match("./index.html") : Response.error()))
    )
  );
});
