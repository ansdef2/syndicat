/* Форматирование чисел в русской локали. Табличные цифры включены в CSS. */
export const nf = (v, d = 0) =>
  (v === null || v === undefined || Number.isNaN(v)) ? "—"
    : v.toLocaleString("ru-RU", { minimumFractionDigits: d, maximumFractionDigits: d });

export const rub = (v, d = 0) => nf(v, d) + " ₽";
export const pct = (v, d = 1) => (v >= 0 ? "+" : "−") + nf(Math.abs(v * 100), d) + "%";
export const pct0 = (v, d = 1) => nf(v * 100, d) + "%";
export const tch = (v, d = 2) => nf(v, d) + " ТЧЧ";

export function compact(v, unit = "") {
  const a = Math.abs(v);
  if (a >= 1e9) return nf(v / 1e9, 2) + " млрд" + unit;
  if (a >= 1e6) return nf(v / 1e6, 1) + " млн" + unit;
  if (a >= 1e3) return nf(v / 1e3, 1) + " тыс." + unit;
  return nf(v, 0) + unit;
}

export const el = (tag, attrs = {}, text) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v; else node.setAttribute(k, v);
  }
  if (text !== undefined) node.textContent = text;
  return node;
};
