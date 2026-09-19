# -*- coding: utf-8 -*-
"""Расчётное API платформы. Каждый обработчик возвращает JSON-совместимый dict."""

import io
from urllib.parse import parse_qs

from .model import analytics, costing, enterprises, indexation, industries
from .model.constants import (ALPHA, ALPHA_HALFLIFE, BETA, BETA_HALFLIFE, D0,
                              DELTA, GAMMA, HOURS_PER_MONTH, INDEX_CAP,
                              LAMBDA, MAX_STEP, NATIONAL_WAGE_ANCHOR,
                              PERSONAL_CAP, PHI, PHI_RANGE, QUALITY_FLOOR, RHO,
                              SOCIAL_RATE, THETA, ZETA)


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


ROUTES = {
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
