/* Offline shell update lifecycle. */
(() => {
  "use strict";
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((registration) => {
        let updateRequested = false;
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
          if (window.basisPending && (await window.basisPending())) {
            window.basisStatus?.(
              "Sincroniza o exporta tus registros pendientes antes de actualizar.",
            );
            return;
          }
          updateRequested = true;
          registration.waiting?.postMessage({ type: "ACTIVATE" });
        });
        navigator.serviceWorker.addEventListener("controllerchange", () => {
          if (updateRequested) location.reload();
        });
      })
      .catch(() =>
        window.basisStatus?.(
          "No se pudo preparar el modo sin conexión. Puedes seguir usando la app en línea.",
        ),
      );
  }
})();
