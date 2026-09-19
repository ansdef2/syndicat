/* ===========================================================================
   Диаграммы панели. Чистый SVG, без внешних библиотек.
   Правила: одна ось на диаграмму, легенда при двух и более рядах,
   выборочные прямые подписи, наведение с подсказкой, ненавязчивая сетка.
   ========================================================================= */
import { nf } from "./format.js";

const NS = "http://www.w3.org/2000/svg";
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

export const SERIES = ["var(--ser-2)", "var(--ser-1)", "var(--ser-3)", "var(--luch)"];

function s(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

function frame(host, width, height) {
  host.innerHTML = "";
  host.classList.add("chart");
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, role: "img" });
  host.appendChild(svg);
  const tip = document.createElement("div");
  tip.className = "tip";
  host.appendChild(tip);
  return { svg, tip };
}

function showTip(host, tip, evt, title, rows) {
  const box = host.getBoundingClientRect();
  tip.innerHTML = `<b>${title}</b><dl>${rows
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  tip.style.left = Math.max(70, Math.min(box.width - 70, evt.clientX - box.left)) + "px";
  tip.style.top = (evt.clientY - box.top) + "px";
  tip.classList.add("on");
}
const hideTip = (tip) => tip.classList.remove("on");

export function legend(host, items) {
  const box = document.createElement("div");
  box.className = "legend";
  box.innerHTML = items.map((it) =>
    `<span><i class="${it.line ? "ln" : ""}" style="background:${it.color}"></i>${it.label}</span>`
  ).join("");
  host.appendChild(box);
}

/* --------------------------------------------------------------------------
   Отраслевая розетка: длина луча - коэффициент часа k_j, кольцо - единица.
   Мотив лучевой вспышки логотипа, ставший шкалой.
   ------------------------------------------------------------------------ */
export function rosette(host, rows, onPick) {
  const size = 360, R0 = 36, UNIT = 82;
  const { svg, tip } = frame(host, size, size);
  svg.setAttribute("viewBox", `${-size / 2} ${-size / 2} ${size} ${size}`);
  svg.setAttribute("aria-label", "Отраслевая розетка: коэффициент часа k_j по классам ОКВЭД 20-30");

  svg.appendChild(s("circle", { cx: 0, cy: 0, r: R0 + UNIT, fill: "none",
    stroke: "var(--hair)", "stroke-width": 1, "stroke-dasharray": "3 4" }));

  rows.forEach((d, i) => {
    const ang = (i / rows.length) * 2 * Math.PI - Math.PI / 2;
    const len = R0 + UNIT * d.k;
    const g = s("g", { class: "ray mark-hit", tabindex: "0", role: "button",
      "aria-label": `${d.name}, коэффициент ${nf(d.k, 3)}` });
    const line = s("line", {
      x1: Math.cos(ang) * R0, y1: Math.sin(ang) * R0,
      x2: Math.cos(ang) * len, y2: Math.sin(ang) * len,
      stroke: d.k >= 1 ? "var(--luch)" : "var(--ser-1)",
      "stroke-width": d.k >= 1 ? 9 : 7, opacity: d.k >= 1 ? 0.95 : 0.85,
    });
    const dot = s("circle", { cx: Math.cos(ang) * (len + 9), cy: Math.sin(ang) * (len + 9),
      r: 2.6, fill: "var(--latun)" });
    const lab = s("text", { x: Math.cos(ang) * (len + 26), y: Math.sin(ang) * (len + 26) + 4,
      fill: "var(--latun)", "font-size": 11.5, "text-anchor": "middle",
      "font-family": "Unbounded, sans-serif", "font-weight": 700 }, d.code);
    g.append(line, dot, lab);

    if (!REDUCED) {
      const total = Math.hypot(line.getAttribute("x2") - line.getAttribute("x1"),
                               line.getAttribute("y2") - line.getAttribute("y1"));
      line.style.strokeDasharray = total;
      line.style.strokeDashoffset = total;
      line.style.transition = `stroke-dashoffset .55s cubic-bezier(.2,.8,.2,1) ${i * 40}ms`;
      requestAnimationFrame(() => requestAnimationFrame(() => { line.style.strokeDashoffset = 0; }));
    }

    const show = (evt) => {
      line.setAttribute("stroke-width", 13);
      showTip(host, tip, evt.clientX ? evt : { clientX: host.getBoundingClientRect().left + size / 2,
        clientY: host.getBoundingClientRect().top + 40 }, `${d.code} · ${d.name}`, [
        ["коэффициент k_j", nf(d.k, 3)],
        ["база часа", nf(d.base, 2) + " ₽"],
        ["надбавка μ_j", nf(d.mu, 3)],
        ["доля труда в ВДС", nf(d.labour_share * 100, 0) + "%"],
      ]);
      if (onPick) onPick(d);
    };
    const hide = () => { line.setAttribute("stroke-width", d.k >= 1 ? 9 : 7); hideTip(tip); };
    g.addEventListener("mousemove", show);
    g.addEventListener("mouseleave", hide);
    g.addEventListener("focus", show);
    g.addEventListener("blur", hide);
    g.addEventListener("click", () => onPick && onPick(d, true));
    svg.appendChild(g);
  });

  // ядро: шестерня логотипа
  const core = s("g", { "aria-hidden": "true" });
  for (let i = 0; i < 12; i++) {
    core.appendChild(s("rect", { x: -3.2, y: -R0 - 4, width: 6.4, height: 9,
      fill: "var(--kumach)", transform: `rotate(${(i / 12) * 360})` }));
  }
  core.appendChild(s("circle", { cx: 0, cy: 0, r: R0 - 2, fill: "none",
    stroke: "var(--kumach)", "stroke-width": 7 }));
  core.appendChild(s("circle", { cx: 0, cy: 0, r: 12, fill: "var(--tush)",
    stroke: "var(--kumach-deep)", "stroke-width": 3 }));
  svg.appendChild(core);
}

/* --------------------------------------------------------------------------
   Горизонтальные полосы: величина по одной оси, подпись слева, значение справа.
   ------------------------------------------------------------------------ */
export function barsH(host, opt) {
  const rows = opt.rows, rowH = opt.rowH || 26, padL = opt.padL || 168;
  const W = opt.width || 1000, padR = opt.padR || 96;
  const H = rows.length * rowH + 16;
  const { svg, tip } = frame(host, W, H);
  if (opt.title) svg.setAttribute("aria-label", opt.title);
  const max = opt.max || Math.max(...rows.map((r) => Math.abs(opt.value(r)))) || 1;
  const plot = W - padL - padR;
  if (opt.refValue !== undefined) {
    const rx = padL + (opt.refValue / max) * plot;
    svg.appendChild(s("line", { x1: rx, x2: rx, y1: 2, y2: H - 4, stroke: "var(--latun)",
      "stroke-width": 1, "stroke-dasharray": "4 4" }));
    svg.appendChild(s("text", { x: rx + 6, y: 12, class: "lbl", fill: "var(--latun)",
      "font-size": 10.5 }, opt.refLabel || ""));
  }

  rows.forEach((r, i) => {
    const y = i * rowH + 8, v = opt.value(r);
    const w = Math.max(2, (Math.abs(v) / max) * plot);
    const color = opt.color ? opt.color(r, i) : SERIES[0];
    svg.appendChild(s("text", { x: padL - 12, y: y + 13, "text-anchor": "end",
      class: "lbl", fill: opt.labelColor || "var(--ink-2)" }, opt.label(r)));
    const bar = s("rect", { x: padL, y: y + 3, width: w, height: rowH - 10,
      fill: color, class: "mark-hit" });
    svg.appendChild(bar);
    svg.appendChild(s("text", { x: padL + w + 10, y: y + 13, class: "val",
      fill: opt.valueColor || "var(--grunt)" }, opt.format(v, r)));
    const show = (evt) => showTip(host, tip, evt, opt.tipTitle ? opt.tipTitle(r) : opt.label(r),
      opt.tip ? opt.tip(r) : [[opt.unit || "значение", opt.format(v, r)]]);
    bar.addEventListener("mousemove", show);
    bar.addEventListener("mouseleave", () => hideTip(tip));
  });
  return svg;
}

/* --------------------------------------------------------------------------
   Сгруппированные столбцы: сравнение рядов, приведённых к общей базе.
   Две величины разной природы сравниваются только после индексации
   к общему основанию - двух шкал на одной диаграмме не бывает.
   ------------------------------------------------------------------------ */
export function groupedBars(host, opt) {
  const rows = opt.rows, series = opt.series;
  const W = 1000, H = opt.height || 340, padB = 92, padT = 18, padL = 46, padR = 12;
  const { svg, tip } = frame(host, W, H);
  svg.setAttribute("aria-label", opt.title || "Сравнительная диаграмма");
  const plotH = H - padB - padT, plotW = W - padL - padR;
  const max = opt.max || Math.max(...rows.flatMap((r) => series.map((sr) => sr.value(r)))) * 1.08;
  const y = (v) => padT + plotH - (v / max) * plotH;

  // сетка и ось
  const ticks = opt.ticks || [0, 25, 50, 75, 100, 125, 150].filter((t) => t <= max);
  ticks.forEach((t) => {
    svg.appendChild(s("line", { x1: padL, x2: W - padR, y1: y(t), y2: y(t),
      stroke: "var(--hair-2)", "stroke-width": 1 }));
    svg.appendChild(s("text", { x: padL - 8, y: y(t) + 4, "text-anchor": "end",
      class: "lbl", "font-size": 10.5 }, nf(t, 0)));
  });
  if (opt.refLine !== undefined) {
    svg.appendChild(s("line", { x1: padL, x2: W - padR, y1: y(opt.refLine), y2: y(opt.refLine),
      stroke: "var(--latun)", "stroke-width": 1, "stroke-dasharray": "4 4" }));
    svg.appendChild(s("text", { x: W - padR, y: y(opt.refLine) - 6, "text-anchor": "end",
      class: "lbl", fill: "var(--latun)", "font-size": 10.5 }, opt.refLabel || "сеть = 100"));
  }

  const step = plotW / rows.length;
  const gap = 2, barW = Math.max(4, (step - 14 - gap * (series.length - 1)) / series.length);

  rows.forEach((r, i) => {
    const x0 = padL + i * step + 7;
    series.forEach((sr, j) => {
      const v = sr.value(r), x = x0 + j * (barW + gap);
      const h = Math.max(1, padT + plotH - y(v));
      const rect = s("rect", { x, y: y(v), width: barW, height: h,
        fill: r.focus && sr.focusColor ? sr.focusColor : sr.color, class: "mark-hit" });
      svg.appendChild(rect);
      const show = (evt) => showTip(host, tip, evt, opt.tipTitle(r),
        opt.tip ? opt.tip(r) : series.map((x2) => [x2.label, nf(x2.value(r), 1)]));
      rect.addEventListener("mousemove", show);
      rect.addEventListener("mouseleave", () => hideTip(tip));
    });
    const label = s("text", { x: x0 + (step - 14) / 2, y: padT + plotH + 12,
      "text-anchor": "end", class: "lbl", "font-size": 10.5,
      fill: r.focus ? "var(--luch)" : "var(--ink-2)",
      transform: `rotate(-34 ${x0 + (step - 14) / 2} ${padT + plotH + 12})` }, opt.label(r));
    svg.appendChild(label);
  });
  legend(host, series.map((sr) => ({ color: sr.color, label: sr.label })));
  return svg;
}

/* --------------------------------------------------------------------------
   Линии с коридором: наблюдения, сглаженный уровень, база и её ограничитель.
   ------------------------------------------------------------------------ */
export function lines(host, opt) {
  const W = 1000, H = opt.height || 320, padL = 62, padR = 88, padT = 16, padB = 34;
  const { svg, tip } = frame(host, W, H);
  svg.setAttribute("aria-label", opt.title || "Динамика");
  const pts = opt.points, n = pts.length;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const all = opt.series.flatMap((sr) => pts.map(sr.value))
    .concat(opt.band ? pts.flatMap((p) => [opt.band.low(p), opt.band.high(p)]) : []);
  const min = opt.min !== undefined ? opt.min : Math.min(...all) * 0.97;
  const max = opt.max !== undefined ? opt.max : Math.max(...all) * 1.03;
  const x = (i) => padL + (i / Math.max(1, n - 1)) * plotW;
  const y = (v) => padT + plotH - ((v - min) / (max - min || 1)) * plotH;

  for (let t = 0; t <= 4; t++) {
    const v = min + ((max - min) * t) / 4;
    svg.appendChild(s("line", { x1: padL, x2: W - padR, y1: y(v), y2: y(v),
      stroke: "var(--hair-2)" }));
    svg.appendChild(s("text", { x: padL - 8, y: y(v) + 4, "text-anchor": "end",
      class: "lbl", "font-size": 10.5 }, nf(v, 0)));
  }
  pts.forEach((p, i) => {
    if (i % Math.ceil(n / 12) === 0 || i === n - 1) {
      svg.appendChild(s("text", { x: x(i), y: H - 12, "text-anchor": "middle",
        class: "lbl", "font-size": 10.5 }, opt.xLabel(p, i)));
    }
  });

  if (opt.band) {
    const up = pts.map((p, i) => `${x(i)},${y(opt.band.high(p))}`).join(" ");
    const down = pts.map((p, i) => `${x(i)},${y(opt.band.low(p))}`).reverse().join(" ");
    svg.appendChild(s("polygon", { points: `${up} ${down}`, fill: "var(--latun)",
      opacity: 0.12 }));
  }

  opt.series.forEach((sr) => {
    if (sr.dots) {
      pts.forEach((p, i) => svg.appendChild(s("circle", { cx: x(i), cy: y(sr.value(p)),
        r: 2.6, fill: sr.color, opacity: 0.75 })));
    } else {
      svg.appendChild(s("polyline", { points: pts.map((p, i) => `${x(i)},${y(sr.value(p))}`).join(" "),
        fill: "none", stroke: sr.color, "stroke-width": sr.width || 2,
        "stroke-dasharray": sr.dash || "none" }));
    }
    const last = pts[pts.length - 1];
    svg.appendChild(s("text", { x: W - padR + 8, y: y(sr.value(last)) + 4, class: "val",
      fill: sr.color, "font-size": 11 }, sr.endLabel ? sr.endLabel(last) : nf(sr.value(last), 0)));
  });

  // прицел и подсказка
  const cross = s("line", { x1: 0, x2: 0, y1: padT, y2: padT + plotH,
    stroke: "var(--latun)", "stroke-width": 1, opacity: 0 });
  svg.appendChild(cross);
  const hit = s("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent" });
  svg.appendChild(hit);
  hit.addEventListener("mousemove", (evt) => {
    const box = svg.getBoundingClientRect();
    const rel = ((evt.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(((rel - padL) / plotW) * (n - 1))));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i));
    cross.setAttribute("opacity", 0.6);
    showTip(host, tip, evt, opt.tipTitle(pts[i], i),
      opt.series.map((sr) => [sr.label, sr.format ? sr.format(sr.value(pts[i])) : nf(sr.value(pts[i]), 1)]));
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); hideTip(tip); });
  legend(host, opt.series.map((sr) => ({ color: sr.color, label: sr.label, line: !sr.dots })));
  return svg;
}

/* --------------------------------------------------------------------------
   Каскад: как складывается цена производства и чем она отличается от рыночной.
   ------------------------------------------------------------------------ */
export function waterfall(host, opt) {
  const items = opt.items, W = 1000, H = opt.height || 280, padT = 24, padB = 56, padL = 20;
  const { svg, tip } = frame(host, W, H);
  svg.setAttribute("aria-label", opt.title || "Формирование цены");
  const plotH = H - padT - padB, colW = (W - padL * 2) / items.length - 18;
  const max = Math.max(...items.map((i) => i.total !== undefined ? i.total : i.value)) * 1.12;
  const y = (v) => padT + plotH - (v / max) * plotH;

  let running = 0;
  items.forEach((it, i) => {
    const x = padL + i * ((W - padL * 2) / items.length) + 9;
    const isTotal = it.kind === "total" || it.kind === "market";
    const from = isTotal ? 0 : running;
    const to = isTotal ? it.value : running + it.value;
    if (!isTotal) running = to;
    const top = y(Math.max(from, to)), h = Math.max(2, Math.abs(y(from) - y(to)));
    const color = it.kind === "labour" ? "var(--ser-2)"
      : it.kind === "external" ? "var(--ser-1)"
      : it.kind === "market" ? "var(--patina)" : "var(--luch)";
    const rect = s("rect", { x, y: top, width: colW, height: h, fill: color, class: "mark-hit",
      opacity: it.kind === "market" ? 0.9 : 1 });
    svg.appendChild(rect);
    svg.appendChild(s("text", { x: x + colW / 2, y: top - 8, "text-anchor": "middle",
      class: "val", "font-size": 12 }, opt.format(it.value)));
    const words = it.label.split(" ");
    words.forEach((w, k) => svg.appendChild(s("text", { x: x + colW / 2,
      y: padT + plotH + 18 + k * 13, "text-anchor": "middle", class: "lbl",
      "font-size": 11 }, w)));
    if (i < items.length - 1 && !isTotal) {
      svg.appendChild(s("line", { x1: x + colW, x2: x + (W - padL * 2) / items.length,
        y1: y(to), y2: y(to), stroke: "var(--hair)", "stroke-dasharray": "3 3" }));
    }
    rect.addEventListener("mousemove", (evt) => showTip(host, tip, evt, it.label,
      it.tip || [["величина", opt.format(it.value)]]));
    rect.addEventListener("mouseleave", () => hideTip(tip));
  });
  return svg;
}

/* --------------------------------------------------------------------------
   Двусторонние полосы: доля труда влево, доля капитала вправо от оси.
   ------------------------------------------------------------------------ */
export function splitBars(host, opt) {
  const rows = opt.rows, rowH = 22, W = 1000, H = rows.length * rowH + 14;
  const { svg, tip } = frame(host, W, H);
  svg.setAttribute("aria-label", opt.title || "Труд и капитал в добавленной стоимости");
  const mid = W / 2, half = mid - 96;
  rows.forEach((r, i) => {
    const y0 = i * rowH + 8;
    const l = opt.left(r), c = opt.right(r);
    svg.appendChild(s("text", { x: mid - half - 12, y: y0 + 12, "text-anchor": "end", class: "lbl",
      "font-family": "Unbounded, sans-serif", "font-size": 11, fill: "var(--latun)" }, r.code));
    svg.appendChild(s("rect", { x: mid - 2 - l * half, y: y0 + 3, width: l * half,
      height: rowH - 9, fill: "var(--ser-2)", class: "mark-hit" }));
    svg.appendChild(s("rect", { x: mid + 2, y: y0 + 3, width: c * half, height: rowH - 9,
      fill: "var(--ser-1)", class: "mark-hit" }));
    svg.appendChild(s("text", { x: W - 16, y: y0 + 12, "text-anchor": "end", class: "val",
      "font-size": 11 }, `${nf(l * 100, 0)} / ${nf(c * 100, 0)}`));
    const hit = s("rect", { x: 0, y: y0, width: W, height: rowH, fill: "transparent",
      class: "mark-hit" });
    svg.appendChild(hit);
    hit.addEventListener("mousemove", (evt) => showTip(host, tip, evt, `${r.code} · ${r.short}`,
      [["доля труда", nf(l * 100, 0) + "%"], ["доля капитала", nf(c * 100, 0) + "%"],
       ["амортизация", nf((1 - l - c) * 100, 0) + "%"]]));
    hit.addEventListener("mouseleave", () => hideTip(tip));
  });
  svg.appendChild(s("line", { x1: mid, x2: mid, y1: 4, y2: H - 4, stroke: "var(--hair)" }));
  legend(host, [{ color: "var(--ser-2)", label: "доля оплаты труда в ВДС" },
                { color: "var(--ser-1)", label: "доля прибавочного продукта" }]);
  return svg;
}

/* --------------------------------------------------------------------------
   Поле рассеяния: количественный показатель против качественного.
   ------------------------------------------------------------------------ */
export function scatter(host, opt) {
  const W = 1000, H = opt.height || 420, padL = 58, padR = 24, padT = 18, padB = 46;
  const { svg, tip } = frame(host, W, H);
  svg.setAttribute("aria-label", opt.title || "Поле рассеяния");
  const rows = opt.rows, plotW = W - padL - padR, plotH = H - padT - padB;
  const xs = rows.map(opt.x), ys = rows.map(opt.y);
  const xMin = Math.min(...xs) * 0.96, xMax = Math.max(...xs) * 1.04;
  const yMin = Math.min(...ys) * 0.96, yMax = Math.max(...ys) * 1.04;
  const X = (v) => padL + ((v - xMin) / (xMax - xMin)) * plotW;
  const Y = (v) => padT + plotH - ((v - yMin) / (yMax - yMin)) * plotH;
  const rMax = Math.max(...rows.map(opt.r));

  [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
    const vx = xMin + (xMax - xMin) * t, vy = yMin + (yMax - yMin) * t;
    svg.appendChild(s("line", { x1: X(vx), x2: X(vx), y1: padT, y2: padT + plotH, stroke: "var(--hair-2)" }));
    svg.appendChild(s("line", { x1: padL, x2: W - padR, y1: Y(vy), y2: Y(vy), stroke: "var(--hair-2)" }));
    svg.appendChild(s("text", { x: X(vx), y: H - 22, "text-anchor": "middle", class: "lbl",
      "font-size": 10.5 }, nf(vx, 0)));
    svg.appendChild(s("text", { x: padL - 8, y: Y(vy) + 4, "text-anchor": "end", class: "lbl",
      "font-size": 10.5 }, nf(vy, 0)));
  });
  if (opt.refX !== undefined) svg.appendChild(s("line", { x1: X(opt.refX), x2: X(opt.refX),
    y1: padT, y2: padT + plotH, stroke: "var(--latun)", "stroke-dasharray": "4 4" }));
  if (opt.refY !== undefined) svg.appendChild(s("line", { x1: padL, x2: W - padR,
    y1: Y(opt.refY), y2: Y(opt.refY), stroke: "var(--latun)", "stroke-dasharray": "4 4" }));

  const labelled = new Set([...rows].sort((a, b) =>
    Math.abs(opt.x(b) - 100) - Math.abs(opt.x(a) - 100)).slice(0, 8).map(opt.label));
  rows.forEach((r) => {
    const rad = 6 + 16 * Math.sqrt(opt.r(r) / rMax);
    const dot = s("circle", { cx: X(opt.x(r)), cy: Y(opt.y(r)), r: rad,
      fill: r.focus ? "var(--luch)" : "var(--ser-1)", opacity: 0.78,
      stroke: "var(--tush)", "stroke-width": 2, class: "mark-hit" });
    svg.appendChild(dot);
    if (r.focus || labelled.has(opt.label(r))) {
      svg.appendChild(s("text", { x: X(opt.x(r)), y: Y(opt.y(r)) - rad - 6, "text-anchor": "middle",
        class: "lbl", "font-size": 10.5, fill: r.focus ? "var(--luch)" : "var(--ink-2)" },
        opt.label(r)));
    }
    dot.addEventListener("mousemove", (evt) => showTip(host, tip, evt, opt.tipTitle(r), opt.tip(r)));
    dot.addEventListener("mouseleave", () => hideTip(tip));
  });
  svg.appendChild(s("text", { x: W - padR, y: H - 6, "text-anchor": "end", class: "lbl",
    fill: "var(--latun)", "font-size": 11 }, opt.xTitle));
  svg.appendChild(s("text", { x: padL + 6, y: padT + 12, class: "lbl",
    fill: "var(--latun)", "font-size": 11 }, opt.yTitle));
  return svg;
}

/* Полоса-мера: значение в коридоре (индекс токен-цен). */
export function meter(host, opt) {
  const W = 1000, H = 92;
  const { svg } = frame(host, W, H);
  svg.setAttribute("aria-label", opt.title || "Коридор");
  const padL = 20, plotW = W - 40;
  const X = (v) => padL + ((v - opt.min) / (opt.max - opt.min)) * plotW;
  svg.appendChild(s("rect", { x: padL, y: 34, width: plotW, height: 14, fill: "var(--tush-3)" }));
  svg.appendChild(s("rect", { x: X(opt.low), y: 34, width: X(opt.high) - X(opt.low), height: 14,
    fill: "var(--ser-3)", opacity: 0.35 }));
  svg.appendChild(s("line", { x1: X(opt.target), x2: X(opt.target), y1: 28, y2: 54,
    stroke: "var(--latun)", "stroke-width": 1, "stroke-dasharray": "3 3" }));
  svg.appendChild(s("rect", { x: X(opt.value) - 2, y: 24, width: 4, height: 34,
    fill: opt.inside ? "var(--luch)" : "var(--ser-1)" }));
  svg.appendChild(s("text", { x: X(opt.value), y: 18, "text-anchor": "middle", class: "val",
    fill: opt.inside ? "var(--luch)" : "var(--ser-1)", "font-size": 13 }, nf(opt.value, 4)));
  [opt.min, opt.low, opt.target, opt.high, opt.max].forEach((v) =>
    svg.appendChild(s("text", { x: X(v), y: 72, "text-anchor": "middle", class: "lbl",
      "font-size": 10.5 }, nf(v, 3))));
  return svg;
}
