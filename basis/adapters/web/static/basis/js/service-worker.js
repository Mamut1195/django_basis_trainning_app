/* Never cache authenticated documents, API results, payment pages or user data. */
const CACHE = "basis-shell-__BASIS_SHELL_VERSION__";
const OFFLINE = "/offline/";
const ASSETS = __BASIS_SHELL_ASSETS__;
self.addEventListener("install", (event) =>
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      // Explicitly omit credentials: the offline shell must never contain account HTML/CSRF.
      for (const url of ASSETS) {
        const response = await fetch(url, { credentials: "omit", cache: "reload" });
        if (!response.ok) throw new Error("Offline asset unavailable");
        await cache.put(url, response);
      }
    }),
  ),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys())
        if (key.startsWith("basis-shell-") && key !== CACHE) await caches.delete(key);
      await self.clients.claim();
    })(),
  ),
);
let updating = false;
async function activateSafely() {
  if (updating) return;
  updating = true;
  let windows = [];
  let activated = false;
  try {
    windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const replies = await Promise.all(
      windows.map(
        (client) =>
          new Promise((resolve) => {
            const channel = new MessageChannel();
            const finish = (safe) => {
              clearTimeout(timer);
              channel.port1.close();
              resolve(safe);
            };
            const timer = setTimeout(() => finish(false), 3000);
            channel.port1.onmessage = (reply) => finish(reply.data?.safe === true);
            client.postMessage({ type: "PREPARE_UPDATE" }, [channel.port2]);
          }),
      ),
    );
    const current = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    if (
      replies.every(Boolean) &&
      windows.length > 0 &&
      current.every((client) => windows.some((previous) => previous.id === client.id))
    ) {
      await self.skipWaiting();
      activated = true;
      return;
    }
  } finally {
    // On refusal all windows can keep editing. On success controllerchange reloads them.
    if (!activated) for (const client of windows) client.postMessage({ type: "RELEASE_UPDATE" });
    updating = false;
  }
}
self.addEventListener("message", (event) => {
  if (event.data?.type === "ACTIVATE") event.waitUntil(activateSafely());
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (ASSETS.includes(url.pathname))
    event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
