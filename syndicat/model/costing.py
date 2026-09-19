# -*- coding: utf-8 -*-
"""Порядок образования цены изделия при генерации ТЧЧ.

Восемь шагов, каждый из которых наблюдаем и проверяем:

  1. Нормирование операций (ЕНиР/ЕТКС): T_норм, T_факт, разряд, цикл
  2. Эмиссия ТЧЧ на изделие: τ = [λT_ф + (1−λ)T_н]·K_сл·K_цикл·q·k_j
  3. Прямые трудозатраты отрасли l_j = ψ_j / v_j
  4. Полные трудозатраты h = l·(I − A)⁻¹ и множитель цепочки
  5. Разложение полных трудозатрат по отраслям-донорам
  6. Трудовая часть цены: B · Σ_m h_im·k_m·(1 + μ_m)
  7. Внешний контур E_i по рыночному рублю → цена производства
  8. Сверка с рыночной ценой → индикатор ренты; сценарий экстерналий
"""

from . import industries as ind
from .constants import LAMBDA, PHI
from .enterprises import BY_ID, product_emission, profile
from .pricing import direct_labour_vector, price_of
from .tokens import calibrate, cycle_coef, skill_coef


def products_index() -> list:
    """Плоский список изделий реестра - для выпадающего списка панели."""
    out = []
    for ent in BY_ID.values():
        for p in ent["products"]:
            out.append(dict(ent_id=ent["id"], ent_name=ent["name"], sku=p["sku"],
                            name=p["name"], cls=ent["cls"], okved=ent["okved"],
                            unit=p["unit"], market_price=p["market_price"],
                            focus=ent.get("focus", False)))
    return out


def dossier(ent_id: str, sku: str, factors: dict = None, phi: float = PHI) -> dict:
    """Полное досье цены изделия: восемь шагов с числами на каждом."""
    ent = BY_ID[ent_id]
    product = next((p for p in ent["products"] if p["sku"] == sku), ent["products"][0])
    calib = calibrate(phi)
    row = calib["industries"][ent["cls"]]
    B, k, mu = calib["B"], row["k"], row["mu"]

    # шаг 1-2: нормирование и эмиссия
    emission = product_emission(ent, product, k)
    t_norm = product["norm_hours"]
    t_fact = t_norm / max(ent["oee"], 0.3) * 0.82

    # шаги 3-7: цена через полные трудозатраты
    price = price_of(ent["cls"], float(product["market_price"]), phi, factors)

    # собственная трудоёмкость предприятия против отраслевой нормы
    l = direct_labour_vector()[ind.INDEX[ent["cls"]]]
    industry_direct_hours = l * product["market_price"]

    steps = [
        dict(n=1, title="Нормирование операции",
             detail=f"T_норм {t_norm:g} ч по ЕНиР, T_факт {t_fact:.1f} ч при OEE {ent['oee']:.2f}, "
                    f"разряд {product.get('grade', round(ent['avg_grade']))}, "
                    f"цикл {product.get('cycle_days', 30)} дн.",
             value=LAMBDA * t_fact + (1 - LAMBDA) * t_norm, unit="ч базы времени"),
        dict(n=2, title="Эмиссия ТЧЧ на изделие",
             detail="τ = [λ·T_факт + (1−λ)·T_норм] · K_сл · K_цикл · q · k_j",
             value=emission["tokens"], unit="ТЧЧ"),
        dict(n=3, title="Прямые трудозатраты отрасли",
             detail=f"l_j = ψ_j / v_j = {l * 1000:.4f} чел.-ч на 1000 руб. выпуска",
             value=industry_direct_hours, unit="чел.-ч прямых"),
        dict(n=4, title="Полные трудозатраты по цепочке",
             detail=f"h = l·(I − A)⁻¹, множитель цепочки {price['chain_multiplier']:.3f}",
             value=price["full_hours"], unit="чел.-ч полных"),
        dict(n=5, title="Разложение по отраслям-донорам",
             detail=f"{len(price['donors'])} классов ОКВЭД в цепочке изделия",
             value=len(price["donors"]), unit="доноров"),
        dict(n=6, title="Трудовая часть цены",
             detail=f"B · Σ h_im·k_m·(1 + μ_m) при B = {B:,.2f} руб./ТЧЧ".replace(",", " "),
             value=price["labour_rub"], unit="руб."),
        dict(n=7, title="Внешний контур по рыночному рублю",
             detail="сырьё ОКВЭД 05-09, энергия 35, транспорт 49-52",
             value=price["external_rub"], unit="руб."),
        dict(n=8, title="Цена производства",
             detail=f"рыночная цена аналога {product['market_price']:,.0f} руб.".replace(",", " "),
             value=price["production_price"], unit="руб."),
    ]

    return dict(
        enterprise=profile(ent_id, phi)["enterprise"],
        product=dict(**product, industry=ind.name(ent["cls"]), cls=ent["cls"]),
        B=B, k=k, mu=mu, phi=phi,
        t_norm=t_norm, t_fact=t_fact,
        emission=emission,
        tokens_per_unit=emission["tokens"],
        tokens_rub_per_unit=emission["tokens"] * B,
        price=price, steps=steps,
        labour_share_price=price["labour_rub"] / price["production_price"],
        external_share_price=price["external_rub"] / price["production_price"],
        waterfall=[
            dict(label="Трудовая часть", value=price["labour_rub"], kind="labour"),
            dict(label="Внешний контур", value=price["external_rub"], kind="external"),
            dict(label="Цена производства", value=price["production_price"], kind="total"),
            dict(label="Рыночная цена", value=price["market_price"], kind="market"),
        ],
    )
