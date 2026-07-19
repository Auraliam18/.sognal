/* Hamid Signal Agent — service worker
   Caches the app shell so the panel opens instantly (even offline),
   while always going to the network for live market data and the cloud API. */
const CACHE = "hsa-shell-v4";
const ASSETS = [
  "./",
  "./index.html",
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

  // Never cache live market data or the cloud-sync API — always network.
  if (
    url.hostname.includes("binance") ||
    url.hostname.includes("upstash") ||
    url.pathname.includes("/api/")
  ) {
    return; // let the browser handle it (network)
  }

  // App shell: cache-first, fall back to network, then to cached index.
  e.respondWith(
    caches.match(req).then((hit) =>
      hit ||
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          return resp;
        })
        .catch(() => caches.match("./index.html"))
    )
  );
});
