"""
Синдикат - референс-реализация математической модели.

Слои:
  1. Прибавочный продукт отрасли и его экспоненциальное сглаживание (Holt)
  2. Базовая стоимость токена человеко-часа (ТЧЧ) и отраслевые коэффициенты
  3. Индивидуальная выработка (сложность / длительность / качество)
  4. Ценообразование через полные трудозатраты (обращение Леонтьева)
  5. Экстерналии (лог-линейный пасс-тру)
  6. Контур купирования инфляции (правило эмиссии + буфер часов)

Периметр пилота: ОКВЭД 2, классы 20-30.
Все входные значения помечены как DEMO - подлежат замене данными
Росстата (П-4, П-1, таблицы "затраты-выпуск") на этапе калибровки.
"""

from dataclasses import dataclass, field
import numpy as np
import json

# ---------------------------------------------------------------------------
# 0. Константы и якорь калибровки
# ---------------------------------------------------------------------------

HOURS_PER_MONTH = 164.3       # среднемесячная норма при 40-часовой неделе
SOCIAL_RATE = 0.30            # страховые взносы
NATIONAL_WAGE_ANCHOR = 78591.4  # Росстат, янв-фев 2026, руб./мес

PHI = 0.35      # норма социализации прибавочного продукта (устав синдиката)
GAMMA = 0.125   # шаг тарифной сетки по разрядам
DELTA = 0.12    # чувствительность к длительности цикла
D0 = 30.0       # опорная длительность цикла, дней
LAMBDA = 0.30   # доля гарантии за фактическое время (остальное - за нормо-час)

ALPHA_HALFLIFE = 6.0    # полупериод сглаживания уровня, мес
BETA_HALFLIFE = 12.0    # полупериод сглаживания тренда, мес
MAX_STEP = 0.02         # предел месячного шага базы токена (якорь ожиданий)


def smoothing_coef(halflife_months: float) -> float:
    """alpha = 1 - 2^(-1/h): за h месяцев вес старого наблюдения падает вдвое."""
    return 1.0 - 2.0 ** (-1.0 / halflife_months)


ALPHA = smoothing_coef(ALPHA_HALFLIFE)
BETA = smoothing_coef(BETA_HALFLIFE)

# ---------------------------------------------------------------------------
# 1. Отраслевой справочник (DEMO-калибровка)
# ---------------------------------------------------------------------------
# wage    - средняя начисленная зарплата, руб./мес
# pi      - доля прибавочного продукта в ВДС
# d       - доля потребления основного капитала в ВДС
# psi     - доля ВДС в выпуске
# cycle   - типовая длительность производственного цикла, дней

INDUSTRIES = {
    "20": dict(name="Химические вещества и продукты",      wage=95000, pi=0.42, d=0.12, psi=0.32, cycle=7),
    "21": dict(name="Лекарственные средства",              wage=105000, pi=0.47, d=0.10, psi=0.44, cycle=21),
    "22": dict(name="Резиновые и пластмассовые изделия",   wage=68000, pi=0.28, d=0.10, psi=0.29, cycle=2),
    "23": dict(name="Прочая неметаллическая минеральная",  wage=70000, pi=0.31, d=0.13, psi=0.35, cycle=5),
    "24": dict(name="Металлургическое производство",       wage=98000, pi=0.45, d=0.15, psi=0.27, cycle=10),
    "25": dict(name="Готовые металлические изделия",       wage=82000, pi=0.26, d=0.08, psi=0.33, cycle=14),
    "26": dict(name="Компьютеры, электроника, оптика",     wage=118000, pi=0.35, d=0.10, psi=0.45, cycle=45),
    "27": dict(name="Электрическое оборудование",          wage=85000, pi=0.29, d=0.08, psi=0.34, cycle=30),
    "28": dict(name="Машины и оборудование",               wage=88000, pi=0.27, d=0.08, psi=0.36, cycle=60),
    "29": dict(name="Автотранспортные средства",           wage=80000, pi=0.22, d=0.11, psi=0.25, cycle=20),
    "30": dict(name="Прочие транспортные средства",        wage=112000, pi=0.30, d=0.10, psi=0.38, cycle=180),
}

CODES = list(INDUSTRIES.keys())
N = len(CODES)

# Отработанные человеко-часы по отраслям, млн ч/мес (DEMO, веса сети)
HOURS_SHARE = np.array([7.5, 3.2, 6.8, 9.0, 11.5, 14.0, 6.5, 8.5, 12.0, 7.0, 8.5])
HOURS_SHARE = HOURS_SHARE / HOURS_SHARE.sum()


# ---------------------------------------------------------------------------
# 2. Слой 1-2: прибавочный продукт, сглаживание, база токена
# ---------------------------------------------------------------------------

def hourly_labour_cost(wage_month: float) -> float:
    """Полная часовая стоимость труда с начислениями, руб./ч."""
    return wage_month * (1.0 + SOCIAL_RATE) / HOURS_PER_MONTH


def industry_unit_values(code: str) -> dict:
    """
    Раскладка ВДС на один отработанный человеко-час.
    v = w_total + d + s,  где pi = s/v, d_share = d/v.
    """
    row = INDUSTRIES[code]
    w_total = hourly_labour_cost(row["wage"])
    labour_share = 1.0 - row["pi"] - row["d"]
    v = w_total / labour_share            # ВДС на человеко-час
    s = row["pi"] * v                     # прибавочный продукт на человеко-час
    dep = row["d"] * v                    # амортизация на человеко-час
    return dict(w_total=w_total, v=v, s=s, dep=dep, labour_share=labour_share)


@dataclass
class HoltState:
    """Двойное экспоненциальное сглаживание удельного прибавочного продукта."""
    level: float
    trend: float = 0.0
    history: list = field(default_factory=list)

    def update(self, observation: float) -> float:
        prev_level = self.level
        self.level = ALPHA * observation + (1 - ALPHA) * (self.level + self.trend)
        self.trend = BETA * (self.level - prev_level) + (1 - BETA) * self.trend
        self.history.append(self.level)
        return self.forecast()

    def forecast(self, steps: int = 1) -> float:
        return self.level + steps * self.trend


def token_base(code: str, s_smoothed: float) -> float:
    """b_j = w_j + phi * s_j  - базовая стоимость часа отрасли, руб."""
    return industry_unit_values(code)["w_total"] + PHI * s_smoothed


def markup(code: str, s_smoothed: float) -> float:
    """
    mu_j - надбавка к трудовой цене, покрывающая амортизацию
    и несоциализированную часть прибавочного продукта.
    Выводится, а не назначается: это делает систему замкнутой.
    """
    u = industry_unit_values(code)
    b = token_base(code, s_smoothed)
    return (u["dep"] + (1 - PHI) * s_smoothed) / b


def clip_step(new: float, old: float, limit: float = MAX_STEP) -> float:
    """Ограничитель месячного шага базы - механический якорь ожиданий."""
    if old <= 0:
        return new
    ratio = new / old
    return old * min(max(ratio, 1 - limit), 1 + limit)


# ---------------------------------------------------------------------------
# 3. Слой 3: индивидуальная выработка
# ---------------------------------------------------------------------------

def skill_coef(grade: int) -> float:
    """Тарифный коэффициент разряда 1..8 по геометрической сетке."""
    return (1.0 + GAMMA) ** (grade - 1)


def cycle_coef(cycle_days: float) -> float:
    """Компенсация замороженного в длинном цикле труда."""
    return 1.0 + DELTA * np.log1p(cycle_days / D0)


def emission(t_fact: float, t_norm: float, grade: int, cycle_days: float,
             quality: float, k_ind: float) -> float:
    """
    Эмиссия ТЧЧ за операцию.
    Базой служит смесь фактического и нормативного времени: простой по вине
    оборудования не обнуляет вознаграждение, но и не оплачивается полностью.
    """
    if quality < 0.95:
        quality = 0.0 if quality < 0.90 else quality
    base = LAMBDA * t_fact + (1 - LAMBDA) * t_norm
    return base * skill_coef(grade) * cycle_coef(cycle_days) * quality * k_ind


# ---------------------------------------------------------------------------
# 4. Слой 4: полные трудозатраты и цена
# ---------------------------------------------------------------------------

def direct_labour_vector(s_smoothed: dict) -> np.ndarray:
    """l_j - прямые трудозатраты, чел.-ч на 1 руб. выпуска."""
    out = []
    for code in CODES:
        u = industry_unit_values(code)
        out.append(INDUSTRIES[code]["psi"] / u["v"])
    return np.array(out)


def build_A() -> np.ndarray:
    """
    Матрица прямых затрат внутри периметра 20-30 (DEMO).
    A[i][j] - сколько продукта отрасли i нужно на 1 руб. выпуска отрасли j.
    Сумма столбца < 1 - psi_j: остаток уходит вне периметра (сырьё, энергия).
    """
    A = np.zeros((N, N))
    idx = {c: i for i, c in enumerate(CODES)}
    links = {
        "20": {"20": .12, "23": .03},
        "21": {"20": .22, "22": .05},
        "22": {"20": .34, "24": .02},
        "23": {"20": .06, "24": .04},
        "24": {"20": .05, "23": .04, "24": .14},
        "25": {"24": .38, "20": .04, "22": .03},
        "26": {"24": .07, "22": .06, "20": .04, "27": .05, "25": .06},
        "27": {"24": .16, "22": .10, "20": .04, "25": .09, "26": .06},
        "28": {"24": .14, "25": .16, "27": .09, "22": .05, "26": .04},
        "29": {"24": .11, "25": .13, "22": .10, "27": .08, "28": .06, "26": .05},
        "30": {"24": .13, "25": .14, "27": .09, "26": .08, "28": .07, "22": .04},
    }
    for col, row_map in links.items():
        for row, val in row_map.items():
            A[idx[row], idx[col]] = val
    return A


def full_labour_content(A: np.ndarray, l: np.ndarray) -> np.ndarray:
    """h = l (I - A)^-1: полные трудозатраты, чел.-ч на 1 руб. выпуска."""
    return l @ np.linalg.inv(np.eye(N) - A)


def labour_by_industry(A: np.ndarray, l: np.ndarray, col: int) -> np.ndarray:
    """Разложение полных трудозатрат продукта по отраслям-донорам."""
    L = np.linalg.inv(np.eye(N) - A)
    return l * L[:, col]


def external_intensity(A: np.ndarray) -> np.ndarray:
    """
    Полная потребность в ресурсах вне периметра 20-30 (сырьё 05-09,
    энергия 35, транспорт 49-52) на 1 руб. выпуска. Периметр открыт:
    эти затраты входят в цену по рыночному рублю, а не по трудовой оценке.
    """
    e_direct = np.array([
        1.0 - INDUSTRIES[c]["psi"] - A[:, j].sum() for j, c in enumerate(CODES)
    ])
    return e_direct @ np.linalg.inv(np.eye(N) - A)


def rent_indicator(market_price: float, production_price: float) -> float:
    """
    Доля цены, не объяснённая ни трудом, ни воспроизводством капитала.
    Операционализация "инсайдерской ренты" по Дзарасову: величина,
    которую платформа делает наблюдаемой.
    """
    if market_price <= 0:
        return 0.0
    return (market_price - production_price) / market_price


# ---------------------------------------------------------------------------
# 5. Слой 5: экстерналии
# ---------------------------------------------------------------------------

EXTERNALITIES = ["энергия", "курс", "ключевая ставка", "логистика", "сырьё"]

# Эластичности цены по экстерналиям (DEMO, оцениваются регрессией по сети)
ELASTICITIES = {
    "20": [0.31, 0.18, 0.05, 0.07, 0.34],
    "21": [0.09, 0.41, 0.06, 0.09, 0.22],
    "22": [0.22, 0.24, 0.04, 0.08, 0.39],
    "23": [0.38, 0.08, 0.05, 0.14, 0.21],
    "24": [0.34, 0.16, 0.06, 0.11, 0.28],
    "25": [0.16, 0.12, 0.07, 0.09, 0.44],
    "26": [0.08, 0.46, 0.08, 0.07, 0.24],
    "27": [0.12, 0.33, 0.07, 0.08, 0.31],
    "28": [0.13, 0.27, 0.11, 0.08, 0.33],
    "29": [0.11, 0.29, 0.13, 0.10, 0.32],
    "30": [0.10, 0.23, 0.12, 0.09, 0.30],
}


def price_shock(code: str, dlog_x: dict) -> float:
    """Прирост лог-цены как сумма вкладов экстерналий."""
    eps = ELASTICITIES[code]
    return sum(eps[i] * dlog_x.get(f, 0.0) for i, f in enumerate(EXTERNALITIES))


# ---------------------------------------------------------------------------
# 6. Слой 6: правило эмиссии
# ---------------------------------------------------------------------------

def emission_cap(output_norm_hours: float, rho: float = 0.015) -> float:
    """Потолок прироста массы ТЧЧ: физический выпуск в нормо-часах + допуск."""
    return output_norm_hours * (1.0 + rho)


def phi_adjustment(token_price_index: float, target: float = 1.0,
                   corridor: float = 0.02, sensitivity: float = 0.5) -> float:
    """
    Обратная связь по индексу токен-цен: выход за коридор
    временно снижает норму социализации (сжимает эмиссию).
    """
    gap = token_price_index - target
    if abs(gap) <= corridor:
        return PHI
    return float(np.clip(PHI - sensitivity * (gap - np.sign(gap) * corridor), 0.0, 1.0))


# ---------------------------------------------------------------------------
# Расчёт калибровки
# ---------------------------------------------------------------------------

def run():
    # Прогон сглаживания: 24 месяца наблюдений с шумом и дрейфом
    rng = np.random.default_rng(20)
    smoothed, states = {}, {}
    for code in CODES:
        s0 = industry_unit_values(code)["s"]
        st = HoltState(level=s0 * 0.92, trend=s0 * 0.004)
        for m in range(24):
            drift = 1.0 + 0.0035 * m
            noise = rng.normal(0, 0.06)
            st.update(s0 * drift * (1 + noise))
        states[code] = st
        smoothed[code] = st.forecast()

    # База токена по отраслям
    b = {c: token_base(c, smoothed[c]) for c in CODES}
    B = float(sum(HOURS_SHARE[i] * b[c] for i, c in enumerate(CODES)))
    k = {c: b[c] / B for c in CODES}
    mu = {c: markup(c, smoothed[c]) for c in CODES}

    # Полные трудозатраты
    A = build_A()
    l = direct_labour_vector(smoothed)
    h = full_labour_content(A, l)

    rows = []
    for i, c in enumerate(CODES):
        u = industry_unit_values(c)
        rows.append(dict(
            code=c, name=INDUSTRIES[c]["name"],
            w_hour=round(u["w_total"], 1),
            vds_hour=round(u["v"], 1),
            s_raw=round(u["s"], 1),
            s_smooth=round(smoothed[c], 1),
            b=round(b[c], 2), k=round(k[c], 4), mu=round(mu[c], 4),
            labour_share=round(u["labour_share"], 3),
            capital_share=round(INDUSTRIES[c]["pi"], 3),
            l_direct=round(l[i] * 1000, 4),     # чел.-ч на 1000 руб. выпуска
            h_full=round(h[i] * 1000, 4),
            multiplier=round(h[i] / l[i], 3),
            cycle=INDUSTRIES[c]["cycle"],
            k_cycle=round(cycle_coef(INDUSTRIES[c]["cycle"]), 4),
        ))

    # Пример: насос центробежный К100-65-200, отрасль 28
    idx28 = CODES.index("28")
    output_rub = 186000.0       # DEMO рыночная цена аналога, руб.
    decomposition = labour_by_industry(A, l, idx28) * output_rub
    price_tch = sum(decomposition[i] * k[c] * (1 + mu[c]) for i, c in enumerate(CODES))
    ext = external_intensity(A)
    ext_rub = float(ext[idx28] * output_rub)
    production_price = float(price_tch * B) + ext_rub
    rent = rent_indicator(output_rub, production_price)

    # Пример шока: энергия +12%, курс +8%
    shock = {"энергия": np.log(1.12), "курс": np.log(1.08)}
    shocks = {c: round(100 * (np.exp(price_shock(c, shock)) - 1), 2) for c in CODES}

    result = dict(
        alpha=round(ALPHA, 4), beta=round(BETA, 4), phi=PHI,
        B_network=round(B, 2),
        anchor_national_wage=NATIONAL_WAGE_ANCHOR,
        industries=rows,
        pump_example=dict(
            market_price=output_rub,
            full_hours=round(float(decomposition.sum()), 2),
            price_tch=round(float(price_tch), 2),
            labour_part_rub=round(float(price_tch * B), 2),
            external_rub=round(ext_rub, 2),
            production_price_rub=round(production_price, 2),
            rent_share=round(rent, 4),
            by_industry={CODES[i]: round(float(decomposition[i]), 2)
                         for i in range(N) if decomposition[i] > 0.01},
        ),
        external_intensity={c: round(float(ext[i]), 4) for i, c in enumerate(CODES)},
        shock_energy12_fx8_percent=shocks,
    )
    return result


if __name__ == "__main__":
    res = run()
    print(json.dumps(res, ensure_ascii=False, indent=2))
