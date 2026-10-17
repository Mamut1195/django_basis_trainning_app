/* Progressive enhancement; all normal forms remain usable without JavaScript. */
(() => {
  'use strict';
  function status(text) {
    const node = document.querySelector('#global-status');
    if (node) { node.hidden = false; node.className = 'notice'; node.textContent = text; }
  }
  window.basisStatus = status;
  function network() {
    document.querySelectorAll('[data-network]').forEach(node => {
      node.textContent = navigator.onLine ? 'En línea' : 'Sin conexión';
      node.dataset.offline = String(!navigator.onLine);
    });
  }
  addEventListener('online', network); addEventListener('offline', network); network();
  document.addEventListener('htmx:configRequest', event => {
    event.detail.headers['X-CSRFToken'] = document.querySelector('meta[name=csrf-token]')?.content || '';
  });
  document.addEventListener('htmx:responseError', () => status('No se pudo completar la solicitud. Tus datos locales siguen guardados.'));
  document.addEventListener('click', event => {
    const theme = event.target.closest('[data-theme-toggle]');
    if (theme) {
      document.documentElement.classList.toggle('dark');
      try { localStorage.setItem('basis-theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light'); } catch (_) { /* Optional preference. */ }
    }
    const back = event.target.closest('[data-back]');
    if (back) { event.preventDefault(); history.back(); }
    const timer = event.target.closest('[data-timer]');
    if (timer) {
      const seconds = Number(timer.dataset.timer);
      try { localStorage.setItem('basis-timer', String(seconds ? Date.now() + seconds * 1000 : 0)); } catch (_) { status('El temporizador necesita almacenamiento local disponible.'); }
      tick();
    }
  });
  function tick() {
    let end = 0;
    try { end = Number(localStorage.getItem('basis-timer')); } catch (_) { /* Optional timer. */ }
    const remaining = Math.max(0, Math.ceil((end - Date.now()) / 1000));
    document.querySelectorAll('[data-timer-output]').forEach(output => { output.textContent = `${String(Math.floor(remaining / 60)).padStart(2,'0')}:${String(remaining % 60).padStart(2,'0')}`; });
  }
  setInterval(tick, 1000); tick();
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!form.matches('[data-form-submit]') || !navigator.onLine) return;
    const label = form.querySelector('[data-submit-status]');
    if (label) label.textContent = 'Guardando…';
  });
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js').then(registration => {
      let updateRequested = false;
      function ready() {
        const button = document.querySelector('[data-apply-update]');
        if (button && registration.waiting) button.hidden = false;
      }
      ready();
      registration.addEventListener('updatefound', () => registration.installing?.addEventListener('statechange', ready));
      document.addEventListener('click', async event => {
        if (!event.target.closest('[data-apply-update]')) return;
        if (window.basisPending && await window.basisPending()) {
          status('Sincroniza o exporta tus registros pendientes antes de actualizar.'); return;
        }
        updateRequested = true;
        registration.waiting?.postMessage({type:'ACTIVATE'});
      });
      navigator.serviceWorker.addEventListener('controllerchange', () => { if (updateRequested) location.reload(); });
    }).catch(() => status('No se pudo preparar el modo sin conexión. Puedes seguir usando la app en línea.'));
  }
})();
