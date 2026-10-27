/* Installation and coordinated, conservative updates across every open window. */
(() => {
  "use strict";
  let dirty = false;
  document.addEventListener("input", (event) => {
    if (event.target.closest("form")) dirty = true;
  });
  document.addEventListener("change", (event) => {
    if (event.target.closest("form")) dirty = true;
  });
  document.addEventListener("basis:saved", () => (dirty = false));
  let installPrompt;
  addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    document.querySelectorAll("[data-install-app]").forEach((button) => (button.hidden = false));
  });
  document.addEventListener("click", async (event) => {
    if (!event.target.closest("[data-install-app]") || !installPrompt) return;
    await installPrompt.prompt();
    installPrompt = null;
    document.querySelectorAll("[data-install-app]").forEach((button) => (button.hidden = true));
  });
  if ("serviceWorker" in navigator) {
    let frozen = false;
    navigator.serviceWorker.addEventListener("message", async (event) => {
      if (event.data?.type === "RELEASE_UPDATE") {
        frozen = false;
        window.basisUpdateBlocked = false;
        document.body.inert = false;
        window.basisStatus?.("Actualización aplazada: termina y guarda en todas las pantallas.");
      }
      if (event.data?.type !== "PREPARE_UPDATE" || !event.ports[0]) return;
      // Freeze first so input cannot race the asynchronous pending-data check.
      frozen = true;
      window.basisUpdateBlocked = true;
      document.body.inert = true;
      let safe = false;
      try {
        await window.basisOfflineReady;
        safe =
          !dirty &&
          !document.querySelector("#offline-editor:not([hidden])") &&
          !window.basisSyncing?.() &&
          Number(localStorage.getItem("basis-timer")) <= Date.now() &&
          !!window.basisPending &&
          !(await window.basisPending());
      } catch (_) {
        /* Unavailable storage or an unresponsive window blocks activation. */
      }
      event.ports[0].postMessage({ safe });
    });
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (frozen) location.reload();
    });
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((registration) => {
        function ready() {
          const button = document.querySelector("[data-apply-update]");
          if (button && registration.waiting) button.hidden = false;
        }
        ready();
        registration.addEventListener("updatefound", () =>
          registration.installing?.addEventListener("statechange", ready),
        );
        document.addEventListener("click", async (event) => {
          if (!event.target.closest("[data-apply-update]")) return;
          registration.waiting?.postMessage({ type: "ACTIVATE" });
        });
      })
      .catch(() =>
        window.basisStatus?.(
          "No se pudo preparar el modo sin conexión. Puedes seguir usando la app en línea.",
        ),
      );
  }
})();
