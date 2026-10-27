/* Persistent rest timer; independent of form and offline synchronization state. */
(() => {
  "use strict";
  const account = document.body.dataset.account || "anonymous";
  const key = "basis-rest:" + account;
  let memoryEnd = 0;
  document.addEventListener("click", (event) => {
    const timer = event.target.closest("[data-timer]");
    if (timer) {
      const seconds = Number(timer.dataset.timer);
      try {
        memoryEnd = seconds ? Date.now() + seconds * 1000 : 0;
        sessionStorage.setItem(key, String(memoryEnd));
      } catch (_) {
        window.basisStatus?.("El temporizador necesita almacenamiento local disponible.");
      }
      tick();
    }
  });
  function tick() {
    let end = memoryEnd;
    try {
      end = Number(sessionStorage.getItem(key)) || memoryEnd;
    } catch (_) {
      /* Optional timer. */
    }
    const remaining = Math.max(0, Math.ceil((end - Date.now()) / 1000));
    document.querySelectorAll("[data-timer-output]").forEach((output) => {
      output.textContent = `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;
    });
  }
  document.addEventListener("visibilitychange", tick);
  addEventListener("pageshow", tick);
  setInterval(tick, 1000);
  tick();
})();
