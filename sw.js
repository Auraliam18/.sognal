/* Hamid Signal Agent — service worker
   Caches the app shell so the panel opens instantly (even offline),
   while always going to the network for live market data and the cloud API. */
const CACHE = "hsa-shell-v21.25";
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

  const save = (resp) => {
    if (resp && resp.ok && resp.type === "basic") {
      const copy = resp.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
    }
    return resp;
  };

  // The page itself: network first, cache only as a fallback.
  //
  // Cache-first was wrong here and it showed. A new deploy did not appear on the
  // next visit — the old page came out of the cache while the new worker was
  // still installing, and only the visit after that got the update. Measured:
  // deploy, reload, still the old version; reload again, new version. Anyone
  // opening the panel to check a change saw the change missing.
  //
  // Network-first costs one request the cache could have answered, and buys the
  // guarantee that what is on screen is what was deployed. The cached copy still
  // answers when the network does not, so it still opens offline.
  if (req.mode === "navigate" || (req.destination === "document")) {
    // no-store: fetch(req) خالی از کش HTTP مرورگر می‌خواند و GitHub Pages تا
    // ۱۰ دقیقه max-age می‌دهد — یعنی رفرشِ بعد از دیپلوی، صفحهٔ قدیمی را
    // می‌آورد و «تغییر نام پنل» دیده نمی‌شد. مستقیم از شبکه، همیشه.
    e.respondWith(
      fetch(req, { cache: "no-store" })
        .then(save)
        .catch(() => caches.match(req).then((hit) => hit || caches.match("./index.html")))
    );
    return;
  }

  // Everything else — the chart library, icons, the manifest — is versioned by
  // the cache name and changes only on a deploy, so cache-first is right for it.
  // A failed asset must fail rather than silently become HTML.
  e.respondWith(
    caches.match(req).then((hit) =>
      hit || fetch(req).then(save).catch(() => Response.error())
    )
  );
});
