{% load static %}
/* Never cache authenticated documents, API results, payment pages or user data. */
const CACHE = 'basis-shell-{{ shell_version }}';
const OFFLINE = '/offline/';
const ASSETS = [OFFLINE,
  '{% static "css/tokens.css" %}', '{% static "css/app.css" %}',
  '{% static "js/theme.js" %}', '{% static "js/app.js" %}', '{% static "js/offline.js" %}',
  '{% static "vendor/htmx.min.js" %}', '{% static "vendor/alpine.min.js" %}',
  '{% static "vendor/alpine-focus.min.js" %}', '{% static "vendor/alpine-collapse.min.js" %}',
  '{% static "django_cotton_ui/cotton-ui.css" %}', '{% static "django_cotton_ui/cotton-ui.min.js" %}',
  '{% static "icons/icon-192.png" %}', '{% static "icons/icon-512.png" %}', '{% static "icons/icon.svg" %}'
];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(async cache => {
  // Explicitly omit credentials: the offline shell must never contain account HTML/CSRF.
  for (const url of ASSETS) {
    const response = await fetch(url, {credentials:'omit', cache:'reload'});
    if (!response.ok) throw new Error('Offline asset unavailable');
    await cache.put(url, response);
  }
})));
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const key of await caches.keys()) if (key.startsWith('basis-shell-') && key !== CACHE) await caches.delete(key);
  await self.clients.claim();
})()));
self.addEventListener('message', event => { if (event.data?.type === 'ACTIVATE') self.skipWaiting(); });
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE))); return;
  }
  if (ASSETS.includes(url.pathname)) event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
