/*
 * Angel Claw service worker.
 *
 * Served from the site root (/sw.js) so its scope covers the whole app.
 *
 * Strategy:
 *  - Navigations: network first, cached copy as offline fallback.
 *  - Static assets (own /static + CDN libs): stale-while-revalidate.
 *  - Everything else (chat streams, API calls, non-GET): not intercepted.
 */
const CACHE_NAME = 'angel-claw-v4';

const SHELL_ASSETS = [
  '/static/wing.png',
  '/static/pwa/icon-192.png',
  '/static/pwa/icon-512.png',
  '/static/pwa/icon-maskable-512.png',
  '/static/pwa/offline.html',
  '/static/js/tailwind.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',
  'https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

function isStaticRequest(request, url) {
  return url.origin === self.location.origin
    ? url.pathname.startsWith('/static/')
    : true; // cross-origin: CDN libraries only
}

self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only cacheable GETs. Never touch chat streaming, API or webhook traffic.
  if (request.method !== 'GET' || request.headers.has('range')) return;

  const url = new URL(request.url);
  if (['/chat', '/api', '/mobile', '/webhook'].some((p) => url.pathname === p || url.pathname.startsWith(p + '/'))) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match('/static/pwa/offline.html'))
        )
    );
    return;
  }

  if (isStaticRequest(request, url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((response) => {
            if (response && (response.ok || response.type === 'opaque')) {
              const copy = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            }
            return response;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});
