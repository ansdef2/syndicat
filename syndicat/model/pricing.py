"""Слои 4-6: полные трудозатраты, цена продукта, экстерналии, контур эмиссии.

    l_j = ψ_j / v_j                     прямые трудозатраты, чел.-ч / руб.
    h   = l · (I − A)⁻¹                 полные трудозатраты
    P_i = B · Σ_m h_im·k_m·(1 + μ_m) + E_i
    R_i = (P_рын − P_произв) / P_рын    индикатор ренты
    Δ ln P = Σ_k ε_ik · Δ ln X_k        пасс-тру экстерналий
"""

import math

from .. import linalg
from . import industries as ind
from .constants import (PHI, PHI_SENSITIVITY, RHO, TOKEN_INDEX_CORRIDOR,
                        TOKEN_INDEX_TARGET)
from .tokens import calibrate


def direct_labour_vector() -> list:
    """l_j - прямые трудозатраты, чел.-ч на 1 руб. выпуска."""
    out = []
    for code in ind.CODES:
        from .tokens import industry_unit_values
        out.append(ind.INDUSTRIES[code]["psi"] / industry_unit_values(code)["v"])
    return out


def leontief():
    """(I − A)⁻¹ - матрица полных затрат внутри периметра 20-30."""
    return linalg.leontief_inverse(ind.build_A())


def full_labour_content(l=None, L=None) -> list:
    l = l or direct_labour_vector()
    L = L or leontief()
    return linalg.vec_mat(l, L)


def labour_by_industry(code: str, l=None, L=None) -> dict:
    """Разложение полных трудозатрат продукта отрасли code по отраслям-донорам."""
    l = l or direct_labour_vector()
    L = L or leontief()
    col = ind.INDEX[code]
    return {c: l[i] * L[i][col] for i, c in enumerate(ind.CODES)}


def external_intensity(l=None, L=None) -> dict:
    """Полная потребность в ресурсах вне периметра на 1 руб. выпуска.

    Периметр открыт: сырьё 05-09, энергия 35, транспорт 49-52 входят
    в цену по рыночному рублю, а не по трудовой оценке.
    """
    A = ind.build_A()
    L = L or leontief()
    e_direct = [1.0 - ind.INDUSTRIES[c]["psi"] - sum(A[i][j] for i in range(ind.N))
                for j, c in enumerate(ind.CODES)]
    vals = linalg.vec_mat(e_direct, L)
    return {c: vals[i] for i, c in enumerate(ind.CODES)}


def rent_indicator(market_price: float, production_price: float) -> float:
    if market_price <= 0:
        return 0.0
    return (market_price - production_price) / market_price


def price_shock(code: str, dlog_x: dict) -> float:
    """Прирост лог-цены как сумма вкладов экстерналий."""
    eps = ind.ELASTICITIES[code]
    return sum(eps[i] * dlog_x.get(key, 0.0) for i, key in enumerate(ind.EXT_KEYS))


def shock_contributions(code: str, factors: dict) -> list:
    """Разложение шока по факторам: factors - относительные приросты (0,12 = +12%)."""
    eps = ind.ELASTICITIES[code]
    rows = []
    for i, meta in enumerate(ind.EXTERNALITIES):
        dlog = math.log1p(factors.get(meta["key"], 0.0))
        rows.append(dict(key=meta["key"], label=meta["label"], elasticity=eps[i],
                         change=factors.get(meta["key"], 0.0),
                         contribution=eps[i] * dlog))
    return rows


def price_of(code: str, scale_rub: float, phi: float = PHI, factors: dict = None) -> dict:
    """Развёрнутый порядок образования цены продукта отрасли code.

    scale_rub - масштаб продукта в рублях выпуска (рыночная цена аналога либо
    плановый объём выпуска изделия). Трудовое и внешнее содержание считаются
    на рубль выпуска и масштабируются на эту величину.
    """
    calib = calibrate(phi)
    B = calib["B"]
    rows = calib["industries"]
    l, L = direct_labour_vector(), leontief()

    donors_per_rub = labour_by_industry(code, l, L)
    donors, labour_tokens, labour_rub = [], 0.0, 0.0
    for donor_code, hours_per_rub in donors_per_rub.items():
        hours = hours_per_rub * scale_rub
        if hours <= 1e-6:
            continue
        k = rows[donor_code]["k"]
        mu = rows[donor_code]["mu"]
        tokens = hours * k * (1 + mu)
        rub = tokens * B
        labour_tokens += tokens
        labour_rub += rub
        donors.append(dict(code=donor_code, name=ind.name(donor_code),
                           short=ind.short(donor_code), hours=hours,
                           k=k, mu=mu, tokens=tokens, rub=rub))
    donors.sort(key=lambda r: -r["hours"])

    external_rub = external_intensity(l, L)[code] * scale_rub
    production_price = labour_rub + external_rub
    full_hours = sum(d["hours"] for d in donors)

    result = dict(
        code=code, industry=ind.name(code), scale_rub=scale_rub, B=B, phi=phi,
        full_hours=full_hours,
        direct_hours=l[ind.INDEX[code]] * scale_rub,
        chain_multiplier=(full_hours / (l[ind.INDEX[code]] * scale_rub)) if l[ind.INDEX[code]] else 0.0,
        labour_tokens=labour_tokens, labour_rub=labour_rub,
        external_rub=external_rub, production_price=production_price,
        market_price=scale_rub,
        rent=rent_indicator(scale_rub, production_price),
        donors=donors,
    )
    if factors:
        rows_shock = shock_contributions(code, factors)
        dlog = sum(r["contribution"] for r in rows_shock)
        result["shock"] = dict(factors=rows_shock, dlog=dlog,
                               percent=100.0 * (math.exp(dlog) - 1.0),
                               price_after=production_price * math.exp(dlog))
    return result


def emission_cap(output_norm_hours: float, rho: float = RHO) -> float:
    """Потолок прироста массы ТЧЧ: физический выпуск в нормо-часах + допуск."""
    return output_norm_hours * (1.0 + rho)


def phi_adjustment(token_price_index: float, phi: float = PHI,
                   target: float = TOKEN_INDEX_TARGET,
                   corridor: float = TOKEN_INDEX_CORRIDOR,
                   sensitivity: float = PHI_SENSITIVITY) -> float:
    """Обратная связь: выход индекса токен-цен за коридор сжимает эмиссию."""
    gap = token_price_index - target
    if abs(gap) <= corridor:
        return phi
    sign = 1.0 if gap > 0 else -1.0
    return min(1.0, max(0.0, phi - sensitivity * (gap - sign * corridor)))
