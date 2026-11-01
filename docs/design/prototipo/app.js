/* Classic local JS. All mutable demo data is intentionally process-memory only. */
"use strict";

const demo = {
  state: "normal",
  date: "2026-10-23",
  plan: "Fuerza A · 3 series × 8 repeticiones",
  accepted: false,
  rejected: false,
  sets: Array.from({ length: 3 }, () => ({
    reps: null,
    load: null,
    rpe: null,
    rir: null,
    checked: false,
  })),
  cardio: { minutes: null, distance: null },
  restDeadline: null,
  signupComplete: false,
};
const routes = {
  hoy: ["Hoy", "TU DÍA, PASO A PASO", "Viernes 23 de octubre de 2026 · Fecha ficticia"],
  entrenamiento: [
    "Tu sesión",
    "REGISTRAR, NO ADIVINAR",
    "Sesión A ficticia · Independiente del futuro plan B",
  ],
  plan: [
    "Tu plan",
    "LA INTENCIÓN ANTES DE LA ACCIÓN",
    "19–25 de octubre de 2026 · Semana ficticia",
  ],
  progreso: [
    "Tu progreso",
    "CONTEXTO ANTES QUE NÚMEROS",
    "Ejemplos ficticios · No se calculan métricas deportivas",
  ],
  entrenador: [
    "Entrenador",
    "TÚ TOMAS LA DECISIÓN",
    "Propuesta editorial ficticia · Sin proveedor IA",
  ],
  bienvenida: [
    "Bienvenida a BASIS",
    "ENTRENA CON INTENCIÓN",
    "Un recorrido de diseño, no un servicio activo",
  ],
  registro: [
    "Registro de demostración",
    "PRUEBA SIN CREAR UNA CUENTA",
    "Usa solo datos inventados y una contraseña ficticia",
  ],
};
const stateMessages = {
  normal: [
    "Demo disponible",
    "Puedes recorrer las pantallas. Nada se guarda fuera de esta pestaña.",
  ],
  empty: [
    "Aún no hay datos en esta vista",
    "Ejemplo de primer uso: no hay resultados, porcentajes ni recomendaciones que inferir.",
  ],
  loading: [
    "Cargando · ejemplo detenido",
    "Este estado no hace una petición. Cambia a Normal para continuar; no habrá un éxito automático.",
  ],
  error: [
    "No se pudo completar · error ilustrativo",
    "Tus entradas en memoria se conservan. No se ha enviado nada. Volver a Normal solo restablece la demostración.",
  ],
  offline: [
    "Sin conexión · estado ilustrativo",
    "Puedes ensayar el registro en memoria. No hay almacenamiento duradero: recargar pierde los datos. Nada está sincronizado.",
  ],
  pending: [
    "Sincronización pendiente · ejemplo",
    "La aplicación real esperaría confirmación del servidor. Este boceto no tiene cola persistente ni puede enviar o confirmar operaciones.",
  ],
  conflict: [
    "Conflicto · ejemplo de revisión",
    "Dos copias ilustrativas, sin servidor. No se sobrescribe nada automáticamente. Las acciones de edición quedan bloqueadas en este estado.",
  ],
};
const main = document.querySelector("#main");
const view = document.querySelector("#view");
const announce = (text) => {
  document.querySelector("#announcement").textContent = text;
};
const escapeHTML = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char],
  );
const observed = (value, unit = "") =>
  value === null ? "Sin datos" : `${escapeHTML(value)}${unit}`;
const route = () =>
  Object.hasOwn(routes, location.hash.slice(1)) ? location.hash.slice(1) : "hoy";
const blocked = () => ["loading", "error", "conflict", "empty"].includes(demo.state);
const buttonLink = (href, text, primary = false) =>
  `<a class="button${primary ? " primary" : ""}" href="#${href}">${text}</a>`;

function today() {
  return `<section class="card" id="today-session" aria-labelledby="session-title"><p class="eyebrow">SESIÓN DE HOY · FICTICIA</p><h2 id="session-title">Fuerza A + cardio suave</h2><p><strong>Sentadilla</strong> · Prescrito: 3 × 8 rep · 40 kg · RPE 7 · RIR 3</p><p><strong>Cardio</strong> · Estimado: 20 min suaves. Medido: Sin datos.</p><p class="muted">El registro A no cambia al aceptar un plan futuro B.</p><a id="start-training" class="button primary" href="#entrenamiento">Comenzar</a></section><section class="weekly-summary" aria-label="Resumen semanal ficticio"><h2>Tu semana · Ficticia</h2><p>2 sesiones completadas de 3 previstas · Historial fijo de ejemplo.</p><p class="muted">Próximo plan: <strong data-plan-name>${escapeHTML(demo.plan)}</strong> · <span data-plan-date>${demo.date}</span>. No cambia la fecha ficticia de hoy.</p></section>`;
}
function numberField(id, label, value, max, step = "1", compact = false) {
  return `<div class="field"><label${compact ? ' class="sr-only"' : ""} for="${id}">${label}</label><input id="${id}" name="${id}" type="number" inputmode="decimal" min="0" max="${max}" step="${step}" value="${value === null ? "" : escapeHTML(value)}" /></div>`;
}
function training() {
  const sets = demo.sets
    .map((set, index) => {
      const n = index + 1;
      return `<tr data-set="${n}"><th scope="row">${n}</th><td>${numberField(`load-${n}`, `Carga real serie ${n} (kg)`, set.load, 500, "0.5", true)}</td><td>${numberField(`reps-${n}`, `Repeticiones reales serie ${n}`, set.reps, 100, "1", true)}</td><td>${numberField(`rpe-${n}`, `RPE real serie ${n} (0–10)`, set.rpe, 10, "0.5", true)}</td><td><button class="set-check" id="check-${n}" type="button" aria-pressed="${set.checked}" aria-label="${set.checked ? "Desmarcar" : "Marcar"} serie ${n}">${set.checked ? "✓ Realizada" : "Pendiente"}</button></td></tr><tr><td colspan="5"><p class="previous">Anterior ficticio · Serie ${n}: 40 kg · 8 rep · RPE 7. No son valores realizados hoy.</p><details class="set-details"><summary>Serie ${n}: prescripción y RIR opcional</summary><p>Prescrito A: 8 rep · 40 kg · RPE 7 / 10 · RIR 3.</p>${numberField(`rir-${n}`, `RIR real serie ${n} (0–10, opcional)`, set.rir, 10)}</details></td></tr>`;
    })
    .join("");
  return `<article class="card training-card"><h2>01 / Sentadilla · Sesión A</h2><p class="muted" id="set-help">Realizado: campos vacíos = Sin datos; 0 = cero observado. Para marcar, completa kg, reps y RPE. RIR es opcional e independiente. Desmarca explícitamente para corregir una serie.</p><form id="training-form" aria-describedby="set-help"><table id="sets-table"><caption>Registro rápido · Datos ficticios</caption><thead><tr><th scope="col">Serie</th><th scope="col">kg</th><th scope="col">Reps</th><th scope="col">RPE</th><th scope="col">Check</th></tr></thead><tbody>${sets}</tbody></table><section class="rest" aria-label="Descanso ilustrativo"><h3>Descanso demo · 90 s ilustrativos</h3><p id="rest-timer" aria-live="off"></p><p class="muted">No es una recomendación. No marca series ni envía el registro al terminar.</p><button id="skip-rest" type="button">Omitir descanso</button></section><h2>02 / Cardio</h2><p class="prescription"><strong>Estimado / prescrito:</strong> 20 min suaves. Distancia estimada: Sin datos.</p><h3>Medido / realizado</h3><div class="fields">${numberField("minutes", "Duración medida (min)", demo.cardio.minutes, 600, "0.1")}${numberField("distance", "Distancia medida (km)", demo.cardio.distance, 200, "0.01")}</div><p class="muted">FC, potencia y cadencia: Sin datos. No hay sensores conectados.</p><div class="actions"><button class="primary" id="save-training" type="submit">Conservar en memoria demo</button>${buttonLink("hoy", "Volver a Hoy")}</div></form></article><article class="card" id="record-summary"><h2>Registro en memoria · No enviado</h2><div id="record-values">${recordValues()}</div><p class="muted">Recargar o cerrar borra este registro.</p></article>`;
}
function recordValues() {
  return `${demo.sets.map((set, i) => `<p>Serie ${i + 1} · ${set.checked ? "Realizada" : "Pendiente"}: ${observed(set.reps, " rep")} · ${observed(set.load, " kg")} · RPE ${observed(set.rpe)} · RIR ${observed(set.rir)}</p>`).join("")}<p>Cardio medido: ${observed(demo.cardio.minutes, " min")} · ${observed(demo.cardio.distance, " km")}</p>`;
}
function planning() {
  const days = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
  return `<section aria-label="Semana ficticia del 19 al 25 de octubre de 2026"><ol id="week-strip">${days.map((day, i) => `<li${i === 4 ? ' class="fixture-today"' : ""}><span>${day}</span><time datetime="2026-10-${19 + i}">${19 + i}</time>${i === 4 ? '<span class="sr-only">Hoy ficticio</span>' : ""}</li>`).join("")}</ol><p class="muted">Hoy ficticio: viernes 23. La fecha del próximo plan puede quedar fuera de esta semana.</p></section><div class="grid"><article class="card"><h2 data-plan-name>${escapeHTML(demo.plan)}</h2><p>Fecha programada: <strong data-plan-date>${demo.date}</strong></p><p class="muted">Cambia solo la fecha del próximo plan en memoria, no el registro A ni la historia.</p><details id="reschedule-details"><summary id="show-reschedule">Reprogramar</summary><form id="reschedule-form"><div class="field"><label for="new-date">Nueva fecha de la sesión ficticia</label><input type="date" id="new-date" name="new-date" min="2026-10-23" max="2027-10-23" value="${demo.date}" required /></div><div class="actions"><button id="reschedule" class="primary" type="submit">Aplicar fecha solo en demo</button><button id="cancel-reschedule" type="button">Cancelar</button></div></form></details></article><article class="card"><h2>Antes de cambiar</h2><p class="muted">En el producto, la revisión de versión evita sobrescribir cambios concurrentes. «Conflicto» solo muestra una comparación ilustrativa.</p><p>Plan actual: ${demo.accepted ? "propuesta ficticia aceptada en esta pestaña" : "original ficticio, sin cambios de IA"}.</p>${buttonLink("entrenador", "Ver propuesta IA")}</article></div>`;
}
function progress() {
  return `<section class="weekly-summary"><h2>Lo que sabes. Y lo que aún no.</h2><p>No comparar deportes ni completar observaciones ausentes.</p></section><div class="grid"><article class="card"><h2>Semana de ejemplo · Ficticia</h2><dl class="stats"><div><dt>Sesiones completadas</dt><dd>2</dd></div><div><dt>Sesiones previstas</dt><dd>3</dd></div><div><dt>FC media medida</dt><dd>Sin datos</dd></div></dl><p class="muted">Conteos ilustrativos fijos, independientes del formulario demo. No representan tu adherencia real.</p><div class="progress-row"><span>Sentadilla · Carga externa medida</span><strong>40 kg</strong></div><div class="progress-row"><span>Sentadilla · e1RM estimado</span><strong>Sin datos</strong></div><div class="progress-row"><span>Cardio · Duración estimada</span><strong>20 min</strong></div><div class="progress-row"><span>Cardio · Duración medida</span><strong>Sin datos</strong></div><div class="progress-row"><span>Cardio · Ascenso medido</span><strong>0 m</strong></div><p class="muted">0 m es una observación ficticia de cero. «Sin datos» es ausencia. No hay cálculo de e1RM ni equivalencia entre RPE/RIR.</p></article><article class="card"><h2>Registro de esta pestaña</h2><p>Serie 1 realizada: ${observed(demo.sets[0].reps, " rep")} · ${observed(demo.sets[0].load, " kg")}</p><p>Cardio medido: ${observed(demo.cardio.minutes, " min")}</p><p class="muted">No se combina con el historial fijo de ejemplo.</p>${buttonLink("entrenamiento", "Volver al registro")}</article></div>`;
}
function coach() {
  const status = demo.accepted
    ? "Aceptada solo en memoria"
    : demo.rejected
      ? "Rechazada solo en memoria"
      : "Sin aceptar";
  return `<article class="card"><div class="card-top"><h2>Propuesta IA · Ficticia</h2><span class="badge" id="proposal-status">${status}</span></div><p>Ejemplo editorial, no generado por IA. No evalúa tu salud, recuperación ni objetivos.</p><div class="comparison"><div><h3>Plan original ficticio</h3><p>Fuerza A · 3 series × 8 repeticiones</p><p>Cardio estimado: 20 min</p></div><div><h3>Propuesta, aún sin aplicar</h3><p>Fuerza B · 2 series × 8 repeticiones</p><p>Mantener cardio estimado: 20 min</p></div></div><p class="muted">Motivo ficticio: ilustrar una reducción de series. No es una recomendación. Las prescripciones del registro A y las ejecuciones pasadas no cambian.</p><p>Plan vigente en esta pestaña: <strong data-plan-name>${escapeHTML(demo.plan)}</strong></p>${!demo.accepted && !demo.rejected ? '<div class="actions"><button id="accept-proposal" class="primary" type="button">Aceptar cambio en plan demo</button><button id="reject-proposal" type="button">Rechazar propuesta demo</button></div><p class="muted">Aceptar es explícito y solo afecta al próximo plan ficticio, nunca al servidor.</p>' : '<p>No se ha enviado nada. Puedes restaurar el plan original y revisar de nuevo.</p><button id="reset-proposal" type="button">Restaurar plan original demo</button>'}</article><div class="actions">${buttonLink("plan", "Consultar plan vigente")}${buttonLink("hoy", "Volver a Hoy")}</div>`;
}
function welcome() {
  return `<section class="card"><h2>Tu plan orienta. Tú decides.</h2><p>Explora una sesión, distingue lo prescrito de lo realizado y revisa propuestas antes de aceptarlas.</p><p><strong>Demo ficticia y solo en memoria.</strong> No hay cuenta, correo, servidor ni sincronización. Recargar borra todo.</p><p>No introduzcas datos personales ni credenciales reales.</p><a class="button primary" id="open-registration" href="#registro">Probar registro demo</a><p class="actions"><a href="#hoy">Seguir sin registro a Hoy</a></p></section>`;
}
function signupResult() {
  return '<h2>Prueba completada solo en memoria</h2><p><strong>NO se ha creado una cuenta, NO se ha enviado correo y NO hay sincronización con servidor.</strong></p><p>No se conservan el nombre, email ni contraseña en el objeto demo. Recargar borra este resultado.</p><a class="button primary" href="#hoy">Volver a Hoy</a>';
}
function registration() {
  return `<section class="card"><p><strong>Solo datos inventados.</strong> No uses tu email ni una contraseña real. No hay servicio de registro.</p><form id="signup-form" autocomplete="off"${demo.signupComplete ? " hidden" : ""}><div class="field"><label for="signup-name">Nombre ficticio</label><input id="signup-name" name="demo-name" type="text" minlength="2" maxlength="60" required autocomplete="off" /></div><div class="field"><label for="signup-email">Email ficticio (ej.: atleta@example.test)</label><input id="signup-email" name="demo-email" type="email" required autocomplete="off" /></div><div class="field"><label for="signup-password">Contraseña ficticia (mínimo 8 caracteres)</label><input id="signup-password" type="password" minlength="8" required autocomplete="new-password" aria-describedby="password-help" /><p class="muted" id="password-help">Solo validación local; se borra al enviar o navegar. No se almacena ni se muestra en el resultado.</p></div><div class="field"><label for="signup-adult">Confirmación de mayoría de edad para la demo</label><select id="signup-adult" required><option value="">Selecciona una opción</option><option value="adult">Confirmo que soy mayor de 18 años</option></select></div><p class="muted">Todos los campos son obligatorios. Corrige el campo indicado y vuelve a intentar; no se envía nada.</p><button id="signup-submit" class="primary" type="submit">Completar prueba local</button></form><section id="signup-result" tabindex="-1"${demo.signupComplete ? "" : " hidden"}>${demo.signupComplete ? signupResult() : ""}</section></section>`;
}
function renderState() {
  const [title, text] = stateMessages[demo.state];
  document.querySelector("#state-panel").innerHTML =
    demo.state === "normal"
      ? ""
      : `<section class="notice${demo.state === "error" ? " error" : ""}" aria-labelledby="state-title"><h2 id="state-title">${title}</h2><p>${text}</p>${demo.state === "conflict" ? '<div class="comparison"><div><h3>Copia local ficticia</h3><p>Sesión: 2026-10-24 · revisión 1</p></div><div><h3>Copia remota ilustrativa</h3><p>Sesión: 2026-10-25 · revisión 2</p></div></div><p>No hay copia remota real ni resolución automática.</p>' : ""}${["empty", "error", "conflict"].includes(demo.state) ? '<button id="normal-state" type="button">Volver a Normal (demo)</button>' : ""}</section>`;
  view.hidden = ["empty", "loading"].includes(demo.state);
  view.setAttribute("aria-busy", String(demo.state === "loading"));
  view
    .querySelectorAll(
      "form button, form input, form select, #accept-proposal, #reject-proposal, #reset-proposal",
    )
    .forEach((control) => {
      control.disabled = blocked();
    });
  demo.sets.forEach((set, i) => {
    ["load", "reps", "rpe", "rir"].forEach((key) => {
      const field = document.getElementById(`${key}-${i + 1}`);
      if (field) field.disabled = blocked() || set.checked;
    });
  });
  updateRestText();
}
function render(moveFocus = false) {
  // Never retain credentials in the model or carry the password across navigation.
  const password = document.querySelector("#signup-password");
  if (password) password.value = "";
  const current = route();
  const [title, eyebrow, description] = routes[current];
  document.title = `BASIS · ${title} · Demo ficticia`;
  document.querySelector("#page-title").textContent = title;
  document.querySelector("#eyebrow").textContent = eyebrow;
  document.querySelector("#page-description").textContent = description;
  document.querySelectorAll("[data-nav]").forEach((link) => {
    if (link.dataset.nav === (current === "entrenamiento" ? "hoy" : current))
      link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  view.innerHTML = {
    hoy: today,
    entrenamiento: training,
    plan: planning,
    progreso: progress,
    entrenador: coach,
    bienvenida: welcome,
    registro: registration,
  }[current]();
  renderState();
  if (moveFocus) {
    main.focus();
    window.scrollTo(0, 0);
  }
}
function rememberForm() {
  const form = document.querySelector("#training-form");
  if (!form || blocked() || !form.checkValidity()) return;
  const read = (id) => {
    const field = document.getElementById(id);
    return field.value === "" ? null : field.valueAsNumber;
  };
  demo.sets.forEach((set, index) => {
    if (set.checked) return;
    ["reps", "load", "rpe", "rir"].forEach((key) => {
      set[key] = read(`${key}-${index + 1}`);
    });
  });
  demo.cardio = { minutes: read("minutes"), distance: read("distance") };
}
// A single interval follows a deadline, not accumulated ticks. Only its text is updated.
let restInterval = null;
function updateRestText() {
  const remaining =
    demo.restDeadline === null
      ? 0
      : Math.max(0, Math.ceil((demo.restDeadline - Date.now()) / 1000));
  const text = document.querySelector("#rest-timer");
  if (text)
    text.textContent =
      remaining > 0 ? `Descanso ilustrativo: ${remaining} s restantes` : "Sin descanso activo.";
  const skip = document.querySelector("#skip-rest");
  if (skip) skip.disabled = blocked() || remaining === 0;
}
function endRest(message) {
  if (restInterval !== null) window.clearInterval(restInterval);
  restInterval = null;
  demo.restDeadline = null;
  updateRestText();
  announce(message);
}
function startRest() {
  demo.restDeadline = Date.now() + 90000;
  if (restInterval === null)
    restInterval = window.setInterval(() => {
      if (demo.restDeadline !== null && Date.now() >= demo.restDeadline)
        endRest(
          "Descanso ilustrativo terminado. Ninguna serie se ha marcado ni enviado automáticamente.",
        );
      else updateRestText();
    }, 1000);
  updateRestText();
  announce(
    "Serie marcada realizada solo en memoria. Comienza un descanso ilustrativo de 90 segundos; no envía ni completa la sesión.",
  );
}
function checkSet(n) {
  if (blocked()) return;
  const set = demo.sets[n - 1];
  if (!set) return;
  if (set.checked) {
    set.checked = false;
    announce(`Serie ${n} pendiente de nuevo. Puedes corregir sus datos.`);
  } else {
    const fields = ["load", "reps", "rpe", "rir"].map((key) =>
      document.getElementById(`${key}-${n}`),
    );
    const invalid = fields.find(
      (field, index) => !field.checkValidity() || (index < 3 && field.value === ""),
    );
    if (invalid) {
      announce(`Completa kg, repeticiones y RPE válidos de la serie ${n}. RIR es opcional.`);
      if (invalid.value === "")
        invalid.setCustomValidity("Completa este dato real antes de marcar la serie.");
      invalid.reportValidity();
      invalid.focus();
      return;
    }
    // Read only the validated row; unrelated unfinished rows must not be discarded.
    ["load", "reps", "rpe", "rir"].forEach((key, i) => {
      set[key] = fields[i].value === "" ? null : fields[i].valueAsNumber;
    });
    set.checked = true;
    startRest();
  }
  const button = document.getElementById(`check-${n}`);
  button.setAttribute("aria-pressed", String(set.checked));
  button.setAttribute("aria-label", `${set.checked ? "Desmarcar" : "Marcar"} serie ${n}`);
  button.textContent = set.checked ? "✓ Realizada" : "Pendiente";
  ["load", "reps", "rpe", "rir"].forEach((key) => {
    document.getElementById(`${key}-${n}`).disabled = set.checked;
  });
  document.querySelector("#record-values").innerHTML = recordValues();
}
view.addEventListener("input", (event) => {
  if (event.target.matches("input")) event.target.setCustomValidity("");
  rememberForm();
});
view.addEventListener("submit", (event) => {
  event.preventDefault();
  if (blocked()) {
    announce("Acción bloqueada en este estado ilustrativo. No se ha cambiado nada.");
    return;
  }
  if (!event.target.reportValidity()) return;
  if (event.target.id === "training-form") {
    rememberForm();
    document.querySelector("#record-values").innerHTML = recordValues();
    announce(
      "Registro ficticio conservado solo en memoria. No enviado ni sincronizado. Recargar lo borra.",
    );
  } else if (event.target.id === "reschedule-form") {
    demo.date = document.querySelector("#new-date").value;
    render();
    document.querySelector("#show-reschedule").focus();
    announce(`Fecha ficticia cambiada a ${demo.date} solo en memoria. No enviada al servidor.`);
  } else if (event.target.id === "signup-form") {
    // Read no credential values. The only model change is a demonstration boolean.
    demo.signupComplete = true;
    event.target.reset();
    document.querySelector("#signup-password").value = "";
    event.target.hidden = true;
    const result = document.querySelector("#signup-result");
    result.innerHTML = signupResult();
    result.hidden = false;
    result.focus();
    announce(
      "Prueba local completada. NO se creó cuenta, NO se envió correo y NO hay sincronización. Solo memoria demo.",
    );
  }
});
view.addEventListener("click", (event) => {
  const id = event.target.closest("button")?.id;
  if (blocked() || !id) return;
  if (/^check-[1-3]$/.test(id)) {
    checkSet(Number(id.slice(-1)));
    return;
  }
  if (id === "skip-rest") {
    if (demo.restDeadline !== null)
      endRest("Descanso ilustrativo omitido. No se ha marcado ni enviado ninguna serie.");
    return;
  }
  if (id === "cancel-reschedule") {
    document.querySelector("#new-date").value = demo.date;
    document.querySelector("#reschedule-details").open = false;
    document.querySelector("#show-reschedule").focus();
    announce("Reprogramación cancelada. La fecha no ha cambiado.");
    return;
  }
  if (id === "accept-proposal") {
    demo.plan = "Fuerza B · 2 series × 8 repeticiones";
    demo.accepted = true;
    announce(
      "Propuesta ficticia aceptada explícitamente. Solo el plan en memoria cambia; el registro A permanece intacto.",
    );
  } else if (id === "reject-proposal") {
    demo.rejected = true;
    announce("Propuesta ficticia rechazada. El plan no ha cambiado.");
  } else if (id === "reset-proposal") {
    demo.plan = "Fuerza A · 3 series × 8 repeticiones";
    demo.accepted = false;
    demo.rejected = false;
    announce("Plan original ficticio restaurado solo en memoria.");
  } else return;
  render();
  document
    .querySelector(demo.accepted || demo.rejected ? "#reset-proposal" : "#accept-proposal")
    .focus();
});
document.querySelector("#state").addEventListener("change", (event) => {
  rememberForm();
  demo.state = event.target.value;
  renderState();
  announce(stateMessages[demo.state].join(". "));
});
document.querySelector("#state-panel").addEventListener("click", (event) => {
  if (event.target.id !== "normal-state") return;
  demo.state = "normal";
  document.querySelector("#state").value = "normal";
  renderState();
  document.querySelector("#demo-tools").open = true;
  document.querySelector("#state").focus();
  announce("Normal restablecido solo para explorar la demo. Ninguna operación se ha sincronizado.");
});
document.querySelector("#theme").addEventListener("click", (event) => {
  const dark = document.documentElement.dataset.theme !== "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  event.target.setAttribute("aria-pressed", String(dark));
  event.target.textContent = dark ? "Tema claro" : "Tema oscuro";
  announce(`Tema ${dark ? "oscuro" : "claro"}. Cambian únicamente los tokens CSS.`);
});
window.addEventListener("hashchange", () => {
  render(true);
  announce(`${routes[route()][0]}. Demo ficticia, cambios solo en memoria.`);
});
render();
