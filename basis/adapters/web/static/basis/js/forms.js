/* Native form enhancement; validation and server-rendered errors work without JS. */
(() => {
  "use strict";
  const reset = (form) => {
    form.removeAttribute("aria-busy");
    form.querySelectorAll("[data-submit-locked]").forEach((button) => {
      button.disabled = false;
      delete button.dataset.submitLocked;
    });
    const label = form.querySelector("[data-submit-status]");
    if (label) label.textContent = "";
  };
  addEventListener("pageshow", () =>
    document.querySelectorAll("[data-form-submit]").forEach(reset),
  );
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form.matches("[data-form-submit]")) return;
    if (form.getAttribute("aria-busy") === "true") {
      event.preventDefault();
      return;
    }
    form.setAttribute("aria-busy", "true");
    const label = form.querySelector("[data-submit-status]");
    if (label)
      label.textContent = navigator.onLine ? "Guardando\u2026" : "Esperando conexi\u00f3n\u2026";
    // Delay locking until the browser serializes the clicked submitter's name/value.
    setTimeout(() => {
      if (!event.defaultPrevented)
        form.querySelectorAll("button[type=submit]").forEach((button) => {
          if (!button.disabled) {
            button.dataset.submitLocked = "";
            button.disabled = true;
          }
        });
      else reset(form);
    }, 0);
  });
  document.addEventListener("htmx:afterRequest", (event) => {
    const form = event.target.closest?.("[data-form-submit]");
    if (form) reset(form);
  });
  document.querySelector("[data-error-summary]")?.focus();
})();
