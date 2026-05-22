// FundGuldasta Service Worker v2
// Strategy: network-first for all requests, cache-on-success for offline fallback.
// No pre-caching of hashed filenames — those change on every build and can't be
// hardcoded here. The cache populates organically as pages are visited.
const CACHE_NAME = 'fundguldasta-v2';

self.addEventListener('install', event => {
  // Only pre-cache the shell HTML — JS/CSS filenames are hashed and unknown here
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.add('/').catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  // Delete any old cache versions
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = event.request.url;

  // Always bypass for API calls and non-GET requests — these must hit the network
  if (event.request.method !== 'GET') return;
  if (url.includes('/api/')) return;
  if (url.includes('localhost:8000')) return;

  // Network-first: try network, cache the response, fall back to cache if offline
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
