# -*- coding: utf-8 -*-
"""Синтетическая панель ПМО и история активности предприятий за 2017-2024 годы.

Пока реальная выгрузка БД ПМО недоступна, панель строится той же моделью, что
и прогноз (municipal.city_year), по синтетической истории активности:
тренд дивизиона, производственный цикл, общие шоки 2020 и 2022-2023 годов,
ступени ввода и вывода мощностей и шум наблюдения. Все значения помечены
источником «синтетика». Реальная выгрузка кладётся в data/pmo/real.csv и
замещает синтетику построчно (см. pmo.py).

Запуск:  python3 -m syndicat.model.pmo_synth   - перезаписывает data/pmo/*.csv
"""

import math
import random

from . import pmo, rosatom
from .municipal import (CYCLE_YEARS, HISTORY_SCENARIO, city_enterprises, city_year,
                        enterprise_base, structural_base)

SEED = 2024
SOURCE = "синтетика"
FIRST = pmo.YEARS[0] - 1     # год до панели - для миграционного прироста

TREND = {"power": 0.004, "fuel": 0.012, "mining": -0.025, "radiochem": 0.008, "machine": 0.04}
TREND_OVERRIDE = {"skhk": 0.004, "aekhk": 0.002, "chmz": 0.006, "nzhk": 0.008}
AMPLITUDE = {"power": 0.02, "fuel": 0.012, "mining": 0.03, "radiochem": 0.03, "machine": 0.07}
NOISE = 0.012
# Ступени активности (ln), действующие с указанного года: синтетическое
# отображение вывода старых и ввода замещающих мощностей, не отчётные данные.
EVENTS = {
    "kursk": {2021: -0.12, 2024: -0.10},
    "leningrad": {2018: -0.06, 2019: 0.08, 2020: -0.07, 2021: 0.09},
    "novovoronezh": {2017: 0.05},
    "beloyarsk": {2019: 0.04},
}
# Общие шоки (ln) с экспозицией по доле выручки
SHOCKS = [(2020, "domestic", -0.03, False), (2022, "export", -0.06, True),
          (2023, "export", 0.03, True)]

# Шум наблюдения панели по показателям (лог-стандартное отклонение)
PANEL_NOISE = dict(population=0.003, employees=0.008, avg_wage=0.01, shipped=0.02,
                   investment=0.06, fin_result=0.05, retail=0.015, other_own=0.03,
                   ndfl_local=0.012, transfers=0.04, budget_expenditure=0.02,
                   emissions=0.04, env_costs=0.03, lean_capex=0.08)


def activity_history() -> dict:
    """Синтетический индекс активности предприятий, 2024 = 1."""
    out = {}
    for i, (eid, e) in enumerate(sorted(enterprise_base().items())):
        rng = random.Random(SEED + i)
        div = e["division"]
        trend = TREND_OVERRIDE.get(eid, TREND[div])
        period = CYCLE_YEARS[div]
        phase = rng.uniform(0, 2 * math.pi)
        out_ = e["output"] or 1.0
        exposure = dict(export=e["export"] / out_, domestic=(e["domestic"] + e["internal"]) / out_)
        raw = {}
        for year in range(FIRST, pmo.BASE_YEAR + 1):
            tau = year - pmo.BASE_YEAR
            v = trend * tau + AMPLITUDE[div] * math.cos(2 * math.pi * tau / period + phase)
            v += sum(step for y, step in EVENTS.get(eid, {}).items() if year >= y)
            for y, kind, size, persistent in SHOCKS:
                if year == y or (persistent and year > y):
                    v += size * exposure[kind]
            v += rng.gauss(0.0, NOISE)
            raw[year] = v
        out[eid] = {y: math.exp(v - raw[pmo.BASE_YEAR]) for y, v in raw.items()}
    return out


def generate():
    """Строки panel.csv и activity.csv."""
    acts = activity_history()
    activity_rows = [dict(enterprise=eid, year=y, index=f"{v:.5f}", source=SOURCE)
                     for eid in sorted(acts) for y, v in sorted(acts[eid].items()) if y >= pmo.YEARS[0]]

    panel_rows = []
    for ci, cid in enumerate(rosatom.CITIES):
        ents = city_enterprises(cid)
        if not ents:
            continue
        rng = random.Random(SEED * 7 + ci)
        noise = lambda key: math.exp(rng.gauss(0.0, PANEL_NOISE[key]))
        base = structural_base(cid)
        states = {y: city_year(base, ents, {e["id"]: acts[e["id"]][y] for e in ents}, y,
                               HISTORY_SCENARIO) for y in range(FIRST, pmo.BASE_YEAR + 1)}
        prev_pop = None
        for year in range(FIRST, pmo.BASE_YEAR + 1):
            st = states[year]
            pop = round(st["population"] * noise("population"))
            emp = round(st["employees"] * noise("employees"))
            wage = st["avg_wage"] * noise("avg_wage")
            payroll = emp * wage * 12 / 1e3
            ndfl = payroll * 0.13 * (st["ndfl_local"] / (st["payroll"] * 0.13)) * noise("ndfl_local")
            rest = (st["tax_revenue"] - st["ndfl_local"]) / 1e3 * noise("other_own")
            tax = ndfl + rest
            transfers = st["transfers"] / 1e3 * noise("transfers")
            expenditure = st["budget_expenditure"] / 1e3 * noise("budget_expenditure")
            values = dict(
                population=pop, employees=emp, avg_wage=round(wage, 1), payroll=round(payroll),
                shipped=round(st["shipped"] / 1e3 * noise("shipped")),
                investment=round(st["investment"] / 1e3 * noise("investment")),
                fin_result=round(st["fin_result"] / 1e3 * noise("fin_result")),
                retail=round(st["retail"] / 1e3 * noise("retail")),
                tax_revenue=round(tax), ndfl_local=round(ndfl), transfers=round(transfers),
                budget_revenue=round(tax) + round(transfers),
                budget_expenditure=round(expenditure),
                budget_balance=round(tax) + round(transfers) - round(expenditure),
                emissions=round(st["emissions"] * noise("emissions"), 1),
                env_costs=round(st["env_costs"] / 1e3 * noise("env_costs")),
                lean_capex=round(st["lean_capex"] / 1e3 * noise("lean_capex")),
            )
            if prev_pop is not None:
                values["migration"] = pop - prev_pop
            prev_pop = pop
            if year < pmo.YEARS[0]:
                continue
            for key, value in values.items():
                panel_rows.append(dict(municipality=cid, oktmo="", indicator=key, year=year,
                                       value=value, unit=pmo.BY_KEY[key]["unit"], source=SOURCE))
    return panel_rows, activity_rows


if __name__ == "__main__":
    panel_rows, activity_rows = generate()
    pmo.write_panel(panel_rows)
    pmo.write_activity(activity_rows)
    print(f"panel.csv: {len(panel_rows)} строк, activity.csv: {len(activity_rows)} строк")
