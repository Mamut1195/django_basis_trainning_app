/* Classic local JS. All mutable demo data is intentionally process-memory only. */
"use strict";

const demo = {
  state: "normal",
  date: "2026-10-23",
  plan: "Fuerza A · 3 series × 8 repeticiones",
  accepted: false,
  rejected: false,
  sets: [
    { reps: null, load: null, rpe: null, rir: null },
    { reps: null, load: null, rpe: null, rir: null },
    { reps: null, load: null, rpe: null, rir: null },
  ],
  cardio: { minutes: null, distance: null },
};
const routes = {
  hoy: ["Hoy", "TU DÍA, PASO A PASO", "Viernes 23 de octubre de 2026 · Semana ficticia 04"],
  entrenamiento: [
    "Tu sesión",
    "REGISTRAR, NO ADIVINAR",
    "Fuerza A + cardio suave · Ejemplo ficticio, no una recomendación",
  ],
  plan: [
    "Tu plan",
    "LA INTENCIÓN ANTES DE LA ACCIÓN",
    "Semana ficticia 04 · Versión de demostración",
  ],
  progreso: [
    "Tu progreso",
    "CONTEXTO ANTES QUE NÚMEROS",
    "Ejemplos ficticios · No se calculan métricas deportivas",
  ],
  entrenador: [
    "Entrenador",
    "TÚ TOMAS LA DECISIÓN",
    "Propuesta escrita para este boceto · Sin modelo ni proveedor IA",
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
  return `<div class="hero"><div><p class="eyebrow">CONSTANCIA, NO PERFECCIÓN</p><h2>Un registro honesto.<br />Una sesión a la vez.</h2><p>Tu plan orienta. Lo realizado cuenta su propia historia.</p></div><div><p class="hero-number">04 <small>/ semana</small></p><p>Base de fuerza · Ficticia</p></div></div>
    <div class="grid"><article class="card"><div class="card-top"><h2>Tu siguiente sesión</h2><span class="badge">Programada · Demo</span></div><p class="eyebrow">FUERZA + CARDIO</p><h3>${escapeHTML(demo.plan)}</h3><p class="muted">Fecha del plan: <strong data-plan-date>${demo.date}</strong></p><div class="session-line"><p><strong>01 / Sentadilla</strong></p><p class="muted">Prescrito: 3 × 8 rep · 40 kg · RPE 7 · RIR 3</p></div><div class="session-line"><p><strong>02 / Cardio suave</strong></p><p class="muted">Duración estimada: 20 min. Los datos medidos aún no existen.</p></div><div class="actions">${buttonLink("entrenamiento", "Comenzar demo", true)}${buttonLink("plan", "Reprogramar")}</div></article><div class="stack"><article class="card"><p class="eyebrow">TU CRITERIO PRIMERO</p><h2>El plan puede esperar.</h2><p class="muted">Revisa una propuesta sin cambiar nada. Solo una aceptación explícita modifica el plan ficticio.</p>${buttonLink("entrenador", "Revisar propuesta IA")}</article><article class="card"><h2>Un dato ausente no es cero</h2><p class="muted">Registramos lo observado. No inventamos frecuencia cardíaca, potencia ni distancia.</p>${buttonLink("progreso", "Explorar progreso")}</article></div></div>`;
}
function numberField(id, label, value, max, step = "1") {
  return `<div class="field"><label for="${id}">${label}</label><input id="${id}" name="${id}" type="number" min="0" max="${max}" step="${step}" value="${value === null ? "" : escapeHTML(value)}" /></div>`;
}
function training() {
  const sets = demo.sets
    .map((set, index) => {
      const n = index + 1;
      return `<fieldset><legend>Sentadilla · Serie ${n}</legend><div class="prescription"><p><strong>Prescrito</strong></p><p>8 rep · 40 kg · RPE 7 / 10 · RIR 3</p></div><div class="actual"><h3>Realizado · Serie ${n}</h3><div class="fields">${numberField(`reps-${n}`, "Repeticiones", set.reps, 100)}${numberField(`load-${n}`, "Carga externa (kg)", set.load, 500, "0.5")}${numberField(`rpe-${n}`, "RPE real (0–10)", set.rpe, 10, "0.5")}${numberField(`rir-${n}`, "RIR real (0–10)", set.rir, 10)}</div></div></fieldset>`;
    })
    .join("");
  return `<article class="card"><div class="card-top"><h2>01 / Fuerza por series</h2><span class="badge">Datos ficticios</span></div><p class="muted" id="set-help">Campos opcionales. Vacío = Sin datos; 0 = cero observado. RPE y RIR se registran por separado, sin conversión ni relleno automático.</p><form id="training-form" aria-describedby="set-help">${sets}<h2>02 / Cardio</h2><div class="prescription"><p><strong>Estimado / prescrito</strong>: 20 min suaves. Distancia estimada: Sin datos.</p></div><h3>Medido / realizado</h3><div class="fields">${numberField("minutes", "Duración medida (min)", demo.cardio.minutes, 600, "0.1")}${numberField("distance", "Distancia medida (km)", demo.cardio.distance, 200, "0.01")}</div><p class="muted">FC, potencia y cadencia: Sin datos. No hay sensores conectados.</p><div class="actions"><button class="primary" id="save-training" type="submit">Conservar en memoria demo</button>${buttonLink("hoy", "Volver a Hoy")}</div></form></article><article class="card" id="record-summary"><h2>Registro en memoria · No enviado</h2>${demo.sets.map((set, index) => `<p>Serie ${index + 1}: ${observed(set.reps, " rep")} · ${observed(set.load, " kg")} · RPE ${observed(set.rpe)} · RIR ${observed(set.rir)}</p>`).join("")}<p>Cardio medido: ${observed(demo.cardio.minutes, " min")} · ${observed(demo.cardio.distance, " km")}</p><p class="muted">Recargar o cerrar borra este registro.</p></article>`;
}
function planning() {
  return `<div class="grid"><article class="card"><p class="eyebrow">MICROCICLO / SEMANA 04</p><h2 data-plan-name>${escapeHTML(demo.plan)}</h2><p>Fecha programada: <strong data-plan-date>${demo.date}</strong></p><p class="muted">La reprogramación de este boceto cambia solo esta fecha en memoria; no altera registros realizados ni historia.</p><form id="reschedule-form"><div class="field"><label for="new-date">Nueva fecha de la sesión ficticia</label><input type="date" id="new-date" name="new-date" min="2026-10-23" max="2027-10-23" value="${demo.date}" required /></div><div class="actions"><button id="reschedule" class="primary" type="submit">Aplicar fecha solo en demo</button>${buttonLink("hoy", "Cancelar y volver")}</div></form></article><article class="card"><h2>Antes de cambiar</h2><p class="muted">En el producto, la revisión de versión evita sobrescribir cambios concurrentes. Explora «Conflicto» para ver la comparación, no una resolución remota real.</p><p>Plan actual: ${demo.accepted ? "propuesta ficticia aceptada en esta pestaña" : "original ficticio, sin cambios de IA"}.</p>${buttonLink("entrenador", "Ver propuesta IA")}</article></div>`;
}
function progress() {
  return `<div class="hero"><div><p class="eyebrow">LECTURA SIN INFERENCIAS</p><h2>Lo que sabes.<br />Y lo que aún no.</h2><p>No comparar deportes ni completar observaciones ausentes.</p></div></div><div class="grid"><article class="card"><h2>Semana de ejemplo · Ficticia</h2><dl class="stats"><div><dt>Sesiones completadas</dt><dd>2</dd></div><div><dt>Sesiones previstas</dt><dd>3</dd></div><div><dt>FC media medida</dt><dd>Sin datos</dd></div></dl><p class="muted">Conteos ilustrativos fijos, independientes del formulario demo. No representan tu adherencia real.</p><div class="progress-row"><span>Sentadilla · Carga externa medida</span><strong>40 kg</strong></div><div class="progress-row"><span>Sentadilla · e1RM estimado</span><strong>Sin datos</strong></div><div class="progress-row"><span>Cardio · Duración estimada</span><strong>20 min</strong></div><div class="progress-row"><span>Cardio · Duración medida</span><strong>Sin datos</strong></div><div class="progress-row"><span>Cardio · Ascenso medido</span><strong>0 m</strong></div><p class="muted">0 m es una observación ficticia de cero. «Sin datos» es ausencia. No hay cálculo de e1RM ni equivalencia entre RPE/RIR.</p></article><article class="card"><h2>Registro de esta pestaña</h2><p>Serie 1 realizada: ${observed(demo.sets[0].reps, " rep")} · ${observed(demo.sets[0].load, " kg")}</p><p>Cardio medido: ${observed(demo.cardio.minutes, " min")}</p><p class="muted">No se combina con el historial fijo de ejemplo.</p>${buttonLink("entrenamiento", "Volver al registro")}</article></div>`;
}
function coach() {
  const status = demo.accepted
    ? "Aceptada solo en memoria"
    : demo.rejected
      ? "Rechazada solo en memoria"
      : "Sin aceptar";
  return `<article class="card"><div class="card-top"><h2>Propuesta IA · Ficticia</h2><span class="badge" id="proposal-status">${status}</span></div><p>Ejemplo editorial para revisar una decisión, no generado por IA. No evalúa tu salud, recuperación ni objetivos.</p><div class="comparison"><div><h3>Plan original ficticio</h3><p>Fuerza A · 3 series × 8 repeticiones</p><p>Cardio estimado: 20 min</p></div><div><h3>Propuesta, aún sin aplicar</h3><p>Fuerza B · 2 series × 8 repeticiones</p><p>Mantener cardio estimado: 20 min</p></div></div><p class="muted">Motivo ficticio: ilustrar una reducción de series. No es una recomendación. Las prescripciones del registro A y las ejecuciones pasadas no cambian.</p><p>Plan vigente en esta pestaña: <strong data-plan-name>${escapeHTML(demo.plan)}</strong></p>${!demo.accepted && !demo.rejected ? `<div class="actions"><button id="accept-proposal" class="primary" type="button">Aceptar cambio en plan demo</button><button id="reject-proposal" type="button">Rechazar propuesta demo</button></div><p class="muted">Aceptar es explícito y solo afecta al próximo plan ficticio, nunca al servidor.</p>` : `<p>No se ha enviado nada. Puedes restaurar el plan original y revisar de nuevo.</p><button id="reset-proposal" type="button">Restaurar plan original demo</button>`}</article><div class="actions">${buttonLink("plan", "Consultar plan vigente")}${buttonLink("hoy", "Volver a Hoy")}</div>`;
}
function renderState() {
  const [title, text] = stateMessages[demo.state];
  const panel = document.querySelector("#state-panel");
  panel.innerHTML =
    demo.state === "normal"
      ? ""
      : `<section class="notice${demo.state === "error" ? " error" : ""}" aria-labelledby="state-title"><h2 id="state-title">${title}</h2><p>${text}</p>${demo.state === "conflict" ? `<div class="comparison"><div><h3>Copia local ficticia</h3><p>Sesión: 2026-10-24 · revisión 1</p></div><div><h3>Copia remota ilustrativa</h3><p>Sesión: 2026-10-25 · revisión 2</p></div></div><p>En el producto: conservar ambas y elegir después de revisar. Aquí no existe una copia remota real.</p>` : ""}${["empty", "error", "conflict"].includes(demo.state) ? `<button id="normal-state" type="button">Volver a Normal (demo)</button>` : ""}</section>`;
  view.hidden = ["empty", "loading"].includes(demo.state);
  view.setAttribute("aria-busy", String(demo.state === "loading"));
  view
    .querySelectorAll("form button, #accept-proposal, #reject-proposal, #reset-proposal")
    .forEach((button) => {
      button.disabled = blocked();
    });
}
function render(moveFocus = false) {
  const current = route();
  const [title, eyebrow, description] = routes[current];
  document.title = `BASIS · ${title} · Demo ficticia`;
  document.querySelector("#page-title").textContent = title;
  document.querySelector("#eyebrow").textContent = eyebrow;
  document.querySelector("#page-description").textContent = description;
  document.querySelectorAll("[data-nav]").forEach((link) => {
    const active = link.dataset.nav === (current === "entrenamiento" ? "hoy" : current);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  view.innerHTML = {
    hoy: today,
    entrenamiento: training,
    plan: planning,
    progreso: progress,
    entrenador: coach,
  }[current]();
  renderState();
  if (moveFocus) {
    main.focus();
    window.scrollTo(0, 0);
  }
}
function rememberForm() {
  const form = document.querySelector("#training-form");
  if (!form) return;
  const read = (id) => {
    const field = document.getElementById(id);
    return field.value === "" ? null : field.valueAsNumber;
  };
  if (!form.checkValidity()) return;
  demo.sets = demo.sets.map((_, index) => ({
    reps: read(`reps-${index + 1}`),
    load: read(`load-${index + 1}`),
    rpe: read(`rpe-${index + 1}`),
    rir: read(`rir-${index + 1}`),
  }));
  demo.cardio = { minutes: read("minutes"), distance: read("distance") };
}
// Keep drafts when navigating or changing the illustrative state, without storage.
view.addEventListener("input", rememberForm);
view.addEventListener("submit", (event) => {
  event.preventDefault();
  if (blocked()) {
    announce("Acción bloqueada en este estado ilustrativo. No se ha cambiado el plan.");
    return;
  }
  if (event.target.id === "training-form") {
    rememberForm();
    render();
    document.querySelector("#save-training").focus();
    announce(
      "Registro ficticio conservado solo en memoria. No enviado ni sincronizado. Recargar lo borra.",
    );
  }
  if (event.target.id === "reschedule-form") {
    demo.date = document.querySelector("#new-date").value;
    render();
    document.querySelector("#reschedule").focus();
    announce(`Fecha ficticia cambiada a ${demo.date} solo en memoria. No enviada al servidor.`);
  }
});
view.addEventListener("click", (event) => {
  const id = event.target.closest("button")?.id;
  if (blocked()) return;
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
