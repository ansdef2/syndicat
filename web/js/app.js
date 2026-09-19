/* ===========================================================================
   Оболочка панели: состояние, маршрутизация, запросы к расчётному API.
   ========================================================================= */
import * as V from "./views.js";
import { nf } from "./format.js";

const state = {
  view: "overview",
  phi: 0.35,
  code: "28",
  ent: "livgidromash",
  sku: "К100-65-200",
  size: "все",
  cls: "",
  cpi: 0.074,
  theta: 0.6,
  zeta: 0.5,
  factors: { energy: 0.12, fx: 0.08, rate: 0, logistics: 0, raw: 0 },
};

const VIEWS = {
  overview: { title: "Обзор сети", sub: "курс ТЧЧ, отраслевые коэффициенты, контур эмиссии" },
  generation: { title: "Генерация ТЧЧ", sub: "количественные и качественные показатели, сравнение" },
  smoothing: { title: "Сглаживание и база часа", sub: "двойное экспоненциальное сглаживание Хольта" },
  pricing: { title: "Ценообразование", sub: "полные трудозатраты, цена производства, рента" },
  channel: { title: "Каналы субститутов", sub: "квантили цен, замещаемость, экстерналии" },
  enterprises: { title: "Реестр предприятий", sub: "средние и крупные субъекты периметра 20-30" },
  indexation: { title: "Индексация заработной платы", sub: "локальный корпоративный контур" },
  model: { title: "Модель и параметры", sub: "шесть слоёв, уставные величины, границы применимости" },
};

const qs = (params) => Object.entries(params)
  .filter(([, v]) => v !== undefined && v !== null && v !== "")
  .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");

const cache = new Map();
async function api(path, params, fresh) {
  const url = `${path}?${qs(params)}`;
  if (!fresh && cache.has(url)) return cache.get(url);
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `ошибка ${res.status}`);
  }
  const data = await res.json();
  cache.set(url, data);
  return data;
}

const mount = () => document.getElementById("view");

const actions = {
  set(patch) { Object.assign(state, patch); render(); syncHash(); },
  go(view, patch = {}) { Object.assign(state, patch, { view }); render(); syncHash(); },
};

function syncHash() {
  const short = { view: state.view, phi: state.phi, ent: state.ent, code: state.code };
  location.hash = qs(short);
}

function readHash() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return;
  const params = new URLSearchParams(raw);
  if (params.get("view") && VIEWS[params.get("view")]) state.view = params.get("view");
  if (params.get("phi")) state.phi = parseFloat(params.get("phi"));
  if (params.get("ent")) state.ent = params.get("ent");
  if (params.get("code")) state.code = params.get("code");
}

async function render() {
  const node = mount();
  const meta = VIEWS[state.view];
  document.getElementById("view-title").textContent = meta.title;
  document.getElementById("view-sub").textContent = meta.sub;
  document.querySelectorAll(".nav button").forEach((b) =>
    b.setAttribute("aria-current", String(b.dataset.view === state.view)));
  document.getElementById("phi-out").value = nf(state.phi, 2);
  document.getElementById("phi").value = state.phi;
  document.getElementById("csv").href = `/api/export/calibration.csv?phi=${state.phi}`;
  node.innerHTML = `<div class="loading">расчёт…</div>`;

  try {
    switch (state.view) {
      case "overview":
        V.overview(node, await api("/api/overview", { phi: state.phi }), state, actions);
        break;
      case "generation":
        V.generation(node, await api("/api/generation", { phi: state.phi }), state, actions);
        break;
      case "smoothing":
        V.smoothing(node, await api("/api/smoothing", { phi: state.phi, code: state.code }), state, actions);
        break;
      case "pricing": {
        const data = await api("/api/pricing",
          { phi: state.phi, ent: state.ent, sku: state.sku, ...state.factors });
        state.sku = data.product.sku;
        V.pricing(node, data, state, actions);
        break;
      }
      case "channel":
        V.channel(node, await api("/api/channel", { phi: state.phi }), state, actions);
        break;
      case "enterprises": {
        const list = await api("/api/enterprises", { phi: state.phi });
        V.enterprises(node, list, state, actions);
        const card = await api("/api/enterprise", { phi: state.phi, id: state.ent, cpi: state.cpi });
        V.enterpriseCard(node.querySelector("#card"), card, actions);
        break;
      }
      case "indexation": {
        const data = await api("/api/indexation",
          { phi: state.phi, ent: state.ent, cpi: state.cpi, theta: state.theta, zeta: state.zeta });
        V.indexation(node, data, state, actions);
        break;
      }
      case "model":
        V.model(node, await api("/api/model", {}), state, actions);
        break;
      default:
        node.innerHTML = `<div class="loading">неизвестный вид</div>`;
    }
  } catch (err) {
    node.innerHTML = `<div class="card span-12"><h3>Расчёт не выполнен</h3>
      <p class="cap">${err.message}</p>
      <p class="note">Проверьте, что сервер запущен: <code>python3 -m syndicat</code>.</p></div>`;
  }
}

function boot() {
  document.querySelectorAll(".nav button").forEach((b) =>
    b.addEventListener("click", () => actions.go(b.dataset.view)));

  const phi = document.getElementById("phi");
  phi.addEventListener("input", (e) => {
    document.getElementById("phi-out").value = nf(parseFloat(e.target.value), 2);
  });
  phi.addEventListener("change", (e) => actions.set({ phi: parseFloat(e.target.value) }));

  window.addEventListener("hashchange", () => { readHash(); render(); });
  readHash();
  render();
}

document.addEventListener("DOMContentLoaded", boot);
