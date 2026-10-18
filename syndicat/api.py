# -*- coding: utf-8 -*-
"""Расчётное API платформы. Каждый обработчик возвращает JSON-совместимый dict."""

import io
from urllib.parse import parse_qs

from .model import (analytics, costing, enterprises, indexation, industries, municipal,
                    pmo, rosatom, territories)
from .model.constants import (ACCEPTANCE_CAP, ALPHA, ALPHA_HALFLIFE, BETA, BETA_HALFLIFE, D0,
                              DELTA, DEVELOPMENT_SHARE, GAMMA, HOURS_PER_MONTH, INDEX_CAP,
                              LAMBDA, MAX_STEP, NATIONAL_WAGE_ANCHOR,
                              PERSONAL_CAP, PHI, PHI_RANGE, QUALITY_FLOOR, RHO,
                              SOCIAL_RATE, TERRITORY_SHARE, THETA, ZETA)


def _f(qs: dict, key: str, default):
    try:
        return float(qs.get(key, [default])[0])
    except (TypeError, ValueError):
        return default


def _s(qs: dict, key: str, default):
    value = qs.get(key, [default])[0]
    return value if value else default


def _factors(qs: dict) -> dict:
    return {meta["key"]: _f(qs, meta["key"], 0.0) for meta in industries.EXTERNALITIES}


def _phi(qs: dict) -> float:
    return min(1.0, max(0.0, round(_f(qs, "phi", PHI), 3)))


# --- обработчики ------------------------------------------------------------

def about(qs):
    """Раздел «О платформе»: ключевые величины и раскладка прибавочного продукта при φ."""
    phi = _phi(qs)
    ov = analytics.overview(phi)
    rest = 1.0 - phi
    return dict(
        B=ov["B"], phi=phi, labour_part=ov["labour_part"], social_part=ov["social_part"],
        industries=len(industries.CODES), enterprises=ov["enterprises"],
        headcount=ov["headcount"],
        shares=dict(workers=phi, development=rest * DEVELOPMENT_SHARE,
                    territory=rest * TERRITORY_SHARE, reserve=rest * territories.RESERVE_SHARE),
        charter=dict(development=DEVELOPMENT_SHARE, territory=TERRITORY_SHARE,
                     reserve=territories.RESERVE_SHARE, acceptance_cap=ACCEPTANCE_CAP,
                     max_step=MAX_STEP, theta=THETA),
        group=dict(name=rosatom.GROUP, enterprises=len(rosatom.ENTERPRISES),
                   cities=len(rosatom.CITIES),
                   zato=sum(1 for c in rosatom.CITIES.values() if c["zato"])),
        municipal=dict(indicators=len(pmo.CATALOG), years=[pmo.YEARS[0], pmo.YEARS[-1]],
                       horizons=list(municipal.MARKS)),
    )


def overview(qs):
    return analytics.overview(_phi(qs))


def generation(qs):
    return analytics.generation(_phi(qs))


def smoothing(qs):
    return analytics.smoothing_view(_s(qs, "code", "28"), _phi(qs))


def industries_view(qs):
    return dict(rows=analytics.industry_table(_phi(qs)),
                externalities=industries.EXTERNALITIES,
                shock=analytics.shock_table(_factors(qs), _phi(qs)))


def enterprises_view(qs):
    phi = _phi(qs)
    return dict(rows=enterprises.list_enterprises(phi),
                disclaimer=enterprises.DISCLAIMER,
                products=costing.products_index())


def enterprise_view(qs):
    ent_id = _s(qs, "id", "livgidromash")
    phi = _phi(qs)
    prof = enterprises.profile(ent_id, phi)
    prof["products_priced"] = [
        costing.dossier(ent_id, p["sku"], None, phi) for p in prof["enterprise"]["products"]
    ]
    prof["indexation"] = indexation.indexation(ent_id, _f(qs, "cpi", indexation.DEFAULT_CPI),
                                               _f(qs, "theta", THETA), _f(qs, "zeta", ZETA), phi)
    return prof


def pricing(qs):
    ent_id = _s(qs, "ent", "livgidromash")
    sku = _s(qs, "sku", "К100-65-200")
    factors = _factors(qs)
    data = costing.dossier(ent_id, sku, factors, _phi(qs))
    data["catalogue"] = costing.products_index()
    data["shock_table"] = analytics.shock_table(factors, _phi(qs))
    return data


def indexation_view(qs):
    ent_id = _s(qs, "ent", "livgidromash")
    cpi = _f(qs, "cpi", indexation.DEFAULT_CPI)
    theta = _f(qs, "theta", THETA)
    zeta = _f(qs, "zeta", ZETA)
    phi = _phi(qs)
    data = indexation.indexation(ent_id, cpi, theta, zeta, phi)
    data["network"] = indexation.network_indexation(cpi, theta, zeta, phi)
    data["registry"] = [dict(id=e["id"], name=e["name"], size=e["size"], cls=e["cls"])
                        for e in enterprises.ENTERPRISES]
    data["params"] = dict(cpi=cpi, theta=theta, zeta=zeta, phi=phi,
                          personal_cap=PERSONAL_CAP, index_cap=INDEX_CAP)
    return data


def channel(qs):
    return analytics.channel_view(_phi(qs))


def model_params(qs):
    return dict(
        anchor=dict(wage=NATIONAL_WAGE_ANCHOR, hours=HOURS_PER_MONTH, social=SOCIAL_RATE),
        smoothing=dict(alpha=ALPHA, beta=BETA, alpha_halflife=ALPHA_HALFLIFE,
                       beta_halflife=BETA_HALFLIFE, max_step=MAX_STEP),
        charter=dict(phi=PHI, phi_range=list(PHI_RANGE), gamma=GAMMA, delta=DELTA,
                     d0=D0, lambda_=LAMBDA, quality_floor=QUALITY_FLOOR, rho=RHO),
        indexation=dict(theta=THETA, zeta=ZETA, personal_cap=PERSONAL_CAP,
                        index_cap=INDEX_CAP),
        perimeter=[dict(code=c, name=industries.name(c), short=industries.short(c))
                   for c in industries.CODES],
    )


def territories_view(qs):
    shock = min(1.0, max(-0.9, _f(qs, "shock", 0.0)))
    return territories.territories(_phi(qs), shock, _f(qs, "cpi", indexation.DEFAULT_CPI))


def municipal_view(qs):
    return municipal.municipal(_s(qs, "city", ""))


ROUTES = {
    "/api/about": about,
    "/api/overview": overview,
    "/api/generation": generation,
    "/api/smoothing": smoothing,
    "/api/industries": industries_view,
    "/api/enterprises": enterprises_view,
    "/api/enterprise": enterprise_view,
    "/api/pricing": pricing,
    "/api/indexation": indexation_view,
    "/api/channel": channel,
    "/api/model": model_params,
    "/api/territories": territories_view,
    "/api/municipal": municipal_view,
}


def calibration_csv(qs) -> str:
    """Выгрузка калибровки по периметру - тот же формат, что и эталонный CSV."""
    rows = analytics.industry_table(_phi(qs))
    out = io.StringIO()
    header = ["Класс ОКВЭД", "Отрасль", "Часовая стоимость труда, руб.",
              "ВДС на чел.-час, руб.", "Приб. продукт на чел.-час, руб.",
              "Сглаженный приб. продукт, руб.", "База часа b_j, руб.",
              "Отраслевой коэф. k_j", "Надбавка mu_j", "Доля труда в ВДС",
              "Доля капитала в ВДС", "Прямые трудозатраты, чел.-ч/1000 руб.",
              "Полные трудозатраты, чел.-ч/1000 руб.", "Множитель цепочки",
              "Цикл, дней", "K_цикл", "Затраты вне периметра, руб./руб."]
    out.write(";".join(header) + "\n")
    for r in rows:
        values = [r["code"], r["name"], f"{r['w_hour']:.1f}", f"{r['vds_hour']:.1f}",
                  f"{r['s_raw']:.1f}", f"{r['s_smooth']:.1f}", f"{r['base']:.2f}",
                  f"{r['k']:.4f}", f"{r['mu']:.4f}", f"{r['labour_share']:.2f}",
                  f"{r['capital_share']:.2f}", f"{r['l_direct']:.4f}",
                  f"{r['h_full']:.4f}", f"{r['multiplier']:.3f}", str(r["cycle_days"]),
                  f"{r['k_cycle']:.4f}", f"{r['external']:.4f}"]
        out.write(";".join(v.replace(".", ",") if v.replace(".", "").replace("-", "").isdigit()
                           else v for v in values) + "\n")
    return out.getvalue()


def territories_csv(qs) -> str:
    """Выгрузка территориального контура: по городу - вклад в экономику и фонды."""
    data = territories_view(qs)
    out = io.StringIO()
    header = ["Город", "Регион", "ЗАТО", "Население", "Предприятия группы",
              "Численность группы", "Доля крупнейшего в занятости", "Градообразующее",
              "ФОТ, руб./мес", "Чистые доходы работников, руб./мес",
              "НДФЛ в бюджет города, руб./мес", "Местные закупки, руб./мес",
              "Территориальный фонд, руб./мес", "Вклад в экономику города, руб./мес",
              "Вклад на жителя, руб./мес", "ВДС, руб./мес", "Амортизационный фонд, руб./мес",
              "Прибавочный продукт S, руб./мес", "Фонд phi*S, руб./мес",
              "Фонд развития, руб./мес", "Резерв, руб./мес",
              "Потребность индексации, руб./мес", "Покрытие индексации фондом"]
    out.write(";".join(header) + "\n")

    def num(v, d=0):
        return f"{v:.{d}f}".replace(".", ",")

    for c in data["cities"]:
        values = [c["name"], c["region"], "да" if c["zato"] else "нет", num(c["population"]),
                  ", ".join(e["short"] for e in c["enterprises"]), num(c["headcount"]),
                  num(c["dependence"], 4), "да" if c["city_forming"] else "нет",
                  num(c["payroll_month"]), num(c["income_month"]), num(c["budget_month"]),
                  num(c["purchases_month"]), num(c["territory_fund_month"]),
                  num(c["contribution_month"]), num(c["contribution_per_resident"]),
                  num(c["V_month"]), num(c["D_month"]), num(c["S_month"]),
                  num(c["socialised_month"]), num(c["development_month"]),
                  num(c["reserve_month"]), num(c["indexation_need_month"]),
                  num(c["coverage"], 3)]
        out.write(";".join(values) + "\n")
    return out.getvalue()


def pmo_panel_csv(qs) -> str:
    """Панель ПМО в том виде, в каком её читает модель: с источником каждого значения."""
    panel = pmo.load_panel()
    out = io.StringIO()
    out.write(";".join(pmo.PANEL_COLUMNS + ["name"]) + "\n")
    for (city, key), values in sorted(panel.items()):
        for year, (value, source) in sorted(values.items()):
            out.write(";".join([city, "", key, str(year), f"{value:g}".replace(".", ","),
                                pmo.BY_KEY[key]["unit"], source, pmo.BY_KEY[key]["name"]]) + "\n")
    return out.getvalue()


def municipal_csv(qs) -> str:
    """Сценарии по городам: эффект предприятий и ключевые показатели на 2030 и 2036 годы."""
    data = municipal.municipal()
    out = io.StringIO()
    header = ["Город", "Регион", "ЗАТО", "Предприятия", "Доля крупнейшего в занятости",
              "Зависимость бюджета от трансфертов", "Доля предприятий в собственных доходах",
              "Устойчивость", "Сценарий", "Доля сценария", "Год", "Эффект предприятий, %",
              "Класс эффекта", "Население", "Занятость", "ФОТ, тыс. руб.",
              "Собственные доходы бюджета, тыс. руб.", "Трансферты, тыс. руб.",
              "Сальдо бюджета, тыс. руб.", "Межбюджетное сальдо, тыс. руб.", "Выбросы, т"]
    out.write(";".join(header) + "\n")
    names = {"positive": "позитивный", "inertial": "инерционный", "negative": "негативный"}

    def num(v, d=0):
        return f"{v:.{d}f}".replace(".", ",")

    for c in data["cities"]:
        for key, label in names.items():
            for year in data["marks"]:
                h = c["horizon"][key][year]
                out.write(";".join([
                    c["name"], c["region"], "да" if c["zato"] else "нет",
                    ", ".join(e["short"] for e in c["enterprises"]),
                    num(c["dependence"], 4), num(c["transfer_dependence"], 4),
                    num(c["ent_own_share"], 4), num(c["resilience"], 3), label,
                    num(c["shares"][key], 3), str(year), num(h["effect"] * 100, 2),
                    names[h["effect_class"]], num(h["population"]), num(h["employees"]),
                    num(h["payroll"] / 1e3), num(h["tax_revenue"] / 1e3),
                    num(h["transfers"] / 1e3), num(h["budget_balance"] / 1e3),
                    num(h["interbudget_net"] / 1e3), num(h["emissions"], 1)]) + "\n")
    return out.getvalue()


def dispatch(path: str, query: str):
    """Возвращает (данные, ошибка). Ошибка - кортеж (код, текст)."""
    handler = ROUTES.get(path)
    if handler is None:
        return None, (404, f"нет обработчика для {path}")
    qs = parse_qs(query or "")
    try:
        return handler(qs), None
    except KeyError as exc:
        return None, (400, f"неизвестный идентификатор: {exc}")
    except ValueError as exc:
        return None, (400, str(exc))
