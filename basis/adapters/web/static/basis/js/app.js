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
})();
