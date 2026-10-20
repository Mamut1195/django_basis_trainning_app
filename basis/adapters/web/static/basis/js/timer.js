/* Persistent rest timer; independent of form and offline synchronization state. */
(() => {
  "use strict";
  document.addEventListener("click", (event) => {
    const timer = event.target.closest("[data-timer]");
    if (timer) {
      const seconds = Number(timer.dataset.timer);
      try {
        localStorage.setItem("basis-timer", String(seconds ? Date.now() + seconds * 1000 : 0));
      } catch (_) {
        window.basisStatus?.("El temporizador necesita almacenamiento local disponible.");
      }
      tick();
    }
  });
  function tick() {
    let end = 0;
    try {
      end = Number(localStorage.getItem("basis-timer"));
    } catch (_) {
      /* Optional timer. */
    }
    const remaining = Math.max(0, Math.ceil((end - Date.now()) / 1000));
    document.querySelectorAll("[data-timer-output]").forEach((output) => {
      output.textContent = `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;
    });
  }
  setInterval(tick, 1000);
  tick();
})();
