/* Server-confirmed quick entry. Offline delivery remains the sync module's job. */
(() => {
  "use strict";
  const root = document.querySelector("#session-player");
  if (!root) return;
  const status = root.querySelector("[data-player-status]");
  const forms = [...root.querySelectorAll("[data-quick-set]")];
  const fields = ["actual_reps", "actual_kg", "actual_rpe", "actual_rir"];
  const states = new Map();
  let serial = Promise.resolve();
  let blocked = false;
  const values = (form) =>
    Object.fromEntries(fields.map((name) => [name, form.elements[name].value]));
  const equal = (a, b) => fields.every((name) => a[name] === b[name]);
  const announce = (form, text) => {
    form.querySelector("[data-row-status]").textContent = text;
    status.textContent = text;
  };
  const setRevision = (revision) => {
    root.dataset.revision = revision;
    document.querySelectorAll("[data-player-revision]").forEach((input) => {
      input.value = revision;
    });
  };
  const key = (form) => `basis-player:${document.body.dataset.account}:${form.action}`;
  const remember = (form) => {
    try {
      sessionStorage.setItem(key(form), JSON.stringify(values(form)));
    } catch (_) {
      announce(form, "Sin guardar. Almacenamiento de pestaña no disponible; no recargues.");
    }
  };
  const forget = (form) => {
    try {
      sessionStorage.removeItem(key(form));
    } catch (_) {
      /* Optional recovery. */
    }
  };
  async function save(form, undo = false) {
    const state = states.get(form);
    if (blocked) {
      announce(form, "Envío bloqueado. Recarga para revisar el servidor y recuperar el borrador.");
      return;
    }
    if (!form.reportValidity()) {
      announce(form, "Corrige los campos; estos cambios no están guardados.");
      return;
    }
    const sent = values(form);
    if (equal(sent, state.saved)) {
      state.dirty = false;
      forget(form);
      return;
    }
    const before = state.saved;
    const data = new FormData(form);
    data.set("revision", root.dataset.revision);
    state.saving = true;
    announce(form, "Guardando… Aún sin confirmación del servidor.");
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: data,
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.headers.get("Content-Type")?.includes("application/json")) {
        blocked = true;
        throw Error("La sesión de acceso cambió o la respuesta es ambigua.");
      }
      let result;
      try {
        result = await response.json();
      } catch (error) {
        blocked = true;
        throw error;
      }
      if (!response.ok) {
        if (response.status !== 400) blocked = true;
        throw Error(
          result.error ||
            Object.values(result.errors || {})
              .flat()
              .map((e) => e.message)
              .join(" ") ||
            "No se pudo guardar.",
        );
      }
      setRevision(result.revision);
      state.saved = result.values;
      state.undo = undo ? null : before;
      state.dirty = !equal(values(form), sent);
      if (!state.dirty) {
        fields.forEach((name) => {
          form.elements[name].value = result.values[name];
        });
        forget(form);
      }
      form.querySelector("[data-player-undo]").disabled = !state.undo;
      announce(
        form,
        state.dirty
          ? "Guardado confirmado. Hay nuevos cambios pendientes."
          : "Guardado confirmado por el servidor.",
      );
    } catch (error) {
      state.dirty = true;
      // A transport failure is ambiguous. Never silently replay a possibly applied write.
      if (error instanceof TypeError || !(error instanceof Error)) blocked = true;
      announce(
        form,
        `Sin confirmar: ${error.message || "Error de red"}. Conserva o recupera el borrador antes de salir.`,
      );
    } finally {
      state.saving = false;
    }
  }
  function enqueue(form, undo = false) {
    serial = serial.then(() => save(form, undo));
    return serial;
  }
  for (const form of forms) {
    const state = { saved: values(form), undo: null, dirty: false, saving: false, timer: null };
    states.set(form, state);
    let draft;
    try {
      draft = JSON.parse(sessionStorage.getItem(key(form)));
    } catch (_) {
      /* Optional recovery. */
    }
    if (
      draft &&
      fields.every((name) => typeof draft[name] === "string") &&
      !equal(draft, state.saved)
    ) {
      state.dirty = true;
      const recover = document.createElement("button");
      recover.type = "button";
      recover.textContent = "Recuperar borrador de esta pestaña (revisar antes de guardar)";
      recover.addEventListener("click", () => {
        fields.forEach((name) => {
          form.elements[name].value = draft[name];
        });
        state.dirty = true;
        announce(
          form,
          "Borrador recuperado sin enviar. Revisa frente al servidor y pulsa Guardar serie.",
        );
        recover.remove();
        discard.remove();
      });
      const discard = document.createElement("button");
      discard.type = "button";
      discard.textContent = "Descartar borrador recuperable";
      discard.addEventListener("click", () => {
        state.dirty = false;
        forget(form);
        recover.remove();
        discard.remove();
        announce(form, "Borrador descartado. Se conserva la versión confirmada del servidor.");
      });
      form.append(recover, discard);
      announce(form, "Hay un borrador recuperable de esta pestaña. No se ha enviado.");
    }
    form.addEventListener("input", () => {
      state.dirty = true;
      remember(form);
      announce(form, "Cambios pendientes de guardar.");
      clearTimeout(state.timer);
      state.timer = setTimeout(() => {
        if (form.checkValidity()) void enqueue(form);
      }, 800);
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      clearTimeout(state.timer);
      void enqueue(form);
    });
    form.querySelector("[data-player-undo]").addEventListener("click", () => {
      if (!state.undo || state.saving || state.dirty) {
        announce(form, "Guarda primero los cambios actuales antes de deshacer.");
        return;
      }
      fields.forEach((name) => {
        form.elements[name].value = state.undo[name];
      });
      state.dirty = true;
      remember(form);
      void enqueue(form, true);
    });
  }
  const close = document.querySelector("#close-session");
  close?.addEventListener("submit", (event) => {
    if (blocked || [...states.values()].some((state) => state.dirty || state.saving)) {
      event.preventDefault();
      status.textContent = "No se cerró: guarda y confirma todos los cambios pendientes primero.";
      root.scrollIntoView();
    }
  });
  addEventListener("beforeunload", (event) => {
    if ([...states.values()].some((state) => state.dirty || state.saving)) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  const rows = [...root.querySelectorAll("[data-player-row]")];
  const nav = root.querySelector("[data-player-navigation]");
  let current = 0,
    all = false;
  function show(focus = false) {
    rows.forEach((row, index) => {
      row.hidden = !all && index !== current;
    });
    root.querySelector("[data-player-position]").textContent = `${current + 1} / ${rows.length}`;
    root.querySelector("[data-player-prev]").disabled = current === 0;
    root.querySelector("[data-player-next]").disabled = current === rows.length - 1;
    root.querySelector("[data-player-all]").textContent = all
      ? "Ver serie actual"
      : "Ver todas las series";
    if (focus) rows[current].querySelector("h3").focus();
  }
  if (rows.length) {
    nav.hidden = false;
    root.querySelector("[data-player-prev]").addEventListener("click", () => {
      current = Math.max(0, current - 1);
      show(true);
    });
    root.querySelector("[data-player-next]").addEventListener("click", () => {
      current = Math.min(rows.length - 1, current + 1);
      show(true);
    });
    root.querySelector("[data-player-all]").addEventListener("click", () => {
      all = !all;
      show();
    });
    show();
  }
})();
