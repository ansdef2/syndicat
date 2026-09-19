# -*- coding: utf-8 -*-
"""Система индексации заработной платы в локальной корпоративной среде.

Опирается на все предыдущие слои: защитный контур берёт индекс
потребительских цен, производительный - прирост базы часа b_j(t), который
уже прошёл сглаживание Хольта и ограничитель ±2%, персональный - фактическую
эмиссию ТЧЧ работника относительно средней по разряду.

    ι_защ  = π                                  (ст. 134 ТК РФ, обязателен)
    ι_пр   = θ · max(0; Δb_j − π)               участие в приросте базы часа
    ι_перс = clip(ζ · (e_i/ē − 1); ±0,08)       индивидуальная выработка
    ι_i    = clip(ι_защ + ι_пр + ι_перс; π; 0,25)

Бюджетное ограничение шага индексации:

    Σ_i W_i · ι_i ≤ F = φ · S_пред + ΔВДС

Если фонд меньше потребности, урезается только надтарифная часть
(производительный и персональный контуры), защитный контур не урезается
никогда: это требование трудового законодательства, а не параметр модели.
"""

from .constants import (INDEX_CAP, INDEX_STEP_MONTHS, PERSONAL_CAP, PHI, THETA,
                        ZETA)
from .enterprises import BY_ID, personnel_profile, profile
from .tokens import calibrate, skill_coef

# Демонстрационный ИПЦ: Росстат, годовой прирост потребительских цен.
DEFAULT_CPI = 0.074


def base_growth(code: str, phi: float = PHI, months: int = INDEX_STEP_MONTHS) -> float:
    """Δb_j за шаг индексации по траектории базы часа с ограничителем ±2%."""
    path = calibrate(phi)["industries"][code]["path"]
    if len(path) <= months:
        months = len(path) - 1
    return path[-1]["base"] / path[-1 - months]["base"] - 1.0


def performance_ratio(grade: int, avg_grade: float, oee: float, quality: float) -> float:
    """e_i/ē - отношение индивидуальной выработки к средней по предприятию.

    Разряд уже оплачен тарифом, поэтому в персональный контур входит только
    то, что сверх тарифа: загрузка оборудования и качество сдачи с первого раза.
    """
    grade_gap = skill_coef(grade) / skill_coef(round(avg_grade))
    return grade_gap ** 0.25 * (oee / 0.75) ** 0.5 * (quality / 0.975) ** 2


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def indexation(ent_id: str, cpi: float = DEFAULT_CPI, theta: float = THETA,
               zeta: float = ZETA, phi: float = PHI) -> dict:
    """Шаг индексации по предприятию: по разрядам, с бюджетным ограничением."""
    ent = BY_ID[ent_id]
    prof = profile(ent_id, phi)
    delta_b = base_growth(ent["cls"], phi)
    productive = theta * max(0.0, delta_b - cpi)

    groups = []
    for row in personnel_profile(ent):
        ratio = performance_ratio(row["grade"], ent["avg_grade"], ent["oee"], ent["quality"])
        personal = clip(zeta * (ratio - 1.0), -PERSONAL_CAP, PERSONAL_CAP)
        total = clip(cpi + productive + personal, cpi, INDEX_CAP)
        groups.append(dict(
            grade=row["grade"], headcount=row["headcount"], wage_month=row["wage_month"],
            protective=cpi, productive=productive, personal=personal,
            index_raw=total, performance=ratio,
            cost_raw=row["headcount"] * row["wage_month"] * total,
        ))

    need = sum(g["cost_raw"] for g in groups)
    protected_need = sum(g["headcount"] * g["wage_month"] * cpi for g in groups)
    # Фонд шага: социализируемый прибавочный продукт за период индексации
    fund = prof["socialised_month"] * INDEX_STEP_MONTHS / 12.0 * 12.0 / INDEX_STEP_MONTHS
    fund = prof["socialised_month"]          # месячный фонд против месячного ФОТ
    above_fund = max(0.0, fund - protected_need)
    above_need = max(0.0, need - protected_need)
    scale = 1.0 if above_need <= above_fund else (above_fund / above_need if above_need else 0.0)

    for g in groups:
        above = max(0.0, g["index_raw"] - cpi)
        g["index"] = cpi + above * scale
        g["scaled"] = scale < 1.0
        g["wage_new"] = g["wage_month"] * (1 + g["index"])
        g["cost"] = g["headcount"] * g["wage_month"] * g["index"]

    payroll = sum(g["headcount"] * g["wage_month"] for g in groups)
    cost = sum(g["cost"] for g in groups)
    return dict(
        enterprise=prof["enterprise"], cpi=cpi, theta=theta, zeta=zeta, phi=phi,
        base_growth=delta_b, productive=productive, step_months=INDEX_STEP_MONTHS,
        groups=groups, payroll_month=payroll, cost_month=cost,
        cost_share=cost / payroll if payroll else 0.0,
        fund_month=fund, need_month=need, protected_need=protected_need,
        scale=scale, constrained=scale < 1.0,
        deficit=max(0.0, protected_need - fund),
        weighted_index=cost / payroll if payroll else 0.0,
        real_gain=(cost / payroll - cpi) if payroll else 0.0,
        tokens_month=prof["tokens_month"], B=prof["B"],
        payroll_in_tokens=payroll / prof["B"] if prof["B"] else 0.0,
    )


def network_indexation(cpi: float = DEFAULT_CPI, theta: float = THETA,
                       zeta: float = ZETA, phi: float = PHI) -> dict:
    """Свод по всем предприятиям реестра - для сравнительной диаграммы."""
    rows = []
    for ent in BY_ID.values():
        r = indexation(ent["id"], cpi, theta, zeta, phi)
        rows.append(dict(
            id=ent["id"], name=ent["name"], cls=ent["cls"], size=ent["size"],
            okved=ent["okved"], index=r["weighted_index"], cpi=cpi,
            real_gain=r["real_gain"], constrained=r["constrained"],
            cost_month=r["cost_month"], payroll_month=r["payroll_month"],
            fund_month=r["fund_month"], base_growth=r["base_growth"],
            headcount=ent["headcount"],
        ))
    rows.sort(key=lambda r: -r["index"])
    return dict(cpi=cpi, theta=theta, zeta=zeta, phi=phi, rows=rows)
