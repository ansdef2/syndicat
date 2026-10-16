# -*- coding: utf-8 -*-
"""Муниципальный слой: влияние производственных циклов предприятий на города.

Слой связывает отраслевую сетку (territories.py) с открытыми данными ПМО
(pmo.py) и строит сценарии до 2036 года. Основа - консорциум (consortium.py):
решения регуляторов консорциума - драйверы сценариев.

1. Производственный цикл. Активность предприятия A_e(t), индекс 2024 = 1,
   раскладывается методом наименьших квадратов по отчётным годам:

       ln A_e(t) = a + b·τ + c·cos(2πτ/P_e) + d·sin(2πτ/P_e) + ε,   τ = t − 2024

   P_e - период производственного цикла дивизиона (кампания перегрузки топлива
   АЭС - 1,5 года, заказной цикл машиностроения - 4 года и т.д.).

2. Доли сценариев. Годовые приросты ln A за отчётные годы делятся на рост
   (> +1,5%), инерцию (±1,5%) и снижение (< −1,5%); доли со сглаживанием Лапласа
   p_s = (n_s + 1)/(n + 3) - веса позитивного, инерционного и негативного сценариев.

3. Проекция до 2036 года:

       ln A_s(τ) = b·Σ_{i≤τ} δⁱ + цикл(τ) + k_s·Δ_e·τ + Σ_k u_{s,k}·x_{e,k}·τ + мощности_s(τ)

   инерционный сценарий - затухающий тренд (δ = 0,92) и продолжение цикла;
   позитивный и негативный - сдвиг тренда на ±Δ_e (половина стандартного
   отклонения приростов) и драйверы консорциума u_{s,k} (рынок, внутренний спрос,
   отраслевая политика), взвешенные долями выручки предприятия x_{e,k}.

4. Передаточный механизм «предприятие → город» на каждый год:

       численность    h_e = h_e⁰·A^η_E                       η_E = 0,35
       ФОТ            W_e = W_e⁰·A^(η_E+η_W)·(1 + g_w)^τ      η_W = 0,15
       смежная занятость  E_пр = E_пр⁰ + κ·(E_пред − E_пред⁰)          κ = 0,5
       население      P = P⁰·(E/E⁰)^μ                          μ = 0,6
       S предприятия  S_e = V_e⁰·A − W_e·(1 + 30%) − D_e       операционный рычаг
       экозатраты     C_e = Q_e·c_d·(1 − λ_s)^τ,  инвестиции в бережливое = Q_e·i_s
       собственные доходы города  НДФЛ·норматив + земельный налог + плата за НВОС + прочие
       расходы        X = P·x⁰·(1 + g_x)^τ
       трансферты     T = max(0; X − собственные доходы)·покрытие
       межбюджетное сальдо  T − (НДФЛ в субъект + налог на имущество + налог на прибыль в субъект)

   Базовый год откалиброван по последнему отчётному году панели ПМО: модель
   разделяет показатели города на вклад предприятий группы и остальную экономику.

5. Устойчивость предприятия - чувствительность его прибавочного продукта S к 10%
   изменению каждого драйвера и просадка негативного сценария к 2030 году:

       R_e = 1 / (1 + Σ_k ΔS_k/S + 2·(1 − A_neg/A_inert))

   Вес предприятия в сетке - его значимость для города (доля в занятости и в
   собственных доходах бюджета), умноженная на ожидаемую активность к 2030 году.

Все коэффициенты - демонстрационные и вынесены в константы этого модуля.
"""

import math
from functools import lru_cache

from .. import linalg
from . import consortium, pmo, rosatom
from .constants import NDFL_RATE, PHI, SOCIAL_RATE
from .territories import grid

PROJ_YEARS = list(range(pmo.BASE_YEAR + 1, 2037))
MARKS = (2030, 2036)

# --- производственные циклы и интенсивности по дивизионам (DEMO) -----------
CYCLE_YEARS = {"power": 1.5, "fuel": 2.0, "mining": 3.0, "radiochem": 3.0, "machine": 4.0}
ENV_INTENSITY = {"mining": 0.012, "fuel": 0.006, "radiochem": 0.015, "machine": 0.004,
                 "power": 0.003}          # текущие экозатраты, доля выпуска
EMISSION_INTENSITY = {"mining": 260.0, "fuel": 45.0, "radiochem": 70.0, "machine": 60.0,
                      "power": 8.0}       # т выбросов на 1 млрд руб. выпуска
REGULATED = {"power": 0.4}                # доля выручки под регулированием отрасли

# --- передаточный механизм (DEMO) ------------------------------------------
ETA_EMPLOYMENT = 0.35
ETA_WAGE = 0.15
LOCAL_MULTIPLIER = 0.5
MIGRATION_ELASTICITY = 0.6
RETAIL_PROPENSITY = 0.55
LAND_RATE = 0.0012          # земельный налог к стоимости основных фондов
PROPERTY_RATE = 0.011       # налог на имущество организаций (в бюджет субъекта)
PROFIT_BASE = 0.5           # налогооблагаемая прибыль как доля S
PROFIT_REGION_RATE = 0.17   # ставка налога на прибыль в бюджет субъекта
BOOK_PROFIT = 0.55          # сальдированный финансовый результат как доля S
ENV_FEE_SHARE = 0.25        # плата за НВОС в текущих экозатратах
ENV_FEE_LOCAL = 0.6         # доля платы за НВОС в бюджете городского округа (уточнить по БК РФ)
REINVEST = 1.05             # инвестиции в основной капитал к амортизации
GROWTH_BAND = 0.015
DAMPING = 0.92
RESILIENT, MODERATE = 0.5, 0.35
EFFECT_BAND = 0.003         # порог среднегодового эффекта для классификации
# Веса индекса эффекта: ФОТ города, занятость, собственные доходы бюджета,
# зависимость от трансфертов (рост - минус), выбросы (рост - минус)
EFFECT_WEIGHTS = dict(payroll=0.30, employees=0.25, tax_revenue=0.25, transfers=0.10,
                      emissions=0.10)

SCENARIOS = [
    dict(key="positive", name="Позитивный", trend=1.0, market=0.015, market_years=12,
         domestic=0.010, sectoral=0.015, wage=0.025, wage_other=0.020, spend=0.015,
         lean=0.05, lean_capex=0.006, ndfl_delta=0.05, cover_delta=0.0, capacity="plan",
         text="рост экспорта и внутреннего спроса, ввод мощностей по плану, норматив НДФЛ "
              "городу +5 п.п., ускоренное бережливое производство"),
    dict(key="inertial", name="Инерционный", trend=0.0, market=0.0, market_years=12,
         domestic=0.0, sectoral=0.0, wage=0.015, wage_other=0.012, spend=0.010,
         lean=0.02, lean_capex=0.003, ndfl_delta=0.0, cover_delta=0.0, capacity="delay",
         text="затухающий тренд отчётных лет, продолжение производственного цикла, ввод "
              "мощностей с задержкой, бюджетные правила без изменений"),
    dict(key="negative", name="Негативный", trend=-1.0, market=-0.03, market_years=4,
         domestic=-0.010, sectoral=-0.015, wage=0.0, wage_other=0.0, spend=0.005,
         lean=0.005, lean_capex=0.001, ndfl_delta=0.0, cover_delta=-0.15, capacity=None,
         text="падение экспорта четыре года, снижение внутреннего спроса и заказа, перенос "
              "ввода мощностей, сокращение покрытия разрыва трансфертами на 15 п.п."),
]
SC_BY_KEY = {s["key"]: s for s in SCENARIOS}

# Ввод замещающих мощностей - допущение сценариев (шаг ln A и год по варианту)
CAPACITY = {"kursk": dict(step=0.30, plan=2027, delay=2029),
            "leningrad": dict(step=0.12, plan=2031, delay=2034)}

HISTORY_SCENARIO = dict(key="history", trend=0.0, market=0.0, market_years=0, domestic=0.0,
                        sectoral=0.0, wage=0.02, wage_other=0.015, spend=0.012, lean=0.02,
                        lean_capex=0.002, ndfl_delta=0.0, cover_delta=0.0, capacity=None)

# Показатели модели вне ПМО, нужные для анализа
EXTRA = [
    dict(key="market_out", name="Выход продукции предприятий группы на внешний рынок",
         unit="тыс. руб.", section="Модель", relation="прямая", scope="модель",
         role="конвертация выпуска на рынке"),
    dict(key="opex", name="Операционные затраты предприятий группы", unit="тыс. руб.",
         section="Модель", relation="прямая", scope="модель",
         role="труд, промежуточное потребление и экозатраты"),
    dict(key="region_receipts", name="Поступления с территории в бюджет субъекта",
         unit="тыс. руб.", section="Модель", relation="косвенная", scope="модель",
         role="НДФЛ в субъект, налог на имущество, налог на прибыль"),
    dict(key="interbudget_net", name="Сальдо межбюджетных отношений в пользу города",
         unit="тыс. руб.", section="Модель", relation="косвенная", scope="модель",
         role="трансферты минус поступления с территории в субъект"),
    dict(key="effect", name="Эффект деятельности предприятий для муниципалитета", unit="%",
         section="Модель", relation="прямая", scope="модель",
         role="отличие города от контрфакта с активностью предприятий на уровне 2024 года: "
              "ФОТ, занятость, собственные доходы, трансферты, выбросы"),
    dict(key="background", name="Экономический и финансовый фон муниципалитета к 2024 году",
         unit="%", section="Модель", relation="косвенная", scope="модель",
         role="тот же индекс относительно 2024 года: эффект предприятий и общий фон"),
]
INDICATORS = pmo.CATALOG + EXTRA
MONEY = {c["key"] for c in INDICATORS if c["unit"] == "тыс. руб."}


# --------------------------------------------------------------------------
# база предприятий из отраслевой сетки
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def enterprise_base() -> dict:
    """Базовый год предприятий: из сетки группы, без шока, по уставному φ."""
    out = {}
    for r in grid(PHI)["rows"]:
        out[r["id"]] = dict(
            id=r["id"], short=r["short"], city_id=r["city_id"], city=r["city"],
            division=r["division"], stage=r["stage"], headcount=r["headcount"],
            payroll=r["payroll_year"], V=r["V"], D=r["D"], IC=r["intermediate"],
            output=r["output"], external=r["external_sales"], export=r["export"],
            domestic=r["domestic"], internal=r["internal_sales"], assets=r["assets"],
            capital=r["capital_received"], S=r["S"])
    return out


def city_enterprises(cid: str) -> list:
    return [e for e in enterprise_base().values() if e["city_id"] == cid]


def _capacity(eid: str, scenario: dict, year: int) -> float:
    c = CAPACITY.get(eid)
    if not c or not scenario.get("capacity"):
        return 0.0
    return c["step"] if year >= c[scenario["capacity"]] else 0.0


def enterprise_year(e: dict, A: float, tau: int, sc: dict, cap: float = 0.0) -> dict:
    """Слой 1 и экозатраты предприятия в году τ при активности A (цены 2024 года)."""
    div = e["division"]
    lean = (1.0 - sc["lean"]) ** tau
    cap_factor = 1.0 + 0.5 * (math.exp(cap) - 1.0)
    headcount = e["headcount"] * A ** ETA_EMPLOYMENT
    payroll = e["payroll"] * A ** (ETA_EMPLOYMENT + ETA_WAGE) * (1.0 + sc["wage"]) ** tau
    V, IC, output = e["V"] * A, e["IC"] * A, e["output"] * A
    D = e["D"] * cap_factor
    W = payroll * (1.0 + SOCIAL_RATE)
    S = V - W - D
    env = output * ENV_INTENSITY[div] * lean
    lean_capex = output * sc["lean_capex"]
    return dict(
        headcount=headcount, payroll=payroll, V=V, W=W, D=D, S=S, output=output,
        external=e["external"] * A, export=e["export"] * A, IC=IC,
        env=env, lean_capex=lean_capex,
        emissions=output / 1e9 * EMISSION_INTENSITY[div] * lean,
        land=e["assets"] * cap_factor * LAND_RATE,
        property=e["assets"] * cap_factor * PROPERTY_RATE,
        profit_region=max(S, 0.0) * PROFIT_BASE * PROFIT_REGION_RATE,
        opex=W + IC + env,
        investment=D * REINVEST + lean_capex + e["capital"] * A,
    )


# --------------------------------------------------------------------------
# город: база и передаточный механизм
# --------------------------------------------------------------------------
def city_year(base: dict, ents: list, acts: dict, year: int, sc: dict) -> dict:
    """Состояние города в году при заданной активности предприятий (₽, цены 2024)."""
    tau = year - pmo.BASE_YEAR
    rows = {e["id"]: enterprise_year(e, acts[e["id"]], tau, sc, _capacity(e["id"], sc, year))
            for e in ents}
    total = lambda k: sum(r[k] for r in rows.values())
    E_ent, W_ent = total("headcount"), total("payroll")
    E_other = max(base["E_other"] + LOCAL_MULTIPLIER * (E_ent - base["E_ent"]), 0.0)
    E_tot = E_ent + E_other
    P = base["P"] * (E_tot / base["E_tot"]) ** MIGRATION_ELASTICITY
    W_other = E_other * base["wage_other"] * 12.0 * (1.0 + sc["wage_other"]) ** tau
    payroll = W_ent + W_other

    norm = base["norm"] + (sc["ndfl_delta"] if year >= 2026 else 0.0)
    ndfl_local = payroll * NDFL_RATE * norm
    land = total("land")
    env_fee = total("env") * ENV_FEE_SHARE * ENV_FEE_LOCAL
    other_own = P * base["other_own_pc"] * (1.0 + 0.5 * sc["spend"]) ** tau
    own = ndfl_local + land + env_fee + other_own
    X = P * base["spend_pc"] * (1.0 + sc["spend"]) ** tau
    cover = min(1.2, max(0.0, base["cover"] + (sc["cover_delta"] if year >= 2026 else 0.0)))
    T = max(0.0, X - own) * cover
    region = payroll * NDFL_RATE * (1.0 - norm) + total("property") + total("profit_region")

    net = payroll * (1.0 - NDFL_RATE)
    return dict(
        year=year, population=P, employees=E_tot, employees_ent=E_ent,
        avg_wage=payroll / E_tot / 12.0, payroll=payroll, payroll_ent=W_ent,
        shipped=total("output") + base["q_other"] * E_other / base["E_other"],
        market_out=total("external"),
        investment=total("investment") + base["inv_other"] * P / base["P"],
        fin_result=total("S") * BOOK_PROFIT + base["fin_other"],
        retail=base["retail_rate"] * net,
        tax_revenue=own, ndfl_local=ndfl_local, land=land, env_fee=env_fee,
        other_own=other_own, ndfl_local_ent=W_ent * NDFL_RATE * norm,
        transfers=T, budget_revenue=own + T, budget_expenditure=X,
        budget_balance=own + T - X,
        region_receipts=region, interbudget_net=T - region,
        emissions=total("emissions") + base["emis_other"],
        env_costs=total("env"), lean_capex=total("lean_capex"), opex=total("opex"),
        S_ent=total("S"), net_income=net, enterprises=rows,
    )


def structural_base(cid: str) -> dict:
    """База города по умолчанию - для синтетической панели (pmo_synth.py)."""
    city = rosatom.CITIES[cid]
    ents = city_enterprises(cid)
    E_ent = sum(e["headcount"] for e in ents)
    W_ent = sum(e["payroll"] for e in ents)
    employed = city["population"] * 0.38
    E_other = max(employed - E_ent, 0.15 * employed)
    wage_other = W_ent / E_ent / 12.0 * 0.6
    payroll = W_ent + E_other * wage_other * 12.0
    base = dict(P=city["population"], E_ent=E_ent, E_other=E_other, E_tot=E_ent + E_other,
                wage_other=wage_other, norm=0.15 + (0.05 if city["zato"] else 0.02),
                spend_pc=62000.0 * (1.3 if city["zato"] else 1.0), other_own_pc=5500.0,
                cover=0.97 if city["zato"] else 0.9, q_other=E_other * 1.3e6,
                inv_other=city["population"] * 25000.0, fin_other=E_other * 90000.0,
                emis_other=city["population"] * 0.02,
                retail_rate=RETAIL_PROPENSITY)
    base["payroll0"] = payroll
    return base


def calibrate(cid: str, panel: dict) -> dict:
    """База города по последнему отчётному году панели ПМО.

    Показатели города делятся на вклад предприятий группы (модель) и остальную
    экономику (остаток). Так модель воспроизводит базовый год панели, а
    изменения активности предприятий передаются только через их долю.
    """
    y = pmo.BASE_YEAR
    get = lambda key, scale=1.0: pmo.series(panel, cid, key)[y] * scale
    ents = city_enterprises(cid)
    hist = HISTORY_SCENARIO
    ent0 = {e["id"]: enterprise_year(e, 1.0, 0, hist) for e in ents}
    tot = lambda k: sum(r[k] for r in ent0.values())

    P, employees, payroll = get("population"), get("employees"), get("payroll", 1e3)
    E_ent, W_ent = tot("headcount"), tot("payroll")
    E_other = max(employees - E_ent, 0.10 * employees)
    W_other = max(payroll - W_ent, 0.05 * payroll)
    tax_revenue, ndfl = get("tax_revenue", 1e3), get("ndfl_local", 1e3)
    expenditure, transfers = get("budget_expenditure", 1e3), get("transfers", 1e3)
    env_fee = tot("env") * ENV_FEE_SHARE * ENV_FEE_LOCAL
    other_own = max(tax_revenue - ndfl - tot("land") - env_fee, 0.0)
    gap = expenditure - tax_revenue
    return dict(
        P=P, E_ent=E_ent, E_other=E_other, E_tot=E_ent + E_other,
        wage_other=W_other / E_other / 12.0,
        norm=ndfl / (payroll * NDFL_RATE), spend_pc=expenditure / P,
        other_own_pc=other_own / P,
        cover=min(1.2, max(0.0, transfers / gap)) if gap > 0 else 0.0,
        q_other=max(get("shipped", 1e3) - tot("output"), 0.0),
        inv_other=max(get("investment", 1e3) - tot("investment"), 0.0),
        fin_other=get("fin_result", 1e3) - tot("S") * BOOK_PROFIT,
        emis_other=max(get("emissions") - tot("emissions"), 0.0),
        retail_rate=get("retail", 1e3) / (payroll * (1.0 - NDFL_RATE)),
        payroll0=payroll,
    )


# --------------------------------------------------------------------------
# производственный цикл: оценка и проекция активности
# --------------------------------------------------------------------------
def fit_activity(history: dict, period: float) -> dict:
    """МНК: ln A = a + b·τ + c·cos(2πτ/P) + d·sin(2πτ/P); доли сценариев по приростам."""
    years = sorted(history)
    taus = [y - pmo.BASE_YEAR for y in years]
    ys = [math.log(history[y]) for y in years]
    columns = [[1.0] * len(taus), [float(t) for t in taus]]
    names = ["a", "b"]
    for name, fn in (("c", math.cos), ("d", math.sin)):
        col = [fn(2 * math.pi * t / period) for t in taus]
        if max(abs(v) for v in col) > 1e-6 and len(years) > len(columns) + 2:
            columns.append(col)
            names.append(name)
    k = len(columns)
    xtx = [[sum(columns[i][n] * columns[j][n] for n in range(len(ys))) for j in range(k)]
           for i in range(k)]
    xty = [sum(columns[i][n] * ys[n] for n in range(len(ys))) for i in range(k)]
    inv = linalg.inverse(xtx)
    beta = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    coef = dict(zip(names, beta))
    fitted = [sum(beta[i] * columns[i][n] for i in range(k)) for n in range(len(ys))]
    ssr = sum((ys[n] - fitted[n]) ** 2 for n in range(len(ys)))
    sigma = math.sqrt(ssr / max(1, len(ys) - k))
    sst = sum((v - sum(ys) / len(ys)) ** 2 for v in ys)

    growth = [ys[n] - ys[n - 1] for n in range(1, len(ys))]
    counts = dict(positive=sum(1 for g in growth if g > GROWTH_BAND),
                  negative=sum(1 for g in growth if g < -GROWTH_BAND))
    counts["inertial"] = len(growth) - counts["positive"] - counts["negative"]
    shares = {s: (counts[s] + 1) / (len(growth) + 3) for s in counts}
    mean_g = sum(growth) / len(growth) if growth else 0.0
    sd_g = math.sqrt(sum((g - mean_g) ** 2 for g in growth) / max(1, len(growth) - 1))
    return dict(a=coef["a"], b=coef["b"], c=coef.get("c", 0.0), d=coef.get("d", 0.0),
                period=period, sigma=sigma, r2=1.0 - ssr / sst if sst > 0 else 0.0,
                growth=dict(zip(years[1:], growth)), counts=counts, shares=shares,
                growth_sd=sd_g, delta=max(0.5 * sd_g, 0.006),
                fitted={y: math.exp(f) for y, f in zip(years, fitted)})


def _cycle(fit: dict, tau: int) -> float:
    w = 2 * math.pi * tau / fit["period"]
    return fit["c"] * math.cos(w) + fit["d"] * math.sin(w)


def project_activity(e: dict, fit: dict, sc: dict, years=PROJ_YEARS) -> dict:
    """Активность предприятия по сценарию: тренд, цикл, драйверы консорциума, мощности."""
    out = e["output"] or 1.0
    x_market = e["export"] / out
    x_domestic = e["domestic"] / out
    x_sector = e["internal"] / out + REGULATED.get(e["division"], 0.0)
    path = {}
    for year in years:
        tau = year - pmo.BASE_YEAR
        trend = fit["b"] * sum(DAMPING ** i for i in range(1, tau + 1))
        cycle = _cycle(fit, tau) - _cycle(fit, 0)
        shift = sc["trend"] * fit["delta"] * tau
        drivers = (sc["market"] * x_market * min(tau, sc["market_years"])
                   + sc["domestic"] * x_domestic * tau + sc["sectoral"] * x_sector * tau)
        path[year] = math.exp(trend + cycle + shift + drivers + _capacity(e["id"], sc, year))
    return path


# --------------------------------------------------------------------------
# сборка слоя
# --------------------------------------------------------------------------
def _to_unit(key: str, value: float) -> float:
    return value / 1e3 if key in MONEY else value


def _effect(state: dict, base: dict) -> float:
    """Индекс эффекта для города относительно базы.

    Совокупные, а не душевые величины: при оттоке населения доход на жителя
    падает слабее, чем экономика города, и душевой индекс скрывал бы ущерб.
    """
    ratio = lambda k: state[k] / base[k] if base[k] else 1.0
    return (EFFECT_WEIGHTS["payroll"] * (ratio("payroll") - 1)
            + EFFECT_WEIGHTS["employees"] * (ratio("employees") - 1)
            + EFFECT_WEIGHTS["tax_revenue"] * (ratio("tax_revenue") - 1)
            + EFFECT_WEIGHTS["transfers"] * (1 - ratio("transfers"))
            + EFFECT_WEIGHTS["emissions"] * (1 - ratio("emissions")))


def effect_class(effect: float, years: int) -> str:
    """Эффект предприятий для города: среднегодовой > +0,3% - положительный, < −0,3% - негативный."""
    annual = (1.0 + effect) ** (1.0 / max(years, 1)) - 1.0
    if annual > EFFECT_BAND:
        return "positive"
    if annual < -EFFECT_BAND:
        return "negative"
    return "inertial"


def _elasticity(xs: dict, ys: dict) -> float:
    """Наклон Δln y на Δln x по общим годам (через начало координат)."""
    years = sorted(set(xs) & set(ys))
    pairs = [(math.log(xs[b] / xs[a]), math.log(ys[b] / ys[a]))
             for a, b in zip(years, years[1:]) if xs[a] > 0 and xs[b] > 0 and ys[a] > 0 and ys[b] > 0]
    den = sum(x * x for x, _ in pairs)
    return sum(x * y for x, y in pairs) / den if den > 1e-12 else 0.0


@lru_cache(maxsize=4)
def _model() -> dict:
    panel = pmo.load_panel()
    activity = pmo.load_activity()
    ebase = enterprise_base()

    fits, paths = {}, {}
    for eid, e in ebase.items():
        hist = {y: v for y, (v, _) in activity.get(eid, {}).items()}
        fits[eid] = fit_activity(hist, CYCLE_YEARS[e["division"]])
        paths[eid] = {s["key"]: project_activity(e, fits[eid], s) for s in SCENARIOS}
        paths[eid]["history"] = hist

    cities = {}
    for cid in rosatom.CITIES:
        ents = city_enterprises(cid)
        if not ents:
            continue
        base = calibrate(cid, panel)
        state0 = city_year(base, ents, {e["id"]: 1.0 for e in ents}, pmo.BASE_YEAR, HISTORY_SCENARIO)
        # модельная история: та же калибровка, фактическая активность отчётных лет
        flat = {e["id"]: 1.0 for e in ents}
        history = {}
        for year in pmo.YEARS:
            acts = {e["id"]: paths[e["id"]]["history"].get(year, 1.0) for e in ents}
            st = city_year(base, ents, acts, year, HISTORY_SCENARIO)
            st["effect"] = _effect(st, city_year(base, ents, flat, year, HISTORY_SCENARIO))
            st["background"] = _effect(st, state0)
            history[year] = st
        proj = {}
        for s in SCENARIOS:
            proj[s["key"]] = {}
            prev = state0
            still = dict(s, capacity=None)      # контрфакт: активность предприятий как в 2024
            for year in PROJ_YEARS:
                acts = {e["id"]: paths[e["id"]][s["key"]][year] for e in ents}
                st = city_year(base, ents, acts, year, s)
                st["migration"] = st["population"] - prev["population"]
                st["effect"] = _effect(st, city_year(base, ents, flat, year, still))
                st["background"] = _effect(st, state0)
                proj[s["key"]][year] = st
                prev = st
        cities[cid] = dict(base=base, state0=state0, proj=proj, history=history)
    return dict(panel=panel, activity=activity, fits=fits, paths=paths, cities=cities)


def _city_shares(ents: list, fits: dict) -> dict:
    weight = sum(e["payroll"] for e in ents)
    return {s["key"]: sum(fits[e["id"]]["shares"][s["key"]] * e["payroll"] for e in ents) / weight
            for s in SCENARIOS}


def enterprises_view(m: dict) -> list:
    """Доли сценариев, чувствительность, устойчивость и вес предприятий в сетке."""
    out = []
    for eid, e in enterprise_base().items():
        fit, path = m["fits"][eid], m["paths"][eid]
        city = m["cities"][e["city_id"]]
        st0 = city["state0"]
        row0 = st0["enterprises"][eid]
        S = row0["S"]
        taxes = row0["land"] + row0["property"] + row0["profit_region"] + \
            row0["env"] * ENV_FEE_SHARE
        risks = dict(
            market=0.1 * e["export"] / S,
            domestic=0.1 * e["domestic"] / S,
            sectoral=0.1 * (e["internal"] + REGULATED.get(e["division"], 0.0) * e["output"]) / S,
            budget=0.1 * taxes / S,
        )
        downside = 1.0 - path["negative"][2030] / path["inertial"][2030]
        resilience = 1.0 / (1.0 + sum(risks.values()) + 2.0 * max(downside, 0.0))
        own_share = (row0["payroll"] * NDFL_RATE * city["base"]["norm"] + row0["land"]
                     + row0["env"] * ENV_FEE_SHARE * ENV_FEE_LOCAL) / st0["tax_revenue"]
        significance = 0.5 * row0["headcount"] / st0["employees"] + 0.5 * own_share
        expected = sum(fit["shares"][s["key"]] * path[s["key"]][2030] for s in SCENARIOS)
        out.append(dict(
            id=eid, short=e["short"], city_id=e["city_id"], city=e["city"],
            division=e["division"], stage=e["stage"], shares=fit["shares"],
            counts=fit["counts"], trend=fit["b"], sigma=fit["sigma"], r2=fit["r2"],
            period=fit["period"], delta=fit["delta"],
            history={y: path["history"][y] for y in sorted(path["history"])},
            fitted=fit["fitted"],
            activity={s["key"]: path[s["key"]] for s in SCENARIOS},
            risks=risks, downside=downside, resilience=resilience,
            resilience_class=("устойчивое" if resilience >= RESILIENT else
                              "умеренное" if resilience >= MODERATE else "уязвимое"),
            significance=significance, own_revenue_share=own_share,
            expected_2030=expected, weight=significance * expected,
        ))
    top = max(r["weight"] for r in out) or 1.0
    for r in out:
        r["weight_norm"] = r["weight"] / top
    return out


def _series(m: dict, cid: str, key: str, shares: dict) -> dict:
    hist = m["panel"].get((cid, key), {})
    city = m["cities"][cid]
    scen = {s["key"]: {y: _to_unit(key, city["proj"][s["key"]][y][key]) for y in PROJ_YEARS}
            for s in SCENARIOS}
    expected = {y: sum(shares[s] * scen[s][y] for s in scen) for y in PROJ_YEARS}
    base_value = (_to_unit(key, city["state0"][key]) if key in city["state0"] else None)
    if hist:
        history = {y: v for y, (v, _) in sorted(hist.items())}
        sources = {y: src for y, (_, src) in hist.items()}
    else:   # показателя нет в панели: модельная история по фактической активности
        history = {y: _to_unit(key, st[key]) for y, st in city["history"].items() if key in st}
        sources = {y: "модель" for y in history}
    if key in ("effect", "background"):
        scen = {s: {y: 100.0 * v for y, v in vals.items()} for s, vals in scen.items()}
        expected = {y: 100.0 * v for y, v in expected.items()}
        history = {y: 100.0 * v for y, v in history.items()}
        base_value = 0.0
    return dict(history=history, sources=sources, base=base_value,
                scenarios=scen, expected=expected)


def municipal(city: str = None) -> dict:
    """Муниципальный слой целиком: консорциум, города, предприятия, детали города."""
    m = _model()
    ents = enterprises_view(m)
    by_city = {}
    for e in ents:
        by_city.setdefault(e["city_id"], []).append(e)
    cities = []
    for cid, c in m["cities"].items():
        info = rosatom.CITIES[cid]
        ce = city_enterprises(cid)
        shares = _city_shares(ce, m["fits"])
        st0 = c["state0"]
        horizon = {}
        for s in SCENARIOS:
            horizon[s["key"]] = {}
            for year in MARKS:
                st = c["proj"][s["key"]][year]
                horizon[s["key"]][year] = dict(
                    effect=st["effect"], effect_class=effect_class(st["effect"], year - pmo.BASE_YEAR),
                    background=st["background"],
                    population=st["population"], employees=st["employees"],
                    budget_balance=st["budget_balance"], tax_revenue=st["tax_revenue"],
                    transfers=st["transfers"], interbudget_net=st["interbudget_net"],
                    payroll=st["payroll"], emissions=st["emissions"])
        expected = {year: sum(shares[s["key"]] * horizon[s["key"]][year]["effect"] for s in SCENARIOS)
                    for year in MARKS}
        top = max(ce, key=lambda e: e["headcount"])
        cities.append(dict(
            id=cid, name=info["name"], region=info["region"], zato=info["zato"],
            enterprises=[dict(id=e["id"], short=e["short"]) for e in ce],
            shares=shares, horizon=horizon, expected_effect=expected,
            expected_class={y: effect_class(v, y - pmo.BASE_YEAR) for y, v in expected.items()},
            dependence=st0["enterprises"][top["id"]]["headcount"] / st0["employees"],
            transfer_dependence=st0["transfers"] / st0["budget_revenue"],
            ent_own_share=(st0["ndfl_local_ent"] + st0["land"] + st0["env_fee"]) / st0["tax_revenue"],
            resilience=sum(e["resilience"] * e["significance"] for e in by_city[cid])
            / sum(e["significance"] for e in by_city[cid]),
            base=dict(population=st0["population"], employees=st0["employees"],
                      payroll=st0["payroll"], tax_revenue=st0["tax_revenue"],
                      transfers=st0["transfers"], budget_balance=st0["budget_balance"],
                      budget_expenditure=st0["budget_expenditure"],
                      interbudget_net=st0["interbudget_net"], emissions=st0["emissions"]),
        ))
    cities.sort(key=lambda c: -c["dependence"])

    cid = city if city in m["cities"] else cities[0]["id"]
    c = m["cities"][cid]
    detail_shares = next(x["shares"] for x in cities if x["id"] == cid)
    ce = city_enterprises(cid)
    panel_hist = lambda key: pmo.series(m["panel"], cid, key)
    act_city = {y: sum(m["paths"][e["id"]]["history"].get(y, 1.0) * e["payroll"] for e in ce)
                / sum(e["payroll"] for e in ce) for y in pmo.YEARS}
    st0 = c["state0"]

    def budget(st):
        return dict(ndfl_ent=st["ndfl_local_ent"] / 1e3,
                    ndfl_other=(st["ndfl_local"] - st["ndfl_local_ent"]) / 1e3,
                    land=st["land"] / 1e3, env_fee=st["env_fee"] / 1e3,
                    other=st["other_own"] / 1e3, transfers=st["transfers"] / 1e3,
                    expenditure=st["budget_expenditure"] / 1e3)

    weights = {e["id"]: e["payroll"] for e in ce}
    wsum = sum(weights.values())
    activity_scenarios = {s["key"]: {y: sum(m["paths"][eid][s["key"]][y] * w for eid, w in weights.items()) / wsum
                                     for y in PROJ_YEARS} for s in SCENARIOS}
    activity_fitted = {y: sum(m["fits"][eid]["fitted"].get(y, 1.0) * w for eid, w in weights.items()) / wsum
                       for y in pmo.YEARS}
    detail = dict(
        id=cid, name=rosatom.CITIES[cid]["name"], shares=detail_shares,
        activity_scenarios=activity_scenarios, activity_fitted=activity_fitted,
        series={ind["key"]: _series(m, cid, ind["key"], detail_shares) for ind in INDICATORS},
        activity_city=act_city,
        elasticity=dict(
            employment=_elasticity(act_city, panel_hist("employees")),
            employment_model=st0["employees_ent"] / st0["employees"] * ETA_EMPLOYMENT
            * (1 + LOCAL_MULTIPLIER),
            budget=_elasticity(panel_hist("payroll"), panel_hist("ndfl_local"))),
        budget={"2024": budget(st0), **{f"{s['key']}-{y}": budget(c["proj"][s["key"]][y])
                                        for s in SCENARIOS for y in MARKS}},
        interbudget={"2024": dict(transfers=st0["transfers"] / 1e3,
                                  region=st0["region_receipts"] / 1e3,
                                  net=st0["interbudget_net"] / 1e3)},
    )

    return dict(
        base_year=pmo.BASE_YEAR, years=pmo.YEARS, proj_years=PROJ_YEARS, marks=list(MARKS),
        catalog=INDICATORS, scenarios=SCENARIOS, consortium=consortium.structure(),
        provenance=pmo.provenance(m["panel"]),
        cities=cities, enterprises=ents, city=detail,
        params=dict(eta_employment=ETA_EMPLOYMENT, eta_wage=ETA_WAGE,
                    multiplier=LOCAL_MULTIPLIER, migration=MIGRATION_ELASTICITY,
                    damping=DAMPING, band=GROWTH_BAND, resilient=RESILIENT,
                    moderate=MODERATE, capacity=CAPACITY),
    )
