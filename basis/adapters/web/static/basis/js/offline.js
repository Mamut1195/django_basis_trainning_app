/* Account-scoped IndexedDB outbox. A transport acknowledgement is the only sync success. */
(() => {
  "use strict";
  const DB = "basis-offline-v1";
  let scope = document.body.dataset.account || "";
  let dbPromise,
    syncing = false,
    conflict = null;
  const status = (text) => {
    const node = document.querySelector("#offline-status");
    if (node) node.textContent = text;
    else window.basisStatus?.(text);
  };
  function database() {
    if (!dbPromise)
      dbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(DB, 1);
        request.onupgradeneeded = () => {
          request.result.createObjectStore("sessions", { keyPath: "key" });
          request.result.createObjectStore("outbox", { keyPath: "mutation_id" });
          request.result.createObjectStore("archive", { keyPath: "key" });
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
    return dbPromise;
  }
  async function write(store, value, remove = false) {
    const db = await database();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(store, "readwrite");
      const objectStore = transaction.objectStore(store);
      if (remove) objectStore.delete(value);
      else objectStore.put(value);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  }
  async function all(store) {
    const db = await database();
    return new Promise((resolve, reject) => {
      const request = db.transaction(store).objectStore(store).getAll();
      request.onsuccess = () => resolve(request.result.filter((row) => row.account === scope));
      request.onerror = () => reject(request.error);
    });
  }
  async function pending() {
    return (await all("outbox")).length;
  }
  window.basisPending = pending;
  function download(name, content) {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(content, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function exportLocal() {
    download("basis-registros-locales.json", {
      schema: "basis-local-v1",
      account: scope,
      sessions: await all("sessions"),
      pending: await all("outbox"),
      archive: await all("archive"),
    });
  }
  async function csrf() {
    const response = await fetch("/api/csrf/", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok || !response.headers.get("Content-Type")?.includes("application/json"))
      throw new Error("Inicia sesión para sincronizar. Los registros locales siguen guardados.");
    const result = await response.json();
    if (result.account !== scope)
      throw new Error(
        "La sesión abierta pertenece a otra cuenta. Entra con la cuenta de estos registros.",
      );
    return result.token;
  }
  async function storeSession(session) {
    await write("sessions", {
      key: scope + ":" + session.id,
      account: scope,
      session,
      updated: Date.now(),
      local_version: crypto.randomUUID(),
    });
  }
  const queueOrder = (a, b) =>
    a.session.revision - b.session.revision ||
    a.created - b.created ||
    a.mutation_id.localeCompare(b.mutation_id);
  const localVersion = (record) => record.local_version || String(record.updated);
  // Read/decide/write in one transaction: another tab or a response cannot race
  // a correction into deleting an operation that has already begun sending.
  async function changeQueue(sessionId, change) {
    const db = await database();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(["sessions", "outbox", "archive"], "readwrite");
      const stores = Object.fromEntries(
        ["sessions", "outbox", "archive"].map((name) => [name, transaction.objectStore(name)]),
      );
      let result, failure;
      const request = stores.outbox.getAll();
      request.onsuccess = () => {
        const rows = request.result
          .filter((row) => row.account === scope && row.session.id === sessionId)
          .sort(queueOrder);
        const record = stores.sessions.get(scope + ":" + sessionId);
        record.onsuccess = () => {
          try {
            result = change(stores, rows, record.result);
          } catch (error) {
            failure = error;
            transaction.abort();
          }
        };
      };
      transaction.oncomplete = () => resolve(result);
      transaction.onerror = () => reject(failure || transaction.error);
      transaction.onabort = () => reject(failure || transaction.error);
    });
  }
  function replaceUnsent(stores, rows, session, revision, record) {
    if (rows.length) {
      stores.archive.put({
        key: scope + ":" + crypto.randomUUID(),
        account: scope,
        reason: "Corrección deliberada de un borrador local o una validación rechazada",
        operations: rows,
      });
      for (const row of rows) stores.outbox.delete(row.mutation_id);
    }
    const snapshot = structuredClone(session);
    snapshot.revision = revision;
    const mutation = {
      mutation_id: crypto.randomUUID(),
      account: scope,
      session: snapshot,
      created: Date.now(),
      delivery: "unsent",
    };
    stores.outbox.put(mutation);
    stores.sessions.put({
      ...record,
      key: scope + ":" + session.id,
      account: scope,
      session: snapshot,
      updated: Date.now(),
      local_version: mutation.mutation_id,
    });
  }
  async function queueSession(session, baseRecord, completionOnly = false) {
    await changeQueue(session.id, (stores, rows, record) => {
      if (completionOnly) {
        // Closing observes only status, not the measurements in old page HTML.
        // Select the current draft INSIDE this read/decide/write transaction:
        // a concurrent save either precedes this read or sees our new version.
        const current = record?.session || rows.at(-1)?.session || session;
        if (current.status === "completed") return;
        session = structuredClone(current);
        session.status = "completed";
      } else if (!baseRecord || !record || localVersion(record) !== localVersion(baseRecord))
        throw new Error(
          "La copia local cambió en otra pantalla. Tus campos siguen abiertos; revisa la sesión antes de guardar.",
        );
      // Legacy entries without delivery are ambiguous, NOT known-unsent. Only a
      // confirmed validation rejection or our own never-sent suffix is replaceable.
      let start = rows.length;
      while (start > 0 && ["unsent", "rejected_validation"].includes(rows[start - 1].delivery))
        start--;
      const suffix = rows.slice(start);
      const revision = suffix.length
        ? suffix[0].session.revision
        : rows.length
          ? rows.at(-1).session.revision + 1
          : baseRecord && record?.acknowledged_version === localVersion(baseRecord)
            ? record.session.revision
            : session.revision;
      replaceUnsent(stores, suffix, session, revision, record);
    });
    status("Guardado en este dispositivo. Pendiente de sincronización.");
    await renderSessions();
    // Do not hold the editor's submit promise across a network operation: a user
    // can reopen and deliberately correct the local snapshot while it is in flight.
    if (navigator.onLine) void sync();
  }
  async function repairRejected(sessionId) {
    return changeQueue(sessionId, (stores, rows, record) => {
      if (
        rows.length < 2 ||
        rows[0].delivery !== "rejected_validation" ||
        !rows.slice(1).every((row) => row.delivery === "unsent")
      )
        return false;
      // The user already submitted this correction while the preceding request
      // was in flight. Its 400 is now definitive; that revision was not consumed.
      replaceUnsent(stores, rows, rows.at(-1).session, rows[0].session.revision, record);
      return true;
    });
  }
  const validationMessage = (item) =>
    "Registro sin sincronizar: " +
    item.validation_error +
    " Abre la sesión, corrige los campos y guarda de nuevo.";
  async function acknowledge(item, session) {
    await changeQueue(item.session.id, (stores, rows, record) => {
      if (!rows.some((row) => row.mutation_id === item.mutation_id)) return;
      stores.outbox.delete(item.mutation_id);
      if (rows.length === 1) {
        const version = record ? localVersion(record) : item.mutation_id;
        stores.sessions.put({
          ...record,
          key: scope + ":" + session.id,
          account: scope,
          session,
          updated: Date.now(),
          local_version: version,
          acknowledged_version: version,
        });
      }
    });
  }
  function showConflict(item, current) {
    conflict = { item, current };
    document.querySelector("#conflict-local").textContent = JSON.stringify(item.session, null, 2);
    document.querySelector("#conflict-remote").textContent = JSON.stringify(current, null, 2);
    const localButton = document.querySelector("[data-conflict=local]");
    localButton.disabled = current.status === "completed";
    localButton.title = localButton.disabled
      ? "El historial completado se conserva. Exporta tu copia local para revisarla."
      : "";
    const dialog = document.querySelector("#sync-conflict");
    if (!dialog.open) dialog.showModal();
  }
  async function syncUnlocked() {
    if (syncing || !scope || !navigator.onLine) return;
    syncing = true;
    try {
      const token = await csrf();
      const blocked = new Set();
      while (navigator.onLine) {
        const next = (await all("outbox"))
          .filter((row) => !blocked.has(row.session.id))
          .sort((a, b) => a.session.id.localeCompare(b.session.id) || queueOrder(a, b))[0];
        if (!next) break;
        if (next.delivery === "rejected_validation") {
          if (await repairRejected(next.session.id)) continue;
          status(validationMessage(next));
          blocked.add(next.session.id);
          continue;
        }
        const item = await changeQueue(next.session.id, (stores, rows) => {
          const current = rows.find((row) => row.mutation_id === next.mutation_id);
          if (!current) return null; // Superseded before claim; reread the queue.
          current.delivery = "attempted";
          stores.outbox.put(current);
          return current;
        });
        if (!item) continue;
        let response;
        try {
          response = await fetch("/api/sync/", {
            method: "POST",
            credentials: "same-origin",
            cache: "no-store",
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({
              mutation_id: item.mutation_id,
              account: item.account,
              session: item.session,
              created: item.created,
            }),
          });
        } catch (_) {
          status("Sin conexión. Los pendientes siguen guardados.");
          break;
        }
        if (response.status === 409) {
          const result = await response.json();
          blocked.add(item.session.id);
          showConflict(item, result.current);
          status("Hay un conflicto pendiente de revisión.");
          continue;
        }
        if (
          response.status === 400 &&
          response.headers.get("Content-Type")?.includes("application/json")
        ) {
          const result = await response.json();
          if (
            Array.isArray(result.detail) &&
            result.detail.every((text) => typeof text === "string") &&
            result.detail.length
          ) {
            item.delivery = "rejected_validation";
            item.validation_error = result.detail.join(" ");
            await changeQueue(item.session.id, (stores, rows) => {
              if (rows.some((row) => row.mutation_id === item.mutation_id)) stores.outbox.put(item);
            });
            if (await repairRejected(item.session.id)) continue;
            status(validationMessage(item));
            blocked.add(item.session.id);
            continue;
          }
        }
        if (!response.ok || !response.headers.get("Content-Type")?.includes("application/json")) {
          status(
            response.status === 403
              ? "No hay acceso activo para enviar registros. Puedes exportarlos; no se han borrado."
              : "No se pudo sincronizar. Conservamos los registros para revisar o reintentar.",
          );
          blocked.add(item.session.id);
          continue;
        }
        const result = await response.json();
        if (!result.session || result.session.id !== item.session.id)
          throw new Error("Respuesta de sincronización inválida; se conserva el pendiente.");
        await acknowledge(item, result.session);
      }
      if (!(await pending())) status("Todos los registros están sincronizados.");
      await renderSessions();
    } catch (error) {
      status(error.message || "El almacenamiento no está disponible.");
    } finally {
      syncing = false;
    }
  }
  async function sync() {
    if (navigator.locks) return navigator.locks.request("basis-sync-" + scope, syncUnlocked);
    status(
      "Este navegador no permite coordinar el envío entre pantallas. Los registros locales se conservan para exportar.",
    );
  }
  function element(tag, text, attributes = {}) {
    const node = document.createElement(tag);
    if (text !== null) node.textContent = text;
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }
  async function renderSessions() {
    const container = document.querySelector("#offline-sessions");
    if (!container) return;
    container.replaceChildren();
    const queued = await all("outbox");
    for (const record of await all("sessions")) {
      const row = element("div", null, { class: "offline-row row" });
      const text = element("div", null);
      text.append(
        element("h2", record.session.title),
        element(
          "small",
          `${record.session.date} · ${queued.some((item) => item.session.id === record.session.id) ? "Pendiente de sincronizar" : "Sincronizada"} · ${record.session.status === "completed" ? "Completada" : "En curso"}`,
        ),
      );
      const button = element("button", "Abrir sesión", { type: "button" });
      button.addEventListener("click", () =>
        openEditor(record).catch((error) =>
          status(error.message || "No se pudo abrir la copia local. Los registros se conservan."),
        ),
      );
      const rejected = queued.find(
        (item) => item.session.id === record.session.id && item.delivery === "rejected_validation",
      );
      if (rejected) text.append(element("p", validationMessage(rejected), { role: "alert" }));
      const count = queued.filter((item) => item.session.id === record.session.id).length;
      if (count) text.append(element("small", `${count} envío(s) pendiente(s)`));
      row.append(text, button);
      container.append(row);
    }
    if (!container.children.length)
      container.append(
        element(
          "p",
          scope
            ? "Aún no tienes sesiones descargadas. Abre una sesión en línea y pulsa «Guardar sin conexión»."
            : "Inicia sesión en línea y descarga una sesión para prepararla en este dispositivo.",
          { class: "muted" },
        ),
      );
  }
  function numberInput(form, label, value, path, step = "any", max = null) {
    const wrapper = element("div", null);
    const id = "offline-" + path.join("-");
    wrapper.append(element("label", label, { for: id }));
    const input = element("input", null, {
      id,
      type: "number",
      step,
      inputmode: "decimal",
      min: "0",
    });
    if (max !== null) input.max = String(max);
    input.value = value ?? "";
    input.dataset.path = JSON.stringify(path);
    input.dataset.number = "true";
    wrapper.append(input);
    form.append(wrapper);
  }
  async function openEditor(record) {
    // A list row may predate a save/close in another tab. Review must open the
    // actual record, not just attach a fresh version to that stale row's data.
    const current = (await all("sessions")).find((row) => row.key === record.key);
    if (!current)
      throw new Error("La copia local ya no está disponible. Revisa las sesiones guardadas.");
    record = current;
    const container = document.querySelector("#offline-editor-content");
    const section = document.querySelector("#offline-editor");
    if (!container) return;
    section.hidden = false;
    container.replaceChildren();
    const snapshot = structuredClone(record.session);
    const completed =
      snapshot.status === "completed" &&
      !(await all("outbox")).some((item) => item.session.id === snapshot.id);
    container.append(element("h2", snapshot.title));
    const form = element("form", null, { class: "stack" });
    const fields = element("div", null, { class: "form-fields" });
    numberInput(
      fields,
      "Duración (" + snapshot.duration_protocol + ", segundos)",
      snapshot.duration_seconds,
      ["duration_seconds"],
      "1",
      604800,
    );
    numberInput(
      fields,
      "RPE real de sesión (0–10)",
      snapshot.reported_rpe,
      ["reported_rpe"],
      "0.5",
      10,
    );
    form.append(fields);
    const schema = JSON.parse(document.querySelector("#offline-schema")?.textContent || "{}");
    for (let index = 0; index < snapshot.blocks.length; index++) {
      const block = snapshot.blocks[index];
      const fieldset = element("fieldset", null);
      fieldset.append(element("legend", block.title));
      const detail = element("details", null);
      detail.append(
        element("summary", "Ver prescripción"),
        element("pre", JSON.stringify(block.target, null, 2)),
      );
      fieldset.append(detail);
      const blockFields = element("div", null, { class: "form-fields" });
      for (const [key, spec] of Object.entries(schema[block.sport] || {})) {
        const path = ["blocks", index, "actual", key];
        if (["text", "choice"].includes(spec.kind)) {
          const wrapper = element("div", null),
            id = `metric-${index}-${key}`;
          wrapper.append(element("label", spec.label, { for: id }));
          const input =
            spec.kind === "choice"
              ? element("select", null, { id })
              : element("input", null, { id, type: "text", maxlength: "500" });
          if (spec.kind === "choice") {
            input.append(element("option", "Sin registrar", { value: "" }));
            for (const choice of spec.choices)
              input.append(element("option", choice, { value: choice }));
          }
          input.value = block.actual[key] ?? "";
          input.dataset.path = JSON.stringify(path);
          wrapper.append(input);
          blockFields.append(wrapper);
        } else {
          numberInput(
            blockFields,
            spec.label + (spec.unit ? " (" + spec.unit + ")" : ""),
            block.actual[key],
            path,
            spec.kind === "integer" ? "1" : "any",
            spec.maximum,
          );
          if (spec.kind === "altitude") blockFields.lastChild.querySelector("input").min = "-500";
        }
      }
      fieldset.append(blockFields);
      for (let n = 0; n < block.sets.length; n++) {
        const row = block.sets[n];
        const setFields = element("div", null, { class: "form-fields" });
        fieldset.append(
          element(
            "h3",
            `Serie ${n + 1} · objetivo ${row.target_reps ?? "—"} × ${row.target_kg ?? "—"} kg`,
          ),
        );
        for (const [key, label, step, max] of [
          ["actual_reps", "Repeticiones reales", "1", 10000],
          ["actual_kg", "Carga real (kg)", "0.25", 99999],
          ["actual_rpe", "RPE real", "0.5", 10],
          ["actual_rir", "RIR real", "1", 20],
          ["actual_rest_seconds", "Descanso real (s)", "1", 100000],
          ["isometric_seconds", "Isometría real (s)", "1", 100000],
        ])
          numberInput(setFields, label, row[key], ["blocks", index, "sets", n, key], step, max);
        fieldset.append(setFields);
        const adaptation = element("details");
        adaptation.append(
          element("summary", "Adaptación real opcional · conserva la prescripción"),
        );
        const adaptationFields = element("div", null, { class: "form-fields" });
        numberInput(
          adaptationFields,
          "Ejercicio real (ID de catálogo, opcional)",
          row.actual_exercise,
          ["blocks", index, "sets", n, "actual_exercise"],
          "1",
          2147483647,
        );
        for (const [key, label, options] of [
          ["actual_load_type", "Carga realizada", ["external", "bodyweight", "assisted"]],
          ["actual_kind", "Serie realizada", ["warmup", "work", "failed"]],
          ["actual_side", "Lado realizado", ["both", "left", "right"]],
        ]) {
          const id = "offline-" + ["blocks", index, "sets", n, key].join("-");
          const wrapper = element("div", null);
          wrapper.append(element("label", label, { for: id }));
          const select = element("select", null, {
            id,
            "data-path": JSON.stringify(["blocks", index, "sets", n, key]),
          });
          for (const value of ["", ...options]) {
            const option = element("option", value || "Sin adaptación", { value });
            option.selected = (row[key] ?? "") === value;
            select.append(option);
          }
          wrapper.append(select);
          adaptationFields.append(wrapper);
        }
        for (const [key, label, max] of [
          ["actual_tempo", "Tempo realizado", 30],
          ["actual_range_of_motion", "Rango de movimiento realizado", 80],
          ["actual_group", "Grupo realizado", 80],
          ["adaptation_reason", "Motivo de adaptación", 1000],
        ]) {
          const wrapper = element("label", label);
          wrapper.append(
            element("input", null, {
              type: "text",
              value: row[key] ?? "",
              maxlength: String(max),
              "data-path": JSON.stringify(["blocks", index, "sets", n, key]),
            }),
          );
          adaptationFields.append(wrapper);
        }
        adaptation.append(adaptationFields);
        fieldset.append(adaptation);
      }
      for (let n = 0; n < block.intervals.length; n++) {
        const interval = block.intervals[n];
        fieldset.append(element("h3", `Intervalo ${n + 1} · ${interval.repetitions} repeticiones`));
        const intervalFields = element("div", null, { class: "form-fields" });
        for (const [key, spec] of Object.entries(schema[block.sport] || {}))
          if (!["text", "choice"].includes(spec.kind))
            numberInput(
              intervalFields,
              spec.label + (spec.unit ? " (" + spec.unit + ")" : ""),
              interval.actual[key],
              ["blocks", index, "intervals", n, "actual", key],
              spec.kind === "integer" ? "1" : "any",
              spec.maximum,
            );
        numberInput(
          intervalFields,
          "RPE real de intervalo",
          interval.actual_rpe,
          ["blocks", index, "intervals", n, "actual_rpe"],
          "0.5",
          10,
        );
        numberInput(
          intervalFields,
          "Descanso real de intervalo (s)",
          interval.actual_rest_seconds,
          ["blocks", index, "intervals", n, "actual_rest_seconds"],
          "1",
          100000,
        );
        fieldset.append(intervalFields);
      }
      form.append(fieldset);
    }
    const controls = element("div", null, { class: "offline-controls actions" });
    if (!completed) {
      const save = element("button", "Guardar registro", {
          type: "submit",
          name: "mode",
          value: "draft",
        }),
        finish = element("button", "Completar sesión", {
          type: "submit",
          name: "mode",
          value: "complete",
        });
      controls.append(save, finish);
    } else {
      for (const input of form.querySelectorAll("input,select")) input.disabled = true;
      controls.append(element("p", "El historial completado se conserva sin cambios."));
    }
    form.append(controls);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const updated = structuredClone(snapshot);
      for (const input of form.querySelectorAll("[data-path]")) {
        const path = JSON.parse(input.dataset.path);
        let target = updated;
        for (const part of path.slice(0, -1)) target = target[part];
        const key = path.at(-1);
        const value = input.value;
        if (path.includes("actual") && value === "") delete target[key];
        else
          target[key] =
            value === ""
              ? key === "adaptation_reason"
                ? ""
                : null
              : input.dataset.number
                ? Number(value)
                : value;
      }
      if (event.submitter?.value === "complete") updated.status = "completed";
      try {
        await queueSession(updated, record);
        section.hidden = true;
      } catch (error) {
        status(
          error.message ||
            "No se pudo guardar en este dispositivo. Mantén esta pantalla abierta y exporta tus datos.",
        );
      }
    });
    container.append(form);
    section.scrollIntoView({ behavior: "auto" });
  }
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-download-session]");
    if (button) {
      try {
        const response = await fetch(`/api/sessions/${button.dataset.downloadSession}/snapshot/`, {
          credentials: "same-origin",
          cache: "no-store",
        });
        if (!response.ok) throw new Error("No se pudo descargar la sesión.");
        const result = await response.json();
        if (result.account !== scope) throw new Error("La sesión pertenece a otra cuenta.");
        if ((await all("outbox")).some((item) => item.session.id === result.session.id))
          throw new Error(
            "Hay registros locales pendientes. Revisa la copia guardada antes de descargar otra versión.",
          );
        await storeSession(result.session);
        status("Sesión guardada en este dispositivo. Ábrela desde «Sesiones sin conexión».");
      } catch (error) {
        status(error.message);
      }
    }
    if (event.target.closest("[data-sync-now]")) await sync();
    if (event.target.closest("[data-export-local]")) await exportLocal();
    const complete = event.target.closest("[data-complete-session]");
    if (complete) {
      const node = document.querySelector("#session-snapshot");
      if (!node) return;
      complete.disabled = true;
      try {
        await queueSession(JSON.parse(node.textContent), null, true);
        if (!(await pending())) location.reload();
      } catch (error) {
        status(error.message || "No se pudo cerrar el registro. La copia local se conserva.");
      } finally {
        complete.disabled = false;
      }
    }
    const decision = event.target.closest("[data-conflict]")?.dataset.conflict;
    if (decision && conflict) {
      document.querySelector("#sync-conflict").close();
      if (decision === "close") return;
      if (!navigator.locks) return;
      const { item, current } = conflict;
      await navigator.locks.request("basis-sync-" + scope, () =>
        changeQueue(item.session.id, (stores, rows, record) => {
          // A previous sync may have already resolved this exact dialog.
          if (!rows.some((row) => row.mutation_id === item.mutation_id)) return;
          const latest = record?.session || item.session;
          stores.archive.put({
            key: scope + ":" + crypto.randomUUID(),
            account: scope,
            local: latest,
            remote: current,
            operations: rows,
          });
          for (const row of rows) stores.outbox.delete(row.mutation_id);
          if (decision === "server")
            stores.sessions.put({
              key: scope + ":" + current.id,
              account: scope,
              session: current,
              updated: Date.now(),
              local_version: crypto.randomUUID(),
            });
          else replaceUnsent(stores, [], latest, current.revision, record);
        }),
      );
      conflict = null;
      await renderSessions();
      if (navigator.onLine) void sync();
    }
  });
  document.addEventListener("submit", async (event) => {
    if (!event.target.matches("[data-logout]")) return;
    event.preventDefault();
    const count = await pending();
    if (count) {
      await exportLocal();
      if (
        !confirm(
          "Se descargó una copia de tus registros pendientes. ¿Cerrar sesión y borrar la copia de este dispositivo?",
        )
      )
        return;
    }
    try {
      const response = await fetch(event.target.action, {
        method: "POST",
        body: new FormData(event.target),
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("Logout failed");
      for (const store of ["sessions", "outbox", "archive"])
        for (const row of await all(store))
          await write(store, store === "outbox" ? row.mutation_id : row.key, true);
      localStorage.removeItem("basis-account");
      localStorage.removeItem("basis-timer");
      channel.postMessage({ type: "logout", account: scope });
      location.assign(response.url);
    } catch (_) {
      status(
        "No se pudo cerrar la sesi\u00f3n. Tus registros locales se conservan; vuelve a intentarlo.",
      );
    }
  });
  addEventListener("online", sync);
  const channel = new BroadcastChannel("basis-auth");
  channel.onmessage = (event) => {
    if (event.data?.type === "logout" && event.data.account === scope)
      location.replace("/accounts/login/");
  };
  (async () => {
    try {
      if (scope) localStorage.setItem("basis-account", scope);
      else if (location.pathname === "/offline/")
        scope = localStorage.getItem("basis-account") || "";
      if (document.querySelector("#offline-sessions")) {
        await renderSessions();
        status(
          navigator.onLine
            ? "Sesiones de esta cuenta guardadas en el dispositivo."
            : "Sin conexión. Puedes registrar datos en las sesiones descargadas.",
        );
      }
      if (scope && navigator.onLine && (await pending())) await sync();
    } catch (error) {
      status(
        "El almacenamiento local no está disponible. No cierres una sesión con registros sin exportar.",
      );
    }
  })();
})();
