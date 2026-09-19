# -*- coding: utf-8 -*-
"""Аналитические витрины: сводка сети, сравнение генерации ТЧЧ, каналы.

Количественные и качественные показатели генерации приводятся к единой
шкале «сеть = 100», чтобы их можно было сравнивать на одной оси: разные
единицы измерения на двух осях одной диаграммы - ошибка чтения, а не стиль.
"""

import math

from . import industries as ind
from .constants import (ANCHOR_NOTE, NATIONAL_WAGE_ANCHOR, RHO,
                        TOKEN_INDEX_CORRIDOR, TOKEN_INDEX_TARGET)
from .enterprises import ENTERPRISES, list_enterprises
from .pricing import (direct_labour_vector, external_intensity,
                      full_labour_content, leontief, phi_adjustment,
                      shock_contributions)
from .tokens import calibrate

# Качественные веса композитного индекса генерации
QUALITY_WEIGHTS = dict(quality=0.30, oee=0.25, grade=0.20, cycle=0.10, localization=0.15)


def _index_to_mean(values):
    mean = sum(values) / len(values) if values else 1.0
    return [100.0 * v / mean if mean else 0.0 for v in values]


def industry_table(phi: float = None) -> list:
    """Таблица по классам ОКВЭД: база часа, k_j, μ_j, трудоёмкость, экстерналии."""
    calib = calibrate() if phi is None else calibrate(phi)
    l, L = direct_labour_vector(), leontief()
    h = full_labour_content(l, L)
    ext = external_intensity(l, L)
    rows = []
    for i, code in enumerate(ind.CODES):
        r = calib["industries"][code]
        rows.append(dict(
            code=code, name=r["name"], short=r["short"],
            w_hour=r["w_hour"], vds_hour=r["vds_hour"], s_raw=r["s_raw"],
            s_smooth=r["s_smooth"], base=r["base"], k=r["k"], mu=r["mu"],
            labour_share=r["labour_share"], capital_share=r["capital_share"],
            depreciation_share=r["depreciation_share"],
            l_direct=l[i] * 1000.0, h_full=h[i] * 1000.0,
            multiplier=h[i] / l[i] if l[i] else 0.0,
            cycle_days=r["cycle_days"], k_cycle=r["k_cycle"],
            external=ext[code], hours_share=r["hours_share"],
            elasticities={meta["key"]: ind.ELASTICITIES[code][j]
                          for j, meta in enumerate(ind.EXTERNALITIES)},
        ))
    return rows


def token_index(phi: float = None) -> dict:
    """Индекс токен-цен и состояние контура эмиссии."""
    calib = calibrate() if phi is None else calibrate(phi)
    steps = [row["step_month"] for row in calib["industries"].values()]
    weighted = sum(calib["industries"][c]["hours_share"] * calib["industries"][c]["step_month"]
                   for c in ind.CODES)
    # Индекс токен-цен: отношение фактического шага базы к нормативному допуску
    index = 1.0 + weighted - RHO / 12.0
    return dict(index=index, target=TOKEN_INDEX_TARGET, corridor=TOKEN_INDEX_CORRIDOR,
                step_month=weighted, in_corridor=abs(index - TOKEN_INDEX_TARGET) <= TOKEN_INDEX_CORRIDOR,
                phi_next=phi_adjustment(index, calib["phi"]),
                step_min=min(steps), step_max=max(steps))


def overview(phi: float = None) -> dict:
    """Витрина «Обзор сети»."""
    calib = calibrate() if phi is None else calibrate(phi)
    rows = industry_table(phi)
    ents = list_enterprises(phi)
    tokens_month = sum(e["tokens_month"] for e in ents)
    hours_month = sum(e["hours_month"] for e in ents)
    payroll = sum(e["payroll_month"] for e in ents)
    B = calib["B"]
    labour_part = sum(r["hours_share"] * r["w_hour"] for r in rows)
    return dict(
        B=B, phi=calib["phi"], months=calib["months"],
        labour_part=labour_part, social_part=B - labour_part,
        anchor_wage=NATIONAL_WAGE_ANCHOR, anchor_note=ANCHOR_NOTE,
        industries=rows, token_index=token_index(phi),
        enterprises=len(ents),
        enterprises_large=sum(1 for e in ents if e["size"] == "крупное"),
        enterprises_medium=sum(1 for e in ents if e["size"] == "среднее"),
        hours_month=hours_month, tokens_month=tokens_month,
        tokens_rub_month=tokens_month * B, payroll_month=payroll,
        headcount=sum(e["headcount"] for e in ents),
        tokens_per_hour=tokens_month / hours_month if hours_month else 0.0,
        # Правило эмиссии ограничивает ПРИРОСТ массы, а не её уровень:
        # ΔM ≤ ΔQ·(1 + ρ). При неизменном выпуске в нормо-часах допустимый
        # месячный прирост сводится к технической ликвидности ρ/12.
        emission_growth_cap=tokens_month * RHO / 12.0,
        emission_rule="ΔM_ТЧЧ ≤ ΔQ_нормо-часов · (1 + ρ), ρ = 1,5% годовых",
    )


def generation(phi: float = None) -> dict:
    """Витрина «Генерация ТЧЧ»: количественные и качественные показатели.

    Количественный показатель - интенсивность эмиссии, ТЧЧ на отработанный
    человеко-час. Качественный - композит из качества сдачи, OEE, сложности,
    длительности цикла и глубины локализации. Оба приводятся к «сеть = 100».
    """
    ents = list_enterprises(phi)
    by_id = {e["id"]: e for e in ENTERPRISES}
    calib = calibrate() if phi is None else calibrate(phi)

    quant_raw, qual_raw = [], []
    for e in ents:
        src = by_id[e["id"]]
        row = calib["industries"][e["cls"]]
        quant_raw.append(e["tokens_per_hour"])
        qual = (QUALITY_WEIGHTS["quality"] * (src["quality"] / 0.975)
                + QUALITY_WEIGHTS["oee"] * (src["oee"] / 0.75)
                + QUALITY_WEIGHTS["grade"] * (src["avg_grade"] / 5.2)
                + QUALITY_WEIGHTS["cycle"] * row["k_cycle"]
                + QUALITY_WEIGHTS["localization"] * (src["localization"] / 0.90))
        qual_raw.append(qual)

    quant_idx = _index_to_mean(quant_raw)
    qual_idx = _index_to_mean(qual_raw)

    rows = []
    for i, e in enumerate(ents):
        src = by_id[e["id"]]
        rows.append(dict(
            id=e["id"], name=e["name"], short=e["short"], cls=e["cls"],
            okved=e["okved"], size=e["size"], industry_short=e["industry_short"],
            headcount=e["headcount"], focus=e["focus"],
            hours_month=e["hours_month"], tokens_month=e["tokens_month"],
            tokens_rub=e["tokens_rub"], tokens_per_hour=e["tokens_per_hour"],
            tokens_per_worker=e["tokens_month"] / e["headcount"],
            quantitative=quant_idx[i], qualitative=qual_idx[i],
            gap=quant_idx[i] - qual_idx[i],
            quality=src["quality"], oee=src["oee"], avg_grade=src["avg_grade"],
            localization=src["localization"], k=e["k"],
            vds_per_hour=e["vds_per_hour"],
        ))
    rows.sort(key=lambda r: -r["quantitative"])

    # агрегат по классам ОКВЭД
    per_class = {}
    for r in rows:
        agg = per_class.setdefault(r["cls"], dict(cls=r["cls"], short=r["industry_short"],
                                                  tokens=0.0, hours=0.0, count=0,
                                                  quality=0.0, oee=0.0))
        agg["tokens"] += r["tokens_month"]
        agg["hours"] += r["hours_month"]
        agg["count"] += 1
        agg["quality"] += r["quality"]
        agg["oee"] += r["oee"]
    for agg in per_class.values():
        agg["quality"] /= agg["count"]
        agg["oee"] /= agg["count"]
        agg["intensity"] = agg["tokens"] / agg["hours"] if agg["hours"] else 0.0

    return dict(rows=rows, weights=QUALITY_WEIGHTS,
                classes=sorted(per_class.values(), key=lambda a: a["cls"]),
                B=calib["B"])


def smoothing_view(code: str = "28", phi: float = None) -> dict:
    """Витрина «Сглаживание»: ряд наблюдений, уровень, тренд, база и коридор."""
    calib = calibrate() if phi is None else calibrate(phi)
    from .constants import ALPHA, ALPHA_HALFLIFE, BETA, BETA_HALFLIFE, MAX_STEP
    row = calib["industries"][code]
    path = []
    for i, p in enumerate(row["path"]):
        prev = row["path"][i - 1]["base"] if i else p["base"]
        path.append(dict(month=p["month"], observation=p["observation"],
                         level=p["level"], trend=p["trend"],
                         forecast=p["level"] + p["trend"],
                         wage_hour=p["wage_hour"], base=p["base"], base_raw=p["base_raw"],
                         corridor_low=prev * (1 - MAX_STEP), corridor_high=prev * (1 + MAX_STEP),
                         clipped=abs(p["base"] - p["base_raw"]) > 1e-9))
    return dict(code=code, name=row["name"], short=row["short"], path=path,
                alpha=ALPHA, beta=BETA, alpha_halflife=ALPHA_HALFLIFE,
                beta_halflife=BETA_HALFLIFE, max_step=MAX_STEP, phi=calib["phi"],
                s_raw=row["s_raw"], s_smooth=row["s_smooth"], base=row["base"],
                w_hour=row["w_hour"], k=row["k"], mu=row["mu"],
                clipped_months=sum(1 for p in path if p["clipped"]),
                codes=[dict(code=c, short=ind.short(c)) for c in ind.CODES])


# --- канал субститутов (раздел 6 спецификации) ------------------------------
CHANNEL = dict(
    key="22.21.21", title="Трубы напорные Dy 100-110",
    note=("Квантили по состоявшимся сделкам сети за 30 суток. "
          "В окне 14 независимых продавцов - публикация разрешена (k ≥ 5, T+1)."),
    sellers=14,
    items=[
        dict(name="Труба ПЭ100 SDR17 d110", origin="ОКВЭД 22.21 · полиэтилен",
             p10=366, p25=389, med=412, p75=441, p90=478, sigma=1.00, loc=0.94),
        dict(name="Труба ПП-R PN10 d110", origin="ОКВЭД 22.21 · полипропилен",
             p10=421, p25=443, med=468, p75=498, p90=535, sigma=0.87, loc=0.91),
        dict(name="Труба ВГП оцинк. Dy100", origin="ОКВЭД 25.21 · сталь",
             p10=612, p25=648, med=690, p75=748, p90=812, sigma=0.61, loc=0.97),
        dict(name="Труба ВЧШГ Dy100", origin="ОКВЭД 24.51 · чугун",
             p10=1020, p25=1075, med=1140, p75=1235, p90=1340, sigma=0.44, loc=0.99),
    ],
    rules=[
        "k-анонимность: не менее пяти независимых продавцов в окне",
        "Задержка T+1: цен в реальном времени нет",
        "Только состоявшиеся сделки: плановых цен в схеме сообщения нет",
        "Идентификаторов продавцов в публичных топиках нет",
        "Дифференциально-приватный шум на P10 и P90",
    ],
)


def channel_view(phi: float = None) -> dict:
    data = dict(CHANNEL)
    data["shock"] = shock_contributions("22", dict(energy=0.12, fx=0.08))
    data["shock_percent"] = 100.0 * (math.exp(sum(r["contribution"] for r in data["shock"])) - 1.0)
    return data


def shock_table(factors: dict, phi: float = None) -> list:
    """Реакция цены по всем классам на один и тот же сценарий экстерналий."""
    out = []
    for code in ind.CODES:
        rows = shock_contributions(code, factors)
        dlog = sum(r["contribution"] for r in rows)
        out.append(dict(code=code, short=ind.short(code),
                        percent=100.0 * (math.exp(dlog) - 1.0), factors=rows))
    return out
