/* ===========================================================================
   Представления панели. Каждая функция получает данные API и монтирует
   разметку в контейнер вида.
   ========================================================================= */
import * as C from "./charts.js";
import { compact, nf, pct, pct0, rub } from "./format.js";

const q = (root, sel) => root.querySelector(sel);
const tile = (value, label, sub, hi) =>
  `<div class="tile"><b class="num${hi ? " hi" : ""}">${value}</b><i>${label}</i>${
    sub ? `<s>${sub}</s>` : ""}</div>`;

/* ------------------------------------------------------------------ обзор */
export function overview(root, d, state, actions) {
  const ti = d.token_index;
  root.innerHTML = `
    <div class="grid">
      <section class="card span-12">
        <div class="hero">
          <div>
            <p class="rate-label">Курс токена человеко-часа</p>
            <div class="rate num">${nf(d.B, 2)} <small>руб. / ТЧЧ</small></div>
            <p class="rate-sub">Один человеко-час первого разряда при среднем по сети
              отраслевом коэффициенте. Из них ${nf(d.labour_part, 0)} руб. - оплата труда
              с начислениями, ${nf(d.social_part, 0)} руб. - социализированная доля
              прибавочного продукта при φ = ${nf(d.phi, 2)}.</p>
            <div class="tiles" style="margin-top:22px">
              ${tile(nf(ti.index, 4), "индекс токен-цен", `коридор ±${pct0(ti.corridor, 0)}`, ti.in_corridor)}
              ${tile(nf(d.phi, 2), "норма социализации φ", "уставной параметр")}
              ${tile(pct(ti.step_month, 2), "шаг базы за месяц", "предел ±2%")}
              ${tile(nf(d.enterprises, 0), "предприятий в периметре",
                     `${d.enterprises_large} крупных · ${d.enterprises_medium} средних`)}
              ${tile(compact(d.headcount), "занятых", "производственный и прочий персонал")}
              ${tile(compact(d.tokens_month), "ТЧЧ эмиссии в месяц", compact(d.tokens_rub_month, " ₽"))}
            </div>
          </div>
          <div>
            <div class="chart" id="rose"></div>
            <p class="note" id="rose-read" aria-live="polite" style="margin-top:12px">
              Наведите или перейдите табуляцией на луч: длина луча - коэффициент часа k<sub>j</sub>,
              пунктирное кольцо - единица.</p>
          </div>
        </div>
      </section>

      <section class="card span-7">
        <h3>База часа по классам ОКВЭД</h3>
        <p class="cap">b<sub>j</sub> = w<sub>j</sub> + φ·ŝ<sub>j</sub>. Светлая заливка -
          класс с коэффициентом часа выше единицы.</p>
        <div class="chart" id="bases"></div>
      </section>

      <section class="card span-5">
        <h3>Индекс токен-цен в коридоре</h3>
        <p class="cap">Правило эмиссии: ΔM<sub>ТЧЧ</sub> ≤ ΔQ<sub>нормо-часов</sub>·(1 + ρ),
          ρ = 1,5% годовых. Выход за коридор временно снижает φ.</p>
        <div class="chart" id="meter"></div>
        <div class="tiles" style="margin-top:14px">
          ${tile(compact(d.hours_month), "человеко-часов в месяц", "фонд времени сети")}
          ${tile(nf(d.tokens_per_hour, 3), "ТЧЧ на человеко-час", "с учётом сложности и цикла")}
          ${tile(compact(d.emission_growth_cap), "допустимый прирост массы", "ТЧЧ в месяц при неизменном выпуске")}
          ${tile(nf(ti.phi_next, 3), "φ на следующий шаг", ti.in_corridor ? "коридор соблюдён" : "сработала обратная связь", !ti.in_corridor)}
        </div>
      </section>

      <section class="card span-6">
        <h3>Труд и капитал в добавленной стоимости</h3>
        <p class="cap">Влево - доля оплаты труда, вправо - доля прибавочного продукта.
          Остаток до единицы - потребление основного капитала. Показатель Пикетти
          публикуется по каждому классу.</p>
        <div class="chart" id="split"></div>
      </section>

      <section class="card span-6">
        <h3>Глубина цепочки: прямые и полные трудозатраты</h3>
        <p class="cap">Множитель цепочки - во сколько раз полные трудозатраты превышают
          прямые. Чем глубже цепочка, тем больше чужого труда упаковано в изделие.</p>
        <div class="chart" id="mult"></div>
      </section>

      <section class="card span-12">
        <h3>Периметр: 11 классов ОКВЭД 20-30</h3>
        <p class="cap">Якорь калибровки: ${nf(d.anchor_wage, 1)} руб./мес. <b>${d.anchor_note}</b>.</p>
        <div class="scroll"><table class="tbl" id="ind-table"></table></div>
      </section>
    </div>`;

  C.rosette(q(root, "#rose"), d.industries, (row) => {
    q(root, "#rose-read").innerHTML =
      `<b>${row.code} · ${row.name}</b> — коэффициент часа k = ${nf(row.k, 3)},
       база ${nf(row.base, 2)} руб./ч, надбавка μ = ${nf(row.mu, 3)},
       доля труда в ВДС ${pct0(row.labour_share, 0)}.`;
  });

  C.barsH(q(root, "#bases"), {
    rows: [...d.industries].sort((a, b) => b.base - a.base),
    label: (r) => `${r.code} ${r.short}`,
    value: (r) => r.base,
    color: (r) => (r.k >= 1 ? "var(--luch)" : "var(--ser-2)"),
    format: (v) => nf(v, 0) + " ₽",
    tipTitle: (r) => `${r.code} · ${r.name}`,
    tip: (r) => [["база часа", nf(r.base, 2) + " ₽"], ["коэффициент k_j", nf(r.k, 3)],
      ["оплата труда", nf(r.w_hour, 0) + " ₽"], ["надбавка μ_j", nf(r.mu, 3)]],
  });
  C.legend(q(root, "#bases"), [
    { color: "var(--luch)", label: "k_j ≥ 1 - час дороже сетевой единицы" },
    { color: "var(--ser-2)", label: "k_j < 1" }]);

  C.meter(q(root, "#meter"), {
    value: ti.index, target: ti.target, low: ti.target - ti.corridor,
    high: ti.target + ti.corridor, min: 0.95, max: 1.05, inside: ti.in_corridor,
    title: "Индекс токен-цен",
  });

  C.splitBars(q(root, "#split"), {
    rows: d.industries, left: (r) => r.labour_share, right: (r) => r.capital_share,
  });

  C.barsH(q(root, "#mult"), {
    rows: [...d.industries].sort((a, b) => b.multiplier - a.multiplier),
    label: (r) => `${r.code} ${r.short}`,
    value: (r) => r.multiplier,
    color: () => "var(--ser-3)",
    format: (v) => "×" + nf(v, 2),
    tipTitle: (r) => `${r.code} · ${r.name}`,
    tip: (r) => [["прямые, ч/1000 ₽", nf(r.l_direct, 3)], ["полные, ч/1000 ₽", nf(r.h_full, 3)],
      ["множитель", "×" + nf(r.multiplier, 3)], ["вне периметра, ₽/₽", nf(r.external, 3)]],
  });

  table(q(root, "#ind-table"), d.industries, [
    { k: "code", t: "ОКВЭД", f: (r) => `<span class="name" title="${r.name}">${r.code} · ${r.short}</span>` },
    { k: "w_hour", t: "Труд, ₽/ч", f: (r) => nf(r.w_hour, 0) },
    { k: "vds_hour", t: "ВДС, ₽/ч", f: (r) => nf(r.vds_hour, 0) },
    { k: "s_smooth", t: "Приб. продукт (сглаж.), ₽/ч", f: (r) => nf(r.s_smooth, 0) },
    { k: "base", t: "База b_j, ₽", f: (r) => `<b>${nf(r.base, 2)}</b>` },
    { k: "k", t: "k_j", f: (r) => nf(r.k, 3) },
    { k: "mu", t: "μ_j", f: (r) => nf(r.mu, 3) },
    { k: "l_direct", t: "Прямые, ч/1000 ₽", f: (r) => nf(r.l_direct, 3) },
    { k: "h_full", t: "Полные, ч/1000 ₽", f: (r) => nf(r.h_full, 3) },
    { k: "multiplier", t: "Множитель", f: (r) => "×" + nf(r.multiplier, 2) },
    { k: "cycle_days", t: "Цикл, дн.", f: (r) => nf(r.cycle_days, 0) },
    { k: "k_cycle", t: "K_цикл", f: (r) => nf(r.k_cycle, 3) },
    { k: "external", t: "Вне периметра, ₽/₽", f: (r) => nf(r.external, 3) },
  ], "base");
}

/* ------------------------------------------------- сортируемая таблица */
export function table(node, rows, cols, sortKey, focusFn) {
  let key = sortKey || cols[0].k, dir = -1;
  const draw = () => {
    const sorted = [...rows].sort((a, b) => {
      const va = a[key], vb = b[key];
      return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * dir;
    });
    node.innerHTML = `<thead><tr>${cols.map((c) =>
      `<th data-k="${c.k}" ${c.k === key ? `data-sort="${dir > 0 ? "asc" : "desc"}"` : ""}
        title="сортировать">${c.t}</th>`).join("")}</tr></thead>
      <tbody>${sorted.map((r) => `<tr${focusFn && focusFn(r) ? ' class="focus"' : ""}
        data-id="${r.id || r.code || ""}">${cols.map((c) => `<td>${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    node.querySelectorAll("th").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.k;
      if (k === key) dir = -dir; else { key = k; dir = -1; }
      draw();
    }));
  };
  draw();
  return node;
}

/* ------------------------------------------------------------ генерация */
export function generation(root, d, state, actions) {
  const sizes = ["все", "крупное", "среднее"];
  root.innerHTML = `
    <div class="filters">
      <div class="f"><span>категория предприятия</span>
        <div class="chips" style="margin:0">${sizes.map((s2) =>
          `<button class="chip" data-size="${s2}" aria-pressed="${state.size === s2}">${s2}</button>`).join("")}</div>
      </div>
      <div class="f"><span>класс ОКВЭД</span>
        <select id="cls"><option value="">все классы</option>
          ${[...new Set(d.rows.map((r) => r.cls))].sort().map((c) =>
            `<option value="${c}" ${state.cls === c ? "selected" : ""}>${c} · ${
              d.rows.find((r) => r.cls === c).industry_short}</option>`).join("")}</select>
      </div>
    </div>
    <div class="grid">
      <section class="card span-12">
        <div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap">
          <span class="tag"><em>сравнительная диаграмма</em></span>
          <h3>Количественные и качественные показатели генерации ТЧЧ</h3>
        </div>
        <p class="cap">Количественный показатель - интенсивность эмиссии, ТЧЧ на отработанный
          человеко-час. Качественный - композит: качество сдачи ${pct0(d.weights.quality, 0)},
          OEE ${pct0(d.weights.oee, 0)}, средний разряд ${pct0(d.weights.grade, 0)},
          длительность цикла ${pct0(d.weights.cycle, 0)}, локализация ${pct0(d.weights.localization, 0)}.
          Оба показателя приведены к общей базе «сеть = 100»: величины разной природы
          сравниваются только после индексации, а не на двух шкалах одной диаграммы.</p>
        <div class="chart" id="cmp"></div>
      </section>

      <section class="card span-7">
        <h3>Разрыв количественного и качественного индекса</h3>
        <p class="cap">По горизонтали - количественный индекс, по вертикали - качественный,
          площадь круга - численность персонала. Правый нижний угол: эмиссия обгоняет
          качество - зона, где нормы требуют пересмотра.</p>
        <div class="chart" id="scatter"></div>
      </section>

      <section class="card span-5">
        <h3>Масса эмиссии по предприятиям</h3>
        <p class="cap">Тысяч ТЧЧ в месяц. Масса пропорциональна фонду времени
          и отраслевому коэффициенту, а не выручке.</p>
        <div class="chart" id="mass"></div>
      </section>

      <section class="card span-12">
        <h3>Свод показателей генерации</h3>
        <p class="cap">Строка - предприятие. Сортировка по любому столбцу.</p>
        <div class="scroll"><table class="tbl" id="gen-table"></table></div>
      </section>
    </div>`;

  root.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click",
    () => actions.set({ size: chip.dataset.size })));
  q(root, "#cls").addEventListener("change", (e) => actions.set({ cls: e.target.value }));

  const rows = d.rows.filter((r) =>
    (state.size === "все" || !state.size || r.size === state.size) &&
    (!state.cls || r.cls === state.cls));

  C.groupedBars(q(root, "#cmp"), {
    rows, height: 360, refLine: 100, refLabel: "сеть = 100",
    label: (r) => r.short,
    series: [
      { label: "количественный индекс (ТЧЧ на чел.-час)", color: "var(--ser-2)", focusColor: "var(--luch)",
        value: (r) => r.quantitative },
      { label: "качественный индекс (композит)", color: "var(--ser-1)",
        value: (r) => r.qualitative },
    ],
    tipTitle: (r) => r.name,
    tip: (r) => [["класс ОКВЭД", r.okved], ["категория", r.size],
      ["количественный", nf(r.quantitative, 1)], ["качественный", nf(r.qualitative, 1)],
      ["разрыв", nf(r.gap, 1) + " п."], ["ТЧЧ на чел.-час", nf(r.tokens_per_hour, 3)],
      ["качество q", nf(r.quality, 3)], ["OEE", nf(r.oee, 2)]],
  });

  C.scatter(q(root, "#scatter"), {
    rows, height: 400, x: (r) => r.quantitative, y: (r) => r.qualitative,
    r: (r) => r.headcount, refX: 100, refY: 100,
    label: (r) => r.short, xTitle: "количественный индекс",
    yTitle: "качественный индекс",
    tipTitle: (r) => r.name,
    tip: (r) => [["численность", nf(r.headcount, 0)], ["ТЧЧ на чел.-час", nf(r.tokens_per_hour, 3)],
      ["качество", nf(r.quality, 3)], ["OEE", nf(r.oee, 2)],
      ["локализация", nf(r.localization, 2)], ["средний разряд", nf(r.avg_grade, 1)]],
  });

  C.barsH(q(root, "#mass"), {
    rows: [...rows].sort((a, b) => b.tokens_month - a.tokens_month).slice(0, 12),
    width: 620, padL: 210, padR: 70, label: (r) => r.short, value: (r) => r.tokens_month / 1000,
    rowH: 30, color: (r) => (r.focus ? "var(--luch)" : "var(--ser-2)"),
    format: (v) => nf(v, 0),
    tipTitle: (r) => r.name,
    tip: (r) => [["ТЧЧ в месяц", nf(r.tokens_month, 0)], ["в рублях", compact(r.tokens_rub, " ₽")],
      ["часов в месяц", nf(r.hours_month, 0)], ["ТЧЧ на работника", nf(r.tokens_per_worker, 1)]],
  });

  table(q(root, "#gen-table"), rows, [
    { k: "name", t: "Предприятие", f: (r) => `<span class="name">${r.name}<i>${r.okved} · ${r.industry_short} · ${r.size}</i></span>` },
    { k: "headcount", t: "Численность", f: (r) => nf(r.headcount, 0) },
    { k: "hours_month", t: "Чел.-ч/мес", f: (r) => compact(r.hours_month) },
    { k: "tokens_month", t: "ТЧЧ/мес", f: (r) => compact(r.tokens_month) },
    { k: "tokens_per_hour", t: "ТЧЧ на чел.-ч", f: (r) => nf(r.tokens_per_hour, 3) },
    { k: "tokens_per_worker", t: "ТЧЧ на работника", f: (r) => nf(r.tokens_per_worker, 1) },
    { k: "quantitative", t: "Количественный", f: (r) => `<b>${nf(r.quantitative, 1)}</b>` },
    { k: "qualitative", t: "Качественный", f: (r) => `<b>${nf(r.qualitative, 1)}</b>` },
    { k: "gap", t: "Разрыв", f: (r) => `<span class="${r.gap >= 0 ? "pos" : "neg"}">${nf(r.gap, 1)}</span>` },
    { k: "quality", t: "Качество q", f: (r) => nf(r.quality, 3) },
    { k: "oee", t: "OEE", f: (r) => nf(r.oee, 2) },
    { k: "avg_grade", t: "Средний разряд", f: (r) => nf(r.avg_grade, 1) },
    { k: "localization", t: "Локализация", f: (r) => nf(r.localization, 2) },
  ], "quantitative", (r) => r.focus);
}

/* --------------------------------------------------------- сглаживание */
export function smoothing(root, d, state, actions) {
  root.innerHTML = `
    <div class="filters">
      <div class="f"><span>класс ОКВЭД</span>
        <select id="code">${d.codes.map((c) =>
          `<option value="${c.code}" ${c.code === d.code ? "selected" : ""}>${c.code} · ${c.short}</option>`).join("")}</select>
      </div>
    </div>
    <div class="grid">
      <section class="card span-12">
        <div class="tiles">
          ${tile(nf(d.alpha, 4), "α - сглаживание уровня", `полупериод ${nf(d.alpha_halflife, 0)} мес`)}
          ${tile(nf(d.beta, 4), "β - сглаживание тренда", `полупериод ${nf(d.beta_halflife, 0)} мес`)}
          ${tile(nf(d.s_raw, 1), "прибавочный продукт, ₽/ч", "текущее наблюдение")}
          ${tile(nf(d.s_smooth, 1), "сглаженный ŝ_j, ₽/ч", "прогноз на шаг вперёд", true)}
          ${tile(nf(d.base, 2), "база часа b_j, ₽", `k_j = ${nf(d.k, 3)}`, true)}
          ${tile(nf(d.clipped_months, 0), "срабатываний ограничителя", `предел ±${pct0(d.max_step, 0)} в месяц`)}
        </div>
      </section>

      <section class="card span-7">
        <h3>Удельный прибавочный продукт и его сглаживание</h3>
        <p class="cap">Точки - наблюдения s<sub>j</sub>(t) = [V − W − D] / H. Линия - уровень
          Хольта L(t), пунктир - прогноз L(t) + T(t). Шок отрабатывается базой наполовину
          за полгода: быстрая реакция означала бы, что при скачке цен на сырьё рабочий
          немедленно получает меньше часов за ту же работу.</p>
        <div class="chart" id="holt"></div>
        <div class="formula">L(t) = α·s(t) + (1 − α)·[L(t−1) + T(t−1)]
T(t) = β·[L(t) − L(t−1)] + (1 − β)·T(t−1)
ŝ(t+1) = L(t) + T(t),   α = 1 − 2^(−1/6) = ${nf(d.alpha, 4)},  β = 1 − 2^(−1/12) = ${nf(d.beta, 4)}</div>
      </section>

      <section class="card span-5">
        <h3>База часа и коридор ±2%</h3>
        <p class="cap">Заливка - допустимый коридор месячного шага относительно
          предыдущего значения. Правило опубликовано заранее, поэтому ожидания
          не разгоняются даже при внешнем шоке.</p>
        <div class="chart" id="base"></div>
        <p class="note">b<sub>j</sub>(t) = w<sub>j</sub>(t) + φ·ŝ<sub>j</sub>(t) при
          φ = ${nf(d.phi, 2)}; оплата труда в демонстрационном ряде растёт с постоянным
          дрейфом и приходит к текущему значению ${nf(d.w_hour, 0)} ₽/ч в последнем месяце.</p>
      </section>
    </div>`;

  q(root, "#code").addEventListener("change", (e) => actions.set({ code: e.target.value }));

  C.lines(q(root, "#holt"), {
    points: d.path, height: 330,
    xLabel: (p) => `M${p.month + 1}`,
    tipTitle: (p) => `месяц ${p.month + 1}`,
    series: [
      { label: "наблюдения s_j(t)", color: "var(--ser-1)", dots: true, value: (p) => p.observation,
        format: (v) => nf(v, 1) + " ₽/ч", endLabel: (p) => nf(p.observation, 0) },
      { label: "уровень L(t)", color: "var(--ser-2)", value: (p) => p.level,
        format: (v) => nf(v, 1) + " ₽/ч", endLabel: (p) => nf(p.level, 0) },
      { label: "прогноз L(t) + T(t)", color: "var(--luch)", dash: "6 4", value: (p) => p.forecast,
        format: (v) => nf(v, 1) + " ₽/ч", endLabel: (p) => nf(p.forecast, 0) },
    ],
  });

  C.lines(q(root, "#base"), {
    points: d.path, height: 330,
    xLabel: (p) => `M${p.month + 1}`,
    tipTitle: (p) => `месяц ${p.month + 1}`,
    band: { low: (p) => p.corridor_low, high: (p) => p.corridor_high },
    series: [
      { label: "база часа b_j(t)", color: "var(--luch)", value: (p) => p.base,
        format: (v) => nf(v, 2) + " ₽", endLabel: (p) => nf(p.base, 0) },
      { label: "оплата труда w_j(t)", color: "var(--ser-2)", dash: "5 4", value: (p) => p.wage_hour,
        format: (v) => nf(v, 2) + " ₽", endLabel: (p) => nf(p.wage_hour, 0) },
    ],
  });
}

/* ------------------------------------------------------ ценообразование */
export function pricing(root, d, state, actions) {
  const p = d.price, sc = p.shock;
  const factors = [
    ["energy", "Энергия"], ["fx", "Курс"], ["rate", "Ключевая ставка"],
    ["logistics", "Логистика"], ["raw", "Сырьё"],
  ];
  root.innerHTML = `
    <div class="filters">
      <div class="f"><span>предприятие и изделие</span>
        <select id="sku">${d.catalogue.map((c) =>
          `<option value="${c.ent_id}|${c.sku}" ${
            c.ent_id === d.enterprise.id && c.sku === d.product.sku ? "selected" : ""}>
            ${c.ent_name.replace(/^[А-Я]+ /, "")} — ${c.name}</option>`).join("")}</select>
      </div>
      ${factors.map(([k, label]) => `
        <div class="f"><span>${label}</span>
          <input type="number" step="1" id="f-${k}" value="${Math.round((state.factors[k] || 0) * 100)}"
                 style="width:92px" aria-label="${label}, процент изменения"> </div>`).join("")}
      <div class="f"><span>&nbsp;</span><button class="btn ghost" id="reset">сбросить сценарий</button></div>
    </div>
    <div class="grid">
      <section class="card span-12">
        <div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap">
          <span class="tag"><em>ОКВЭД ${d.enterprise.okved}</em></span>
          <h3>${d.product.name}</h3>
          <span class="note">${d.enterprise.name} · ${d.enterprise.city} · ${d.enterprise.size} предприятие</span>
        </div>
        <div class="tiles" style="margin-top:16px">
          ${tile(nf(d.tokens_per_unit, 2), "ТЧЧ на изделие", `${nf(d.tokens_rub_per_unit, 0)} ₽ по курсу`, true)}
          ${tile(nf(p.full_hours, 2), "полных чел.-ч", `прямых ${nf(p.direct_hours, 2)} · ×${nf(p.chain_multiplier, 2)}`)}
          ${tile(nf(p.labour_rub, 0), "трудовая часть, ₽", pct0(d.labour_share_price, 0) + " цены")}
          ${tile(nf(p.external_rub, 0), "внешний контур, ₽", pct0(d.external_share_price, 0) + " цены")}
          ${tile(nf(p.production_price, 0), "цена производства, ₽", `рыночная ${nf(p.market_price, 0)} ₽`, true)}
          ${tile(pct(p.rent, 1), "индикатор ренты", p.rent > 0 ? "рынок выше цены производства" : "рынок ниже цены производства")}
          ${sc ? tile(pct(sc.percent / 100, 2), "реакция на сценарий", `цена ${nf(sc.price_after, 0)} ₽`) : ""}
        </div>
      </section>

      <section class="card span-5">
        <h3>Как складывается цена</h3>
        <p class="cap">Трудовая часть считается через полные трудозатраты по цепочке,
          внешний контур - по рыночному рублю. Разрыв с рыночной ценой и есть
          наблюдаемая рента.</p>
        <div class="chart" id="wf"></div>
      </section>

      <section class="card span-7">
        <h3>Разложение полных трудозатрат по отраслям-донорам</h3>
        <p class="cap">Сколько чужого труда упаковано в изделие. Каждый донор входит
          в цену со своим коэффициентом k<sub>m</sub> и надбавкой μ<sub>m</sub>.</p>
        <div class="chart" id="donors"></div>
      </section>

      <section class="card span-7">
        <h3>Порядок образования цены: восемь шагов</h3>
        <p class="cap">Каждый шаг наблюдаем и проверяем по реестру: от нормы времени
          на операцию до сверки с рыночной ценой аналога.</p>
        <div class="steps">${d.steps.map((s2) => `
          <div class="step">
            <span class="n">${s2.n}</span>
            <span class="t">${s2.title}<i>${s2.detail}</i></span>
            <span class="v">${nf(s2.value, s2.value < 100 ? 2 : 0)}<s>${s2.unit}</s></span>
          </div>`).join("")}</div>
        <div class="formula">P_i = B · Σ_m [h_im · k_m · (1 + μ_m)] + E_i
μ_m = [d_m + (1 − φ)·s_m] / b_m        надбавка выводится, а не назначается
R_i = (P_рыночная − P_производства) / P_рыночная</div>
      </section>

      <section class="card span-5">
        <h3>Реакция цены на сценарий экстерналий</h3>
        <p class="cap">Δ ln P = Σ ε<sub>k</sub> · Δ ln X<sub>k</sub>. Эластичности оценены
          панельной регрессией по сделкам сети и переоцениваются ежеквартально.</p>
        <div class="chart" id="shock"></div>
        ${sc ? `<div class="scroll" style="max-height:220px;margin-top:14px">
          <table class="tbl" id="shock-table"></table></div>` : ""}
      </section>

      <section class="card span-12">
        <h3>Эмиссия ТЧЧ на изделие: расшифровка множителей</h3>
        <p class="cap">τ = [λ·T_факт + (1 − λ)·T_норм] · K_сл · K_цикл · q · k_j.
          Простой по вине оборудования оплачивается на 30%, перевыполнение нормы -
          полностью; брак ниже порога 0,90 обнуляет эмиссию.</p>
        <div class="steps">${d.emission.steps.map((s2) => `
          <div class="step">
            <span class="n">${s2.factor ? "×" : "="}</span>
            <span class="t">${s2.label}<i>${s2.detail}${
              s2.factor ? ` · множитель ${nf(s2.factor, 4)}` : ""}</i></span>
            <span class="v">${nf(s2.value, 3)}<s>${s2.factor ? "ТЧЧ" : "ч"}</s></span>
          </div>`).join("")}</div>
      </section>
    </div>`;

  q(root, "#sku").addEventListener("change", (e) => {
    const [ent, sku] = e.target.value.split("|");
    actions.set({ ent, sku });
  });
  factors.forEach(([k]) => q(root, `#f-${k}`).addEventListener("change", (e) => {
    actions.set({ factors: { ...state.factors, [k]: (parseFloat(e.target.value) || 0) / 100 } });
  }));
  q(root, "#reset").addEventListener("click", () => actions.set({
    factors: { energy: 0, fx: 0, rate: 0, logistics: 0, raw: 0 } }));

  C.waterfall(q(root, "#wf"), {
    items: d.waterfall, height: 300, format: (v) => compact(v, " ₽"),
  });
  C.legend(q(root, "#wf"), [
    { color: "var(--ser-2)", label: "трудовая часть" },
    { color: "var(--ser-1)", label: "внешний контур" },
    { color: "var(--luch)", label: "цена производства" },
    { color: "var(--patina)", label: "рыночная цена аналога" }]);

  C.barsH(q(root, "#donors"), {
    rows: p.donors, padL: 200, label: (r) => `${r.code} ${r.short}`,
    value: (r) => r.hours, color: (r) => (r.code === d.product.cls ? "var(--luch)" : "var(--ser-2)"),
    format: (v) => nf(v, 2) + " ч",
    tipTitle: (r) => `${r.code} · ${r.name}`,
    tip: (r) => [["полные чел.-ч", nf(r.hours, 2)], ["коэффициент k_m", nf(r.k, 3)],
      ["надбавка μ_m", nf(r.mu, 3)], ["ТЧЧ", nf(r.tokens, 2)], ["в цене", nf(r.rub, 0) + " ₽"]],
  });
  C.legend(q(root, "#donors"), [
    { color: "var(--luch)", label: "собственная отрасль изделия" },
    { color: "var(--ser-2)", label: "отрасли-доноры цепочки" }]);

  C.barsH(q(root, "#shock"), {
    rows: [...d.shock_table].sort((a, b) => b.percent - a.percent),
    width: 620, padL: 190, padR: 80, label: (r) => `${r.code} ${r.short}`, value: (r) => r.percent,
    color: (r) => (r.code === d.product.cls ? "var(--luch)" : "var(--ser-1)"),
    format: (v) => (v >= 0 ? "+" : "−") + nf(Math.abs(v), 2) + "%",
    tipTitle: (r) => `${r.code} · ${r.short}`,
    tip: (r) => r.factors.map((f) => [f.label,
      `ε ${nf(f.elasticity, 2)} · ${pct(f.change, 0)} → ${pct(f.contribution, 2)}`]),
  });

  if (sc) {
    table(q(root, "#shock-table"), sc.factors.map((f, i) => ({ ...f, id: i })), [
      { k: "label", t: "Фактор", f: (r) => `<span class="name">${r.label}</span>` },
      { k: "elasticity", t: "ε", f: (r) => nf(r.elasticity, 2) },
      { k: "change", t: "Δ фактора", f: (r) => pct(r.change, 0) },
      { k: "contribution", t: "Вклад в Δ ln P", f: (r) =>
        `<span class="${r.contribution >= 0 ? "neg" : "pos"}">${pct(r.contribution, 3)}</span>` },
    ], "contribution");
  }
}

/* --------------------------------------------------- канал субститутов */
export function channel(root, d) {
  const LO = 300, HI = 1400;
  const pos = (v) => ((v - LO) / (HI - LO)) * 100;
  root.innerHTML = `
    <div class="grid">
      <section class="card pale span-8">
        <div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap">
          <span class="tag"><em>канал ${d.key}</em></span>
          <h3>${d.title}</h3>
        </div>
        <p class="cap">${d.note}</p>
        <div class="qrow" style="border:0"><div></div>
          <div class="qscale">${[400, 600, 800, 1000, 1200, 1400].map((v) =>
            `<span class="num" style="left:${pos(v)}%">${v}</span>`).join("")}</div><div></div></div>
        ${d.items.map((it) => `
          <div class="qrow">
            <div class="qname">${it.name}<i>${it.origin}</i></div>
            <div class="qtrack" title="P10 ${it.p10} · медиана ${it.med} · P90 ${it.p90}">
              <div class="qband" style="left:${pos(it.p10)}%;width:${pos(it.p90) - pos(it.p10)}%"></div>
              <div class="qbox" style="left:${pos(it.p25)}%;width:${pos(it.p75) - pos(it.p25)}%"></div>
              <div class="qmed" style="left:${pos(it.med)}%"></div>
            </div>
            <div class="qval num">${nf(it.med, 0)}<i>Σ ${nf(it.sigma, 2)} · лок. ${nf(it.loc, 2)}</i></div>
          </div>`).join("")}
        <p class="cap" style="margin-top:18px">Полоса - интервал P10-P90, плотный блок -
          P25-P75, риска - медиана, руб. за метр. Индекс Σ - замещаемость к ПЭ100:
          0,6·косинус технической близости + 0,4·частота фактических переключений.</p>
      </section>

      <section class="card span-4">
        <h3>Правила публикации</h3>
        <p class="cap">Жёсткие и невыводимые: это юридическое условие законности
          конструкции, а не лучшая практика.</p>
        <div class="steps">${d.rules.map((r, i) => `
          <div class="step"><span class="n">${i + 1}</span>
          <span class="t">${r}</span><span class="v"></span></div>`).join("")}</div>
        <p class="note" style="margin-top:16px">Продавцов в окне: <b>${d.sellers}</b>.
          Порог k-анонимности - 5. Индивидуальные цены сделок не покидают расчётное ядро.</p>
      </section>

      <section class="card span-12">
        <h3>Вклад экстерналий в цену канала</h3>
        <p class="cap">Сценарий: энергия +12%, курс +8%. Итог для класса 22 -
          ${nf(d.shock_percent, 2)}% к цене. Устойчиво большой необъяснённый остаток
          по группе уходит в комплаенс-обзор.</p>
        <div class="chart" id="cshock"></div>
      </section>
    </div>`;

  C.barsH(q(root, "#cshock"), {
    rows: d.shock, padL: 160, label: (r) => r.label,
    value: (r) => r.contribution * 100,
    color: () => "var(--ser-1)",
    format: (v) => nf(v, 3) + " п.п.",
    tipTitle: (r) => r.label,
    tip: (r) => [["эластичность ε", nf(r.elasticity, 2)], ["изменение фактора", pct(r.change, 0)],
      ["вклад в Δ ln P", nf(r.contribution, 4)]],
  });
}

/* ---------------------------------------------------------- предприятия */
export function enterprises(root, d, state, actions) {
  const sizes = ["все", "крупное", "среднее"];
  const rows = d.rows.filter((r) => state.size === "все" || !state.size || r.size === state.size);
  root.innerHTML = `
    <div class="filters">
      <div class="f"><span>категория по 209-ФЗ</span>
        <div class="chips" style="margin:0">${sizes.map((s2) =>
          `<button class="chip" data-size="${s2}" aria-pressed="${state.size === s2}">${s2}</button>`).join("")}</div>
      </div>
      <div class="f"><span>карточка предприятия</span>
        <select id="ent">${d.rows.map((r) =>
          `<option value="${r.id}" ${r.id === state.ent ? "selected" : ""}>${r.name}</option>`).join("")}</select>
      </div>
    </div>
    <div class="grid">
      <section class="card span-12">
        <h3>Реестр экономических субъектов периметра</h3>
        <p class="cap">Критерии отнесения (ФЗ № 209-ФЗ): среднее предприятие -
          251-1000 работников и годовой доход до 2 млрд руб.; крупное - свыше.
          ${d.disclaimer}</p>
        <div class="scroll"><table class="tbl" id="ent-table"></table></div>
      </section>

      <section class="card span-6">
        <h3>Капиталооборот: выручка на работника</h3>
        <p class="cap">Млн руб. в год. Критерий отнесения к средним и крупным субъектам -
          численность и годовой доход; объём инфраструктуры показан отдельно.</p>
        <div class="chart" id="rev"></div>
      </section>

      <section class="card span-6">
        <h3>Объём инфраструктуры: основные фонды на работника</h3>
        <p class="cap">Млн руб. Фондовооружённость объясняет, почему час в фарме
          и металлургии «весомее» часа в переработке пластмасс.</p>
        <div class="chart" id="assets"></div>
      </section>

      <section class="card span-12" id="card"></section>
    </div>`;

  root.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click",
    () => actions.set({ size: chip.dataset.size })));
  q(root, "#ent").addEventListener("change", (e) => actions.set({ ent: e.target.value }));

  table(q(root, "#ent-table"), rows, [
    { k: "name", t: "Предприятие", f: (r) => `<span class="name">${r.name}<i>${r.city} · группа ${r.group}</i></span>` },
    { k: "okved", t: "ОКВЭД", f: (r) => `${r.okved}<br><span style="color:var(--ink-3)">${r.industry_short}</span>` },
    { k: "size", t: "Категория", f: (r) => r.size },
    { k: "headcount", t: "Численность", f: (r) => nf(r.headcount, 0) },
    { k: "revenue_bn", t: "Выручка, млрд ₽", f: (r) => nf(r.revenue_bn, 1) },
    { k: "assets_bn", t: "Основные фонды, млрд ₽", f: (r) => nf(r.assets_bn, 1) },
    { k: "hours_month", t: "Чел.-ч/мес", f: (r) => compact(r.hours_month) },
    { k: "tokens_month", t: "ТЧЧ/мес", f: (r) => compact(r.tokens_month) },
    { k: "tokens_rub", t: "Эмиссия, ₽/мес", f: (r) => compact(r.tokens_rub, "") },
    { k: "payroll_month", t: "ФОТ, ₽/мес", f: (r) => compact(r.payroll_month, "") },
    { k: "vds_per_hour", t: "ВДС, ₽/чел.-ч", f: (r) => nf(r.vds_per_hour, 0) },
    { k: "k", t: "k_j", f: (r) => nf(r.k, 3) },
  ], "revenue_bn", (r) => r.id === state.ent);

  q(root, "#ent-table").querySelectorAll("tbody tr").forEach((tr) =>
    tr.addEventListener("click", () => actions.set({ ent: tr.dataset.id })));

  C.barsH(q(root, "#rev"), {
    rows: [...rows].sort((a, b) => b.revenue_per_worker - a.revenue_per_worker),
    padL: 190, label: (r) => r.short, value: (r) => r.revenue_per_worker / 1e6,
    color: (r) => (r.size === "среднее" ? "var(--ser-3)" : "var(--ser-2)"),
    format: (v) => nf(v, 1),
    tipTitle: (r) => r.name,
    tip: (r) => [["выручка", nf(r.revenue_bn, 1) + " млрд ₽/год"],
      ["численность", nf(r.headcount, 0)], ["на работника", nf(r.revenue_per_worker / 1e6, 2) + " млн ₽"],
      ["категория", r.size]],
  });
  C.legend(q(root, "#rev"), [{ color: "var(--ser-2)", label: "крупное предприятие" },
    { color: "var(--ser-3)", label: "среднее предприятие" }]);

  C.barsH(q(root, "#assets"), {
    rows: [...rows].sort((a, b) => b.capital_per_worker - a.capital_per_worker),
    padL: 190, label: (r) => r.short, value: (r) => r.capital_per_worker / 1e6,
    color: (r) => (r.size === "среднее" ? "var(--ser-3)" : "var(--ser-1)"),
    format: (v) => nf(v, 1),
    tipTitle: (r) => r.name,
    tip: (r) => [["основные фонды", nf(r.assets_bn, 1) + " млрд ₽"],
      ["на работника", nf(r.capital_per_worker / 1e6, 2) + " млн ₽"],
      ["ВДС на чел.-ч", nf(r.vds_per_hour, 0) + " ₽"]],
  });
  C.legend(q(root, "#assets"), [{ color: "var(--ser-1)", label: "крупное предприятие" },
    { color: "var(--ser-3)", label: "среднее предприятие" }]);
}

export function enterpriseCard(node, d, actions) {
  const e = d.enterprise;
  node.innerHTML = `
    <div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap">
      <span class="tag"><em>ОКВЭД ${e.okved}</em></span>
      <h3>${e.name}</h3>
      <span class="note">${e.city} · ${e.size} предприятие · группа ${e.group}</span>
    </div>
    <div class="rule"></div>
    <div class="tiles">
      ${tile(nf(e.headcount, 0), "численность персонала", `производственный ${pct0(e.prod_share, 0)}`)}
      ${tile(nf(e.revenue_bn, 1) + " млрд", "выручка за год", `фонды ${nf(e.assets_bn, 1)} млрд ₽`)}
      ${tile(compact(d.hours_month), "чел.-ч в месяц", "фонд рабочего времени")}
      ${tile(compact(d.tokens_month), "ТЧЧ эмиссии в месяц", compact(d.tokens_rub, " ₽"), true)}
      ${tile(nf(d.tokens_per_hour, 3), "ТЧЧ на чел.-час", `k_j = ${nf(d.k, 3)} · K_цикл ${nf(d.k_cycle, 3)}`)}
      ${tile(compact(d.payroll_month, " ₽"), "фонд оплаты труда", `ВДС ${compact(d.vds_month, " ₽")}/мес`)}
      ${tile(compact(d.socialised_month, " ₽"), "социализируемый S за месяц", `φ·S при φ = ${nf(d.indexation.phi, 2)}`)}
      ${tile(nf(e.oee, 2), "OEE", `качество q = ${nf(e.quality, 3)}`)}
    </div>
    <div class="grid" style="margin-top:20px">
      <div class="span-7">
        <h3 style="font-size:14px">Изделия и порядок образования цены</h3>
        <div class="scroll" style="max-height:340px"><table class="tbl" id="prod-table"></table></div>
      </div>
      <div class="span-5">
        <h3 style="font-size:14px">Структура производственного персонала по разрядам</h3>
        <div class="chart" id="staff"></div>
      </div>
    </div>
    <p class="note" style="margin-top:16px">${d.disclaimer}</p>`;

  table(node.querySelector("#prod-table"), d.products_priced.map((p, i) => ({
    id: i, sku: p.product.sku, name: p.product.name, unit: p.product.unit,
    norm_hours: p.product.norm_hours, tokens: p.tokens_per_unit,
    labour: p.price.labour_rub, external: p.price.external_rub,
    production: p.price.production_price, market: p.price.market_price,
    rent: p.price.rent, full_hours: p.price.full_hours, ent: p.enterprise.id,
  })), [
    { k: "name", t: "Изделие", f: (r) => `<span class="name">${r.name}<i>${r.sku} · ${r.unit}</i></span>` },
    { k: "norm_hours", t: "Норма, ч", f: (r) => nf(r.norm_hours, 2) },
    { k: "full_hours", t: "Полные, чел.-ч", f: (r) => nf(r.full_hours, 2) },
    { k: "tokens", t: "ТЧЧ на изделие", f: (r) => nf(r.tokens, 2) },
    { k: "labour", t: "Трудовая часть, ₽", f: (r) => nf(r.labour, 0) },
    { k: "external", t: "Внешний контур, ₽", f: (r) => nf(r.external, 0) },
    { k: "production", t: "Цена производства, ₽", f: (r) => `<b>${nf(r.production, 0)}</b>` },
    { k: "market", t: "Рыночная, ₽", f: (r) => nf(r.market, 0) },
    { k: "rent", t: "Рента", f: (r) => `<span class="${r.rent >= 0 ? "neg" : "pos"}">${pct(r.rent, 1)}</span>` },
  ], "production");

  node.querySelector("#prod-table").querySelectorAll("tbody tr").forEach((tr, i) =>
    tr.addEventListener("click", () => actions.go("pricing", {
      ent: d.products_priced[0].enterprise.id,
      sku: d.products_priced[Number(tr.dataset.id)] ?
        d.products_priced[Number(tr.dataset.id)].product.sku : undefined })));

  C.barsH(node.querySelector("#staff"), {
    rows: d.staff, width: 620, padL: 130, padR: 90, rowH: 34,
    label: (r) => `разряд ${r.grade}`, value: (r) => r.headcount,
    color: () => "var(--ser-2)", format: (v) => nf(v, 0) + " чел.",
    tipTitle: (r) => `Разряд ${r.grade}`,
    tip: (r) => [["численность", nf(r.headcount, 0)], ["доля", pct0(r.share, 1)],
      ["тарифный коэффициент", nf(r.skill_coef, 3)], ["оплата, ₽/мес", nf(r.wage_month, 0)]],
  });
}

/* ------------------------------------------------------------ индексация */
export function indexation(root, d, state, actions) {
  const p = d.params;
  root.innerHTML = `
    <div class="filters">
      <div class="f"><span>предприятие</span>
        <select id="ent">${d.registry.map((r) =>
          `<option value="${r.id}" ${r.id === d.enterprise.id ? "selected" : ""}>${r.name}</option>`).join("")}</select>
      </div>
      <div class="f"><span>ИПЦ за период, %</span>
        <input type="number" step="0.1" id="cpi" value="${nf(p.cpi * 100, 1).replace(",", ".")}" style="width:92px"></div>
      <div class="f"><span>θ - участие в приросте базы</span>
        <input type="number" step="0.05" id="theta" value="${p.theta}" style="width:92px"></div>
      <div class="f"><span>ζ - вес выработки</span>
        <input type="number" step="0.05" id="zeta" value="${p.zeta}" style="width:92px"></div>
    </div>
    <div class="grid">
      <section class="card span-12">
        <div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap">
          <span class="tag"><em>шаг индексации ${d.step_months} мес</em></span>
          <h3>${d.enterprise.name}</h3>
          <span class="note">${d.enterprise.okved} · ${d.enterprise.size} предприятие</span>
        </div>
        <div class="tiles" style="margin-top:16px">
          ${tile(pct0(d.cpi, 1), "защитный контур", "ИПЦ, ст. 134 ТК РФ")}
          ${tile(pct0(d.base_growth, 2), "прирост базы часа Δb_j", "после сглаживания и коридора")}
          ${tile(pct0(d.productive, 2), "производительный контур", `θ·max(0; Δb − π) при θ = ${nf(d.theta, 2)}`)}
          ${tile(pct0(d.weighted_index, 2), "взвешенный индекс по заводу", "по фонду оплаты труда", true)}
          ${tile(pct0(d.real_gain, 2), "реальный прирост", "сверх инфляции", d.real_gain > 0)}
          ${tile(compact(d.cost_month, " ₽"), "стоимость шага в месяц", `${pct0(d.cost_share, 2)} к ФОТ`)}
          ${tile(compact(d.fund_month, " ₽"), "фонд индексации φ·S", d.constrained ? "фонд исчерпан, надтарифная часть урезана" : "фонда достаточно", !d.constrained)}
          ${tile(nf(d.payroll_in_tokens, 0), "ФОТ в ТЧЧ", `по курсу ${nf(d.B, 2)} ₽`)}
        </div>
        ${d.constrained ? `<p class="warn" style="margin-top:14px">Потребность превышает фонд:
          надтарифная часть индексации умножена на ${nf(d.scale, 3)}. Защитный контур
          не урезается никогда - это требование закона, а не параметр модели.</p>` : ""}
        ${d.deficit > 0 ? `<p class="warn" style="margin-top:14px">Дефицит защитного контура:
          ${compact(d.deficit, " ₽")} в месяц. Требуется решение правления - источник
          вне социализируемого прибавочного продукта.</p>` : ""}
      </section>

      <section class="card span-7">
        <h3>Заработная плата по разрядам: до и после шага</h3>
        <p class="cap">Оба ряда в одних единицах - рублях в месяц, поэтому сравниваются
          на одной шкале. Разряд оплачен тарифом; персональный контур добавляет только
          то, что сверх тарифа.</p>
        <div class="chart" id="wages"></div>
      </section>

      <section class="card span-5">
        <h3>Из чего складывается индекс</h3>
        <p class="cap">Три контура по разрядам, в процентных пунктах.</p>
        <div class="chart" id="parts"></div>
        <div class="formula">ι_защ  = π
ι_пр   = θ · max(0; Δb_j − π)
ι_перс = clip(ζ · (e_i/ē − 1); ±${nf(p.personal_cap * 100, 0)} п.п.)
ι_i    = clip(ι_защ + ι_пр + ι_перс; π; ${nf(p.index_cap * 100, 0)}%)
Σ W_i·ι_i ≤ F = φ · S_предприятия</div>
      </section>

      <section class="card span-12">
        <h3>Расчёт по разрядам</h3>
        <div class="scroll"><table class="tbl" id="grade-table"></table></div>
      </section>

      <section class="card span-12">
        <h3>Индексация по сети: где прирост базы часа опережает инфляцию</h3>
        <p class="cap">Пунктир - ИПЦ ${pct0(d.cpi, 1)}. Всё, что выше, - реальный прирост,
          обеспеченный ростом базы часа и выработкой, а не решением собственника.</p>
        <div class="chart" id="net"></div>
      </section>
    </div>`;

  q(root, "#ent").addEventListener("change", (e) => actions.set({ ent: e.target.value }));
  ["cpi", "theta", "zeta"].forEach((k) => q(root, `#${k}`).addEventListener("change", (e) => {
    const v = parseFloat(e.target.value.replace(",", ".")) || 0;
    actions.set({ [k]: k === "cpi" ? v / 100 : v });
  }));

  C.groupedBars(q(root, "#wages"), {
    rows: d.groups.map((g) => ({ ...g, focus: false })), height: 320,
    label: (r) => `разряд ${r.grade}`,
    max: Math.max(...d.groups.map((g) => g.wage_new)) * 1.12,
    ticks: [0, 30000, 60000, 90000, 120000, 150000].filter((t) =>
      t <= Math.max(...d.groups.map((g) => g.wage_new)) * 1.12),
    series: [
      { label: "до индексации, ₽/мес", color: "var(--ser-3)", value: (r) => r.wage_month },
      { label: "после индексации, ₽/мес", color: "var(--luch)", value: (r) => r.wage_new },
    ],
    tipTitle: (r) => `Разряд ${r.grade} · ${nf(r.headcount, 0)} чел.`,
    tip: (r) => [["до", nf(r.wage_month, 0) + " ₽"], ["после", nf(r.wage_new, 0) + " ₽"],
      ["индекс", pct0(r.index, 2)], ["выработка e_i/ē", nf(r.performance, 3)],
      ["стоимость группы", compact(r.cost, " ₽")]],
  });

  C.barsH(q(root, "#parts"), {
    rows: d.groups, width: 620, padL: 130, padR: 80, rowH: 34,
    label: (r) => `разряд ${r.grade}`, value: (r) => r.index * 100,
    color: () => "var(--ser-2)", format: (v) => nf(v, 2) + "%",
    tipTitle: (r) => `Разряд ${r.grade}`,
    tip: (r) => [["защитный", pct0(r.protective, 2)], ["производительный", pct0(r.productive, 2)],
      ["персональный", pct0(r.personal, 2)], ["итого", pct0(r.index, 2)],
      ["урезан фондом", r.scaled ? "да" : "нет"]],
  });

  table(q(root, "#grade-table"), d.groups.map((g) => ({ ...g, id: g.grade })), [
    { k: "grade", t: "Разряд", f: (r) => `<span class="name">Разряд ${r.grade}<i>выработка e_i/ē = ${nf(r.performance, 3)}</i></span>` },
    { k: "headcount", t: "Численность", f: (r) => nf(r.headcount, 0) },
    { k: "wage_month", t: "Оплата до, ₽/мес", f: (r) => nf(r.wage_month, 0) },
    { k: "protective", t: "Защитный", f: (r) => pct0(r.protective, 2) },
    { k: "productive", t: "Производительный", f: (r) => pct0(r.productive, 2) },
    { k: "personal", t: "Персональный", f: (r) => `<span class="${r.personal >= 0 ? "pos" : "neg"}">${pct0(r.personal, 2)}</span>` },
    { k: "index", t: "Итоговый индекс", f: (r) => `<b>${pct0(r.index, 2)}</b>` },
    { k: "wage_new", t: "Оплата после, ₽/мес", f: (r) => `<b>${nf(r.wage_new, 0)}</b>` },
    { k: "cost", t: "Стоимость, ₽/мес", f: (r) => compact(r.cost, "") },
  ], "grade");

  C.barsH(q(root, "#net"), {
    rows: d.network.rows, padL: 250, label: (r) => r.name.replace(/[«»]/g, ""),
    value: (r) => r.index * 100,
    color: (r) => (r.id === d.enterprise.id ? "var(--luch)"
      : r.constrained ? "var(--ser-1)" : "var(--ser-2)"),
    format: (v) => nf(v, 2) + "%",
    max: Math.max(...d.network.rows.map((r) => r.index * 100)) * 1.05,
    refValue: d.cpi * 100, refLabel: `ИПЦ ${nf(d.cpi * 100, 1)}%`,
    tipTitle: (r) => r.name,
    tip: (r) => [["класс ОКВЭД", r.cls], ["категория", r.size],
      ["индекс", pct0(r.index, 2)], ["ИПЦ", pct0(r.cpi, 2)],
      ["реальный прирост", pct0(r.real_gain, 2)],
      ["стоимость шага", compact(r.cost_month, " ₽")],
      ["фонд φ·S", compact(r.fund_month, " ₽")],
      ["урезано фондом", r.constrained ? "да" : "нет"]],
  });
  C.legend(q(root, "#net"), [
    { color: "var(--luch)", label: "выбранное предприятие" },
    { color: "var(--ser-2)", label: "фонда достаточно" },
    { color: "var(--ser-1)", label: "надтарифная часть урезана фондом" }]);
}

/* ---------------------------------------------------------------- модель */
export function model(root, d) {
  const a = d.anchor, s2 = d.smoothing, c = d.charter, ix = d.indexation;
  root.innerHTML = `
    <div class="grid">
      <section class="card span-6">
        <h3>Уставные параметры</h3>
        <p class="cap">Фиксируются уставом синдиката и публикуются вместе с отчётностью.
          Величина, которая в обычной корпорации является усмотрением инсайдера,
          здесь становится наблюдаемым параметром.</p>
        <div class="tiles">
          ${tile(nf(c.phi, 2), "φ - норма социализации", `рабочий диапазон ${nf(c.phi_range[0], 2)}-${nf(c.phi_range[1], 2)}`)}
          ${tile(nf(c.gamma, 3), "γ - шаг тарифной сетки", `K_сл: 1,000 → ${nf(Math.pow(1 + c.gamma, 7), 3)} на 8 разряде`)}
          ${tile(nf(c.delta, 2), "δ - чувствительность к циклу", `D₀ = ${nf(c.d0, 0)} дней`)}
          ${tile(nf(c.lambda_, 2), "λ - доля факта в базе времени", "остальное - по нормо-часу")}
          ${tile(nf(c.quality_floor, 2), "порог качества", "ниже - эмиссия обнуляется")}
          ${tile(pct0(c.rho, 1), "ρ - допуск ликвидности", "годовых к приросту нормо-часов")}
        </div>
      </section>

      <section class="card span-6">
        <h3>Сглаживание и якорь ожиданий</h3>
        <p class="cap">Коэффициенты задаются через полупериод, а не подбором.
          Правило ограничителя опубликовано заранее - в этом его смысл.</p>
        <div class="tiles">
          ${tile(nf(s2.alpha, 4), "α - уровень", `полупериод ${nf(s2.alpha_halflife, 0)} мес`)}
          ${tile(nf(s2.beta, 4), "β - тренд", `полупериод ${nf(s2.beta_halflife, 0)} мес`)}
          ${tile("±" + pct0(s2.max_step, 0), "предел шага базы", "в месяц")}
          ${tile(nf(a.wage, 1), "якорь, ₽/мес", "Росстат, янв-фев 2026")}
          ${tile(nf(a.hours, 1), "норма месяца, ч", "40-часовая неделя")}
          ${tile(pct0(a.social, 0), "начисления", "страховые взносы")}
        </div>
      </section>

      <section class="card span-12">
        <h3>Шесть слоёв модели</h3>
        <div class="formula">Слой 1  S_j(t) = V_j(t) − W_j(t) − D_j(t);   s_j(t) = S_j(t) / H_j(t)
Слой 2  L(t) = α·s(t) + (1−α)·[L(t−1)+T(t−1)];  T(t) = β·[L(t)−L(t−1)] + (1−β)·T(t−1)
        b_j(t) ∈ [0,98·b_j(t−1); 1,02·b_j(t−1)]
Слой 3  b_j = w_j + φ·ŝ_j;   B = Σ ω_j·b_j,  ω_j = H_j/ΣH;   k_j = b_j/B
Слой 4  τ = [λ·T_факт + (1−λ)·T_норм] · K_сл · K_цикл · q · k_j
        K_сл = (1+γ)^(g−1);  K_цикл = 1 + δ·ln(1 + D/D₀)
Слой 5  l_j = ψ_j/v_j;   h = l·(I − A)⁻¹;   P_i = B·Σ_m[h_im·k_m·(1+μ_m)] + E_i
        μ_j = [d_j + (1−φ)·s_j] / b_j;   R_i = (P_рын − P_произв)/P_рын
Слой 6  ΔM_ТЧЧ ≤ ΔQ_нормо-часов·(1+ρ);  φ(t) = clip(φ − 0,5·(I − 1 ∓ 0,02), 0, 1)
Индекс  ι_i = clip(π + θ·max(0; Δb_j − π) + clip(ζ·(e_i/ē − 1); ±${nf(ix.personal_cap * 100, 0)} п.п.); π; ${nf(ix.index_cap * 100, 0)}%)</div>
      </section>

      <section class="card span-6">
        <h3>Периметр пилота</h3>
        <p class="cap">ОКВЭД 2, классы 20-30. Участники подбираются связанными поставками,
          а не конкуренцией на одном рынке: двое производителей одного ОКПД2
          в одном канале - основание не принимать второго.</p>
        <div class="scroll" style="max-height:340px"><table class="tbl">
          <thead><tr><th>Класс</th><th>Отрасль</th></tr></thead>
          <tbody>${d.perimeter.map((p2) =>
            `<tr><td style="text-align:left"><b>${p2.code}</b></td>
             <td style="text-align:left" class="name">${p2.name}</td></tr>`).join("")}</tbody>
        </table></div>
      </section>

      <section class="card span-6">
        <h3>Границы применимости</h3>
        <p class="cap">Что эта платформа делает и чего не делает.</p>
        <div class="steps">
          <div class="step"><span class="n">1</span><span class="t">Отраслевые значения -
            демонстрационная калибровка<i>Замещаются формами П-1, П-4 и таблицами
            «затраты-выпуск» на этапе 2 дорожной карты</i></span><span class="v"></span></div>
          <div class="step"><span class="n">2</span><span class="t">Наименования предприятий
            фактические, показатели - модельные<i>Выручка, фонды, трудоёмкость и цены
            изделий подлежат замене отчётностью предприятия</i></span><span class="v"></span></div>
          <div class="step"><span class="n">3</span><span class="t">Индивидуальные цены сделок
            не покидают расчётное ядро<i>В открытый контур уходят только агрегаты,
            прошедшие фильтр k-анонимности k ≥ 5 с задержкой T+1</i></span><span class="v"></span></div>
          <div class="step"><span class="n">4</span><span class="t">Блокчейн на пилоте не нужен
            <i>Подписанный append-only журнал на Postgres с ежедневным якорением
            корневого хэша; DLT - опция фазы 5</i></span><span class="v"></span></div>
          <div class="step"><span class="n">5</span><span class="t">Тарифная сетка:
            расхождение в исходной спецификации<i>При γ = 0,125 коэффициент восьмого
            разряда равен 2,281, а не 2,027; значение 2,027 соответствует γ = 0,1075.
            Платформа считает по опубликованному γ и показывает фактический диапазон</i></span><span class="v"></span></div>
          <div class="step"><span class="n">6</span><span class="t">Правовой контур - главный риск
            <i>Ст. 11 ФЗ-135 запрещает ценовые соглашения конкурентов per se;
            конструкция законна как вертикальная кооперация с ретроспективной
            публикацией</i></span><span class="v"></span></div>
        </div>
      </section>
    </div>`;
}
