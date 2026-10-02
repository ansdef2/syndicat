# -*- coding: utf-8 -*-
"""Территориальный контур: сетка предприятий группы и вклад в экономику городов.

Модель периметра переносится на сетку взаимосвязанных предприятий одной группы
(здесь - Госкорпорация «Росатом», данные в rosatom.py) и на города, где они
расположены. Ничего нового в формулах нет - те же слои, применённые к другому
уровню агрегации:

  Слой 1   V_e = W_e + D_e + S_e           по каждому предприятию, S - остаток
  Слои 2-3 b_j, k_j, μ_j                   из калибровки (классы вне периметра -
                                           той же формулой, без входа в B)
  Слой 4   эмиссия ТЧЧ предприятия         как в реестре периметра
  Слой 5   h = l·(I − A_гр)⁻¹              полные трудозатраты по сетке группы,
           p_e = Σ_m h_me·b_m(1+μ_m) + E_e  цена производства рубля выпуска,
           R_e = 1 − p_e                    рента предприятия
  Слой 6   ценовой шок по внешним продажам; фонды подстраиваются с тем же
           ограничителем шага ±2% в месяц, что и база часа
  Слой 7   индексация зарплаты по трём контурам против фонда φ·S

Вклад в экономику города (₽ в месяц):
  чистые доходы работников  = ФОТ·(1 − НДФЛ)
  бюджет городского округа  = ФОТ·НДФЛ·норматив
  местные закупки           = внешние закупки·доля размещения в городе
  территориальный фонд      = (1 − φ)·S·доля территории по уставу

Модель управления финансовыми активами территории раскладывает добавленную
стоимость городских предприятий на фонды: амортизационный (D), социализируемый
(φ·S - индексация и часы), развития, территориальный и резерв ((1 − φ)·S
по уставным долям) - и проверяет, покрывает ли φ·S потребность индексации.
"""

from .. import linalg
from . import industries as ind
from . import rosatom
from .constants import (ACCEPTANCE_CAP, CITY_FORMING_THRESHOLD, DEVELOPMENT_SHARE,
                        EMPLOYED_SHARE, LOCAL_NDFL_SHARE, LOCAL_PURCHASE_SHARE, MAX_STEP,
                        NDFL_RATE, PHI, SOCIAL_RATE, TERRITORY_SHARE)
from .enterprises import profile, register
from .indexation import DEFAULT_CPI, indexation
from .smoothing import clip_step
from .tokens import calibrate, industry_row

register(rosatom.ENTERPRISES)

ENTS = rosatom.ENTERPRISES
IDX = {e["id"]: i for i, e in enumerate(ENTS)}
DIV_NAME = {d["key"]: d["name"] for d in rosatom.DIVISIONS}
DIV_SHORT = {d["key"]: d["short"] for d in rosatom.DIVISIONS}
RESERVE_SHARE = 1.0 - DEVELOPMENT_SHARE - TERRITORY_SHARE


def flows() -> list:
    """Внутригрупповые поставки в рублях за год по базовым ценам."""
    out = []
    for ent in ENTS:
        for p in ent["products"]:
            for consumer, units, kind in p["supplies"]:
                out.append(dict(source=ent["id"], target=consumer, sku=p["sku"],
                                product=p["name"], unit=p["unit"], units=units, kind=kind,
                                value=units * p["market_price"]))
    return out


def _sales(ent: dict, shock: float) -> dict:
    """Выпуск предприятия: внутри группы, на внешний рынок, в том числе экспорт.

    Ценовой шок действует только на внешние продажи: внутригрупповые
    поставки идут по базовым ценам.
    """
    internal = external = export = base_external = 0.0
    lines = []
    for p in ent["products"]:
        units_in = sum(units for _, units, _ in p["supplies"])
        if units_in > p["volume"] + 1e-9:
            raise ValueError(f"{ent['id']}/{p['sku']}: поставки в группу больше выпуска")
        v_in = units_in * p["market_price"]
        v_ext0 = (p["volume"] - units_in) * p["market_price"]
        v_ext = v_ext0 * (1.0 + shock)
        internal += v_in
        external += v_ext
        base_external += v_ext0
        export += v_ext * p.get("export_share", 0.0)
        lines.append(dict(sku=p["sku"], name=p["name"], unit=p["unit"], volume=p["volume"],
                          market_price=p["market_price"], internal_units=units_in,
                          internal=v_in, external=v_ext,
                          conversion=(v_ext / (v_in + v_ext)) if v_in + v_ext else 0.0))
    return dict(internal=internal, external=external, export=export,
                domestic=external - export, output=internal + external,
                output_base=internal + base_external, lines=lines)


def _leontief(base_output: dict, hours_year: dict, phi: float) -> dict:
    """Полные трудозатраты и цена производства по сетке группы.

    A_гр[s][c] - рубли промежуточной продукции предприятия s на рубль выпуска c;
    l_e - собственные человеко-часы на рубль выпуска. Цена человеко-часа донора -
    b_m·(1 + μ_m) его класса: та же величина, что и в цене периметра.
    """
    n = len(ENTS)
    A = [[0.0] * n for _ in range(n)]
    for f in flows():
        if f["kind"] == "intermediate":
            A[IDX[f["source"]]][IDX[f["target"]]] += f["value"] / base_output[f["target"]]
    for j, ent in enumerate(ENTS):
        col = sum(A[i][j] for i in range(n))
        if col > 1.0 - ind.ALL_INDUSTRIES[ent["cls"]]["psi"] + 1e-9:
            raise ValueError(f"{ent['id']}: внутригрупповые закупки больше промежуточного потребления")

    L = linalg.leontief_inverse(A)
    l = [hours_year[e["id"]] / base_output[e["id"]] for e in ENTS]
    calib = calibrate(phi)
    rate = []
    for e in ENTS:
        row = industry_row(calib, e["cls"])
        rate.append(row["base"] * (1.0 + row["mu"]))
    e_direct = [1.0 - ind.ALL_INDUSTRIES[e["cls"]]["psi"] - sum(A[i][j] for i in range(n))
                for j, e in enumerate(ENTS)]

    out = {}
    for c, ent in enumerate(ENTS):
        donors = [l[m] * L[m][c] for m in range(n)]
        full = sum(donors)
        labour = sum(donors[m] * rate[m] for m in range(n))
        external = sum(e_direct[m] * L[m][c] for m in range(n))
        by_div = {}
        for m, hrs in enumerate(donors):
            by_div[ENTS[m]["division"]] = by_div.get(ENTS[m]["division"], 0.0) + hrs
        out[ent["id"]] = dict(direct=l[c], full=full, multiplier=full / l[c] if l[c] else 0.0,
                              labour_per_rub=labour, external_per_rub=external,
                              price_per_rub=labour + external, rent=1.0 - labour - external,
                              by_division=by_div,
                              donors=sorted(({"id": ENTS[m]["id"], "short": ENTS[m]["short"],
                                              "hours_per_mrub": donors[m] * 1e6}
                                             for m in range(n) if donors[m] > 1e-12),
                                            key=lambda d: -d["hours_per_mrub"]))
    return dict(A=A, out=out)


def smoothed_path(before: float, after: float, months: int = 12,
                  limit: float = MAX_STEP) -> list:
    """Фонд после шока с ограничителем шага ±2% в месяц - тем же, что и у базы часа.

    Фонд не обрушивается вслед за ценой: он идёт к новому уровню не быстрее
    2% в месяц, а разницу закрывает резерв. Если новый уровень неположителен,
    фонд снижается по 2% в месяц, пока шок не будет пересмотрен.
    """
    target = max(after, 0.0)
    value, path = before, []
    for _ in range(months):
        value = clip_step(target, value, limit) if value > 0 else target
        path.append(value)
    return path


def adjust_months(before: float, after: float, limit: float = MAX_STEP):
    """Сколько месяцев фонд идёт к новому уровню; None - уровень недостижим (дефицит)."""
    if before <= 0:
        return 0
    if after <= 0:
        return None
    value, months = before, 0
    while abs(value - after) > 1e-6 * before and months < 600:
        value = clip_step(after, value, limit)
        months += 1
    return months


def grid(phi: float = PHI, shock: float = 0.0, cpi: float = DEFAULT_CPI) -> dict:
    """Сетка предприятий группы: выпуск, тождество V = W + D + S, рента, фонды."""
    calib = calibrate(phi)
    B = calib["B"]
    fl = flows()
    rows, base_output, hours_year = [], {}, {}
    for ent in ENTS:
        prof = profile(ent["id"], phi)
        sales, sales0 = _sales(ent, shock), _sales(ent, 0.0)
        base_output[ent["id"]] = sales0["output"]
        hours_year[ent["id"]] = prof["hours_month"] * 12.0
        params = ind.ALL_INDUSTRIES[ent["cls"]]

        # Слой 1 на уровне предприятия. Промежуточное потребление и затраты
        # труда в краткосрочном периоде не реагируют на ценовой шок: весь шок
        # уходит в добавленную стоимость и в прибавочный продукт S.
        ic = sales0["output"] * (1.0 - params["psi"])
        payroll_year = prof["payroll_month"] / ent["prod_share"] * 12.0   # весь персонал
        W = payroll_year * (1.0 + SOCIAL_RATE)
        D = sales0["output"] * params["psi"] * params["d"]
        V = sales["output"] - ic
        S = V - W - D
        S0 = sales0["output"] - ic - W - D
        internal_in = sum(f["value"] for f in fl if f["target"] == ent["id"] and f["kind"] == "intermediate")
        capital_in = sum(f["value"] for f in fl if f["target"] == ent["id"] and f["kind"] == "capital")
        idx = indexation(ent["id"], cpi=cpi, phi=phi)

        rows.append(dict(
            id=ent["id"], name=ent["name"], short=ent["short"], division=ent["division"],
            division_name=DIV_NAME[ent["division"]], stage=ent["stage"],
            city_id=ent["city_id"], city=rosatom.CITIES[ent["city_id"]]["name"],
            okved=ent["okved"], cls=ent["cls"], industry_short=ind.short(ent["cls"]),
            headcount=ent["headcount"], assets=ent["assets_bn"] * 1e9,
            output=sales["output"], output_base=sales0["output"],
            internal_sales=sales["internal"], external_sales=sales["external"],
            export=sales["export"], domestic=sales["domestic"],
            conversion=sales["external"] / sales["output"] if sales["output"] else 0.0,
            products=sales["lines"],
            intermediate=ic, internal_purchases=internal_in, external_purchases=ic - internal_in,
            capital_received=capital_in,
            V=V, W=W, D=D, S=S, S_base=S0, payroll_year=payroll_year,
            socialised=phi * max(S, 0.0), accumulation=(1.0 - phi) * max(S, 0.0),
            hours_year=hours_year[ent["id"]], tokens_month=prof["tokens_month"],
            tokens_rub_month=prof["tokens_rub"], k=prof["k"],
            vds_per_hour=V / hours_year[ent["id"]],
            industry_vds_hour=industry_row(calib, ent["cls"])["vds_hour"],
            indexation_need_month=idx["cost_month"], indexation_index=idx["weighted_index"],
        ))

    chain = _leontief(base_output, hours_year, phi)
    for r in rows:
        r.update(chain["out"][r["id"]])
        r["full_hours_per_unit"] = [dict(sku=p["sku"], unit=p["unit"],
                                         hours=r["full"] * p["market_price"])
                                    for p in r["products"]]

    internal_turnover = sum(f["value"] for f in fl)
    return dict(rows=rows, flows=fl, B=B, phi=phi, shock=shock, cpi=cpi,
                internal_turnover=internal_turnover,
                clearing_tokens_year=ACCEPTANCE_CAP * internal_turnover / B,
                acceptance_cap=ACCEPTANCE_CAP)


def divisions(rows: list) -> list:
    """Источники доходов и расходов по дивизионам."""
    out = []
    for d in rosatom.DIVISIONS:
        part = [r for r in rows if r["division"] == d["key"]]
        agg = dict(key=d["key"], name=d["name"], short=d["short"], enterprises=len(part))
        for k in ("output", "internal_sales", "external_sales", "export", "domestic",
                  "internal_purchases", "external_purchases", "capital_received",
                  "V", "W", "D", "S", "socialised", "headcount", "assets", "hours_year"):
            agg[k] = sum(r[k] for r in part)
        agg["conversion"] = agg["external_sales"] / agg["output"] if agg["output"] else 0.0
        out.append(agg)
    return out


def _city_rows(rows: list, phi: float) -> list:
    out = []
    for cid, city in rosatom.CITIES.items():
        part = [r for r in rows if r["city_id"] == cid]
        if not part:
            continue
        employed = city["population"] * EMPLOYED_SHARE
        payroll = sum(r["payroll_year"] for r in part) / 12.0
        S = sum(r["S"] for r in part) / 12.0
        S_base = sum(r["S_base"] for r in part) / 12.0
        accumulation = (1.0 - phi) * max(S, 0.0)
        top = max(part, key=lambda r: r["headcount"])

        income = payroll * (1.0 - NDFL_RATE)
        budget = payroll * NDFL_RATE * LOCAL_NDFL_SHARE
        purchases = sum(r["external_purchases"] for r in part) / 12.0 * LOCAL_PURCHASE_SHARE
        territory = accumulation * TERRITORY_SHARE
        contribution = income + budget + purchases + territory

        socialised = phi * max(S, 0.0)
        socialised_base = phi * max(S_base, 0.0)
        need = sum(r["indexation_need_month"] for r in part)
        out.append(dict(
            id=cid, name=city["name"], region=city["region"], zato=city["zato"],
            population=city["population"], employed=employed,
            enterprises=[dict(id=r["id"], short=r["short"], division=r["division"]) for r in part],
            headcount=sum(r["headcount"] for r in part),
            dependence=top["headcount"] / employed,
            group_share=sum(r["headcount"] for r in part) / employed,
            city_forming=top["headcount"] / employed >= CITY_FORMING_THRESHOLD,
            city_forming_name=top["short"],
            payroll_month=payroll, income_month=income, budget_month=budget,
            budget_region_month=payroll * NDFL_RATE * (1.0 - LOCAL_NDFL_SHARE),
            purchases_month=purchases, territory_fund_month=territory,
            capital_month=sum(r["capital_received"] for r in part) / 12.0,
            contribution_month=contribution,
            contribution_per_resident=contribution / city["population"],
            tokens_month=sum(r["tokens_month"] for r in part),
            # модель управления финансовыми активами территории, ₽/мес
            assets=sum(r["assets"] for r in part),
            V_month=sum(r["V"] for r in part) / 12.0,
            W_month=sum(r["W"] for r in part) / 12.0,
            D_month=sum(r["D"] for r in part) / 12.0,
            S_month=S, socialised_month=socialised,
            development_month=accumulation * DEVELOPMENT_SHARE,
            reserve_month=accumulation * RESERVE_SHARE,
            indexation_need_month=need,
            coverage=socialised / need if need else 0.0,
            socialised_base_month=socialised_base,
            adjust_months=adjust_months(socialised_base, socialised),
            smoothed_12=smoothed_path(socialised_base, socialised)[-1],
            reserve_draw_12=sum(v - socialised for v in smoothed_path(socialised_base, socialised)),
            deficit=S < 0,
        ))
    return out


def territories(phi: float = PHI, shock: float = 0.0, cpi: float = DEFAULT_CPI) -> dict:
    """Сводка территориального контура: сетка, дивизионы, города, фонды."""
    g = grid(phi, shock, cpi)
    rows = g["rows"]
    cities = _city_rows(rows, phi)
    total = lambda k: sum(r[k] for r in rows)
    return dict(
        group=rosatom.GROUP, disclaimer=rosatom.DISCLAIMER, B=g["B"], phi=phi,
        shock=shock, cpi=cpi, rows=rows, flows=g["flows"], divisions=divisions(rows),
        cities=cities,
        nodes=[dict(id=r["id"], short=r["short"], division=r["division"], stage=r["stage"],
                    city=r["city"], output=r["output"]) for r in rows],
        divisions_meta=rosatom.DIVISIONS,
        totals=dict(
            enterprises=len(rows), cities=len(cities),
            city_forming=sum(1 for c in cities if c["city_forming"]),
            output=total("output"), revenue=total("external_sales"), export=total("export"),
            internal_turnover=g["internal_turnover"],
            conversion=total("external_sales") / total("output"),
            W=total("W"), D=total("D"), V=total("V"), S=total("S"),
            external_purchases=total("external_purchases"),
            capital_internal=sum(f["value"] for f in g["flows"] if f["kind"] == "capital"),
            headcount=total("headcount"), assets=total("assets"),
            socialised_month=sum(c["socialised_month"] for c in cities),
            contribution_month=sum(c["contribution_month"] for c in cities),
            territory_fund_month=sum(c["territory_fund_month"] for c in cities),
            tokens_month=total("tokens_month"),
            clearing_tokens_year=g["clearing_tokens_year"],
            acceptance_cap=g["acceptance_cap"],
        ),
        params=dict(ndfl=NDFL_RATE, local_ndfl=LOCAL_NDFL_SHARE, employed_share=EMPLOYED_SHARE,
                    local_purchase=LOCAL_PURCHASE_SHARE, threshold=CITY_FORMING_THRESHOLD,
                    development=DEVELOPMENT_SHARE, territory=TERRITORY_SHARE,
                    reserve=RESERVE_SHARE, max_step=MAX_STEP),
    )
