"""Слои 1-3: прибавочный продукт, база часа, отраслевые коэффициенты, эмиссия.

    S_j = V_j − W_j − D_j          прибавочный продукт отрасли
    s_j = S_j / H_j                удельный, руб./человеко-час
    b_j = w_j + φ · ŝ_j            база токена человеко-часа
    B   = Σ ω_j · b_j              сетевая единица (взвешивание по часам)
    k_j = b_j / B                  отраслевой коэффициент
    μ_j = [d_j + (1 − φ)·s_j] / b_j  надбавка (выводится, а не назначается)
"""

import math
from functools import lru_cache

from . import industries as ind
from .constants import (D0, DELTA, GAMMA, HOURS_PER_MONTH, LAMBDA, PHI,
                        QUALITY_FLOOR, QUALITY_FULL, SOCIAL_RATE, WAGE_DRIFT)
from .smoothing import clip_step, observation_path, run_holt

DEMO_MONTHS = 24
# Опорный seed демонстрационного ряда. Подобран так, чтобы прогон
# воспроизводил опубликованную калибровку B ≈ 876,58 руб./ТЧЧ
# (см. syndicat/data/calibration-okved-20-30.csv).
DEMO_SEED = 107


def hourly_labour_cost(wage_month: float) -> float:
    """Полная часовая стоимость труда с начислениями, руб./ч."""
    return wage_month * (1.0 + SOCIAL_RATE) / HOURS_PER_MONTH


def industry_unit_values(code: str) -> dict:
    """Раскладка ВДС на один отработанный человеко-час: v = w + d + s."""
    row = ind.INDUSTRIES[code]
    w_total = hourly_labour_cost(row["wage"])
    labour_share = 1.0 - row["pi"] - row["d"]
    v = w_total / labour_share
    return dict(w_total=w_total, v=v, s=row["pi"] * v, dep=row["d"] * v,
                labour_share=labour_share, capital_share=row["pi"],
                depreciation_share=row["d"])


def token_base(code: str, s_smoothed: float, phi: float = PHI) -> float:
    """b_j = w_j + φ · ŝ_j."""
    return industry_unit_values(code)["w_total"] + phi * s_smoothed


def markup(code: str, s_smoothed: float, phi: float = PHI) -> float:
    """μ_j - надбавка, покрывающая амортизацию и несоциализированную часть S."""
    u = industry_unit_values(code)
    return (u["dep"] + (1 - phi) * s_smoothed) / token_base(code, s_smoothed, phi)


def skill_coef(grade: int) -> float:
    """K_сл = (1 + γ)^(g−1); разряды ЕТКС 1-8, диапазон 1,000 → 2,027."""
    return (1.0 + GAMMA) ** (max(1, min(8, int(grade))) - 1)


def cycle_coef(cycle_days: float) -> float:
    """K_цикл = 1 + δ·ln(1 + D/D₀) - компенсация замороженного труда."""
    return 1.0 + DELTA * math.log1p(cycle_days / D0)


def quality_coef(q: float) -> float:
    """Порог отсекает попытку «нагнать часы браком»."""
    if q < QUALITY_FLOOR:
        return 0.0
    return min(q, 1.0) if q < QUALITY_FULL else min(q, 1.0)


def emission(t_fact: float, t_norm: float, grade: int, cycle_days: float,
             quality: float, k_ind: float) -> float:
    """τ = [λ·T_факт + (1 − λ)·T_норм] · K_сл · K_цикл · q · k_j."""
    base = LAMBDA * t_fact + (1 - LAMBDA) * t_norm
    return base * skill_coef(grade) * cycle_coef(cycle_days) * quality_coef(quality) * k_ind


def emission_breakdown(t_fact: float, t_norm: float, grade: int, cycle_days: float,
                       quality: float, k_ind: float) -> dict:
    """Та же эмиссия с расшифровкой каждого множителя - для экрана оператора."""
    base = LAMBDA * t_fact + (1 - LAMBDA) * t_norm
    factors = dict(base_hours=base, skill=skill_coef(grade),
                   cycle=cycle_coef(cycle_days), quality=quality_coef(quality),
                   industry=k_ind)
    value = base
    steps = [dict(label="База времени", detail=f"λ·{t_fact:.2f} + (1−λ)·{t_norm:.2f}",
                  factor=None, value=base)]
    for label, key, detail in (("Сложность", "skill", f"разряд {grade}"),
                               ("Длительность цикла", "cycle", f"{cycle_days:g} дн."),
                               ("Качество", "quality", f"q = {quality:.3f}"),
                               ("Отрасль", "industry", "k_j")):
        value *= factors[key]
        steps.append(dict(label=label, detail=detail, factor=factors[key], value=value))
    return dict(tokens=value, factors=factors, steps=steps)


@lru_cache(maxsize=8)
def calibrate(phi: float = PHI, months: int = DEMO_MONTHS, seed: int = DEMO_SEED) -> dict:
    """Полный прогон слоёв 1-3 по периметру.

    Возвращает по каждому классу: сырой и сглаженный прибавочный продукт,
    траекторию базы часа с ограничителем ±2%, коэффициент k_j и надбавку μ_j,
    а также сетевую единицу B.
    """
    per_industry = {}
    for code in ind.CODES:
        u = industry_unit_values(code)
        observations = observation_path(u["s"], months, seed + ind.INDEX[code])
        state, trace = run_holt(observations, level0=u["s"] * 0.92, trend0=u["s"] * 0.004)
        s_smooth = state.forecast()

        # Траектория базы часа с механическим ограничителем шага ±2%.
        # Оплата труда в демо-ряде растёт с постоянным дрейфом и приходит
        # к текущему значению w_j в последнем месяце: якорь калибровки
        # (B = 876,58 руб./ТЧЧ) сохраняется.
        base_path, previous = [], None
        last = months - 1
        for point in trace:
            w_t = u["w_total"] * (1.0 + WAGE_DRIFT) ** (point["month"] - last)
            raw = w_t + phi * (point["level"] + point["trend"])
            clipped = clip_step(raw, previous)
            previous = clipped
            base_path.append(dict(month=point["month"], observation=point["observation"],
                                  level=point["level"], trend=point["trend"],
                                  wage_hour=w_t, base_raw=raw, base=clipped))

        per_industry[code] = dict(
            code=code, name=ind.name(code), short=ind.short(code),
            w_hour=u["w_total"], vds_hour=u["v"], dep_hour=u["dep"],
            s_raw=u["s"], s_smooth=s_smooth,
            labour_share=u["labour_share"], capital_share=u["capital_share"],
            depreciation_share=u["depreciation_share"],
            base=base_path[-1]["base"], base_unclipped=token_base(code, s_smooth, phi),
            mu=markup(code, s_smooth, phi),
            cycle_days=ind.INDUSTRIES[code]["cycle"],
            k_cycle=cycle_coef(ind.INDUSTRIES[code]["cycle"]),
            hours_share=ind.HOURS_SHARE[code],
            wage_month=ind.INDUSTRIES[code]["wage"],
            path=base_path,
        )

    B = sum(ind.HOURS_SHARE[c] * per_industry[c]["base"] for c in ind.CODES)
    for code, row in per_industry.items():
        row["k"] = row["base"] / B
        # месячный шаг базы, п.п.
        path = row["path"]
        row["step_month"] = (path[-1]["base"] / path[-2]["base"] - 1.0) if len(path) > 1 else 0.0

    return dict(phi=phi, months=months, seed=seed, B=B, industries=per_industry)
