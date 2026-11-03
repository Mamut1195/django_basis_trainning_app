/* The status lives outside the HTMX swap so it survives failed polls. */
(() => {
  "use strict";
  const container = document.querySelector("#coach-job");
  const status = document.querySelector("#coach-job-update-status");
  if (!container || !status) return;

  const isJobPoll = (event) => event.target?.id === "job-result";
  const failed = (event) => {
    if (!isJobPoll(event)) return;
    status.className = "notice";
    status.textContent =
      "No se pudo actualizar el resultado. Conservamos el último estado; volveremos a intentarlo.";
    // app.js handles responseError globally. This poll has its own message.
    if (event.type === "htmx:responseError") event.stopPropagation();
  };
  ["htmx:sendError", "htmx:timeout", "htmx:responseError"].forEach((name) =>
    container.addEventListener(name, failed),
  );
  container.addEventListener("htmx:afterSwap", (event) => {
    if (isJobPoll(event)) {
      status.textContent = "";
      status.className = "";
    }
  });
})();
