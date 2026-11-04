// Isolate this terminal from the classic panel's cache-first root worker.
// Mutable snapshots and application assets always reach the network. Archive
// pages have content-derived names and may use the browser's HTTP cache.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (/\/data\/history\/[a-f0-9]{16}\.json$/.test(url.pathname)) return;
  event.respondWith(fetch(request, {cache: 'no-store'}));
});
