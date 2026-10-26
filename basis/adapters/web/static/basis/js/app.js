/* Progressive enhancement; all normal forms remain usable without JavaScript. */
(() => {
  "use strict";
  function status(text) {
    const node = document.querySelector("#global-status");
    if (node) {
      node.hidden = false;
      node.className = "notice";
      node.textContent = text;
    }
  }
  window.basisStatus = status;
  function network() {
    document.querySelectorAll("[data-network]").forEach((node) => {
      node.textContent = navigator.onLine ? "En línea" : "Sin conexión";
      node.dataset.offline = String(!navigator.onLine);
    });
  }
  addEventListener("online", network);
  addEventListener("offline", network);
  network();
  document.addEventListener("htmx:configRequest", (event) => {
    // Never forward the session's CSRF token to a different origin, even if an
    // extension changes HTMX's default selfRequestsOnly policy.
    let target;
    try {
      target = new URL(event.detail.path, document.baseURI);
    } catch (_) {
      event.preventDefault();
      return;
    }
    if (target.origin !== location.origin) {
      delete event.detail.headers["X-CSRFToken"];
      event.preventDefault();
      return;
    }
    event.detail.headers["X-CSRFToken"] =
      document.querySelector("meta[name=csrf-token]")?.content || "";
  });
  document.addEventListener("htmx:responseError", () =>
    status("No se pudo completar la solicitud. Tus datos locales siguen guardados."),
  );
  document.addEventListener("click", (event) => {
    const theme = event.target.closest("[data-theme-toggle]");
    if (theme) {
      document.documentElement.classList.toggle("dark");
      try {
        localStorage.setItem(
          "basis-theme",
          document.documentElement.classList.contains("dark") ? "dark" : "light",
        );
      } catch (_) {
        /* Optional preference. */
      }
    }
    const back = event.target.closest("[data-back]");
    if (back) {
      event.preventDefault();
      history.back();
    }
  });
  document.addEventListener("DOMContentLoaded", () => {
    if (!document.querySelector("#component-catalog")) return;
    // Compose missing semantics on the actual (teleported) inner panel, not
    // the always-visible root. The kit still owns show, trap, Escape and focus.
    document.querySelectorAll('[x-bind="dialog"]').forEach((dialog) => {
      dialog.setAttribute("role", "dialog");
    });
    // Localize the installed dialog's fixed close label, without copying its
    // primitive or interfering with Alpine's sole ownership of initialization.
    document.querySelectorAll('[x-bind="closeButton"]').forEach((button) => {
      button.setAttribute("aria-label", "Cerrar");
      const label = button.querySelector(".sr-only");
      if (label) label.textContent = "Cerrar";
    });
  });
})();
