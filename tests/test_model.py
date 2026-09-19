# -*- coding: utf-8 -*-
"""Проверки расчётного ядра: учётные тождества, воспроизводимость калибровки,
замкнутость ценовой модели и ограничения контура индексации.

Запуск:  python3 -m unittest discover -s tests -v
"""

import csv
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syndicat import api, linalg
from syndicat.model import analytics, costing, enterprises, indexation, industries
from syndicat.model import pricing, tokens
from syndicat.model.constants import ALPHA, BETA, MAX_STEP, PHI
from syndicat.model.smoothing import clip_step

REFERENCE_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "syndicat", "data", "calibration-okved-20-30.csv")


def reference_rows():
    with open(REFERENCE_CSV, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    return {r["Класс ОКВЭД"]: r for r in rows}


def rus_float(value: str) -> float:
    return float(value.replace(" ", "").replace(",", "."))


class TestSmoothing(unittest.TestCase):
    def test_coefficients_from_halflife(self):
        self.assertAlmostEqual(ALPHA, 1 - 2 ** (-1 / 6), places=10)
        self.assertAlmostEqual(BETA, 1 - 2 ** (-1 / 12), places=10)
        self.assertAlmostEqual(ALPHA, 0.1091, places=4)
        self.assertAlmostEqual(BETA, 0.0561, places=4)

    def test_step_limiter(self):
        self.assertAlmostEqual(clip_step(2000.0, 1000.0), 1000.0 * (1 + MAX_STEP))
        self.assertAlmostEqual(clip_step(10.0, 1000.0), 1000.0 * (1 - MAX_STEP))
        self.assertAlmostEqual(clip_step(1005.0, 1000.0), 1005.0)

    def test_base_path_inside_corridor(self):
        for code, row in tokens.calibrate()["industries"].items():
            path = row["path"]
            for prev, cur in zip(path, path[1:]):
                ratio = cur["base"] / prev["base"]
                self.assertLessEqual(ratio, 1 + MAX_STEP + 1e-9, code)
                self.assertGreaterEqual(ratio, 1 - MAX_STEP - 1e-9, code)


class TestAccountingIdentity(unittest.TestCase):
    def test_vds_decomposition(self):
        """V = W + D + S по каждому классу: учётное тождество замкнуто."""
        for code in industries.CODES:
            u = tokens.industry_unit_values(code)
            self.assertAlmostEqual(u["v"], u["w_total"] + u["dep"] + u["s"], places=6, msg=code)

    def test_shares_sum_to_one(self):
        for code in industries.CODES:
            u = tokens.industry_unit_values(code)
            total = u["labour_share"] + u["capital_share"] + u["depreciation_share"]
            self.assertAlmostEqual(total, 1.0, places=9, msg=code)

    def test_markup_is_derived_not_assigned(self):
        """μ_j = [d_j + (1 − φ)·s_j] / b_j - выводится из тождества."""
        for code in industries.CODES:
            u = tokens.industry_unit_values(code)
            s_smooth = tokens.calibrate()["industries"][code]["s_smooth"]
            expected = (u["dep"] + (1 - PHI) * s_smooth) / tokens.token_base(code, s_smooth)
            self.assertAlmostEqual(tokens.markup(code, s_smooth), expected, places=9, msg=code)


class TestCalibration(unittest.TestCase):
    def test_network_unit_matches_published(self):
        """Прогон воспроизводит опубликованную калибровку: B = 876,58 руб./ТЧЧ."""
        self.assertAlmostEqual(tokens.calibrate()["B"], 876.58, delta=0.02)

    def test_industry_coefficients_close_to_reference(self):
        ref = reference_rows()
        calib = tokens.calibrate()["industries"]
        for code, row in calib.items():
            self.assertAlmostEqual(row["k"], rus_float(ref[code]["Отраслевой коэф. k_j"]),
                                   delta=0.01, msg=f"k_j класса {code}")
            self.assertAlmostEqual(row["w_hour"], rus_float(ref[code]["Часовая стоимость труда, руб."]),
                                   delta=0.5, msg=f"w_j класса {code}")

    def test_hours_weighting_not_revenue(self):
        """Сетевая единица взвешена по часам: Σ ω_j = 1."""
        self.assertAlmostEqual(sum(industries.HOURS_SHARE.values()), 1.0, places=9)
        calib = tokens.calibrate()
        manual = sum(industries.HOURS_SHARE[c] * calib["industries"][c]["base"]
                     for c in industries.CODES)
        self.assertAlmostEqual(manual, calib["B"], places=6)


class TestEmission(unittest.TestCase):
    def test_skill_scale_matches_etks_range(self):
        self.assertAlmostEqual(tokens.skill_coef(1), 1.0, places=9)
        # γ = 0,125 (уставной параметр) даёт 1,125^7 = 2,281 на восьмом разряде.
        # В спецификации рядом указан диапазон «1,000 → 2,027», который
        # соответствует γ = 0,1075: расхождение вынесено в docs/МОДЕЛЬ.md.
        self.assertAlmostEqual(tokens.skill_coef(8), 1.125 ** 7, places=9)
        self.assertAlmostEqual(tokens.skill_coef(8), 2.281, delta=0.001)

    def test_cycle_coefficient(self):
        self.assertAlmostEqual(tokens.cycle_coef(2), 1.008, delta=0.001)
        self.assertAlmostEqual(tokens.cycle_coef(180), 1.234, delta=0.001)

    def test_quality_floor_zeroes_emission(self):
        args = dict(t_fact=10, t_norm=10, grade=5, cycle_days=30, k_ind=1.0)
        self.assertEqual(tokens.emission(quality=0.89, **args), 0.0)
        self.assertGreater(tokens.emission(quality=0.97, **args), 0.0)

    def test_downtime_paid_at_lambda(self):
        """Простой по вине оборудования оплачивается частично, но не полностью."""
        full = tokens.emission(10, 10, 4, 30, 1.0, 1.0)
        downtime = tokens.emission(14, 10, 4, 30, 1.0, 1.0)
        self.assertGreater(downtime, full)
        self.assertLess(downtime, tokens.emission(14, 14, 4, 30, 1.0, 1.0))


class TestPricing(unittest.TestCase):
    def test_leontief_inverse(self):
        A = industries.build_A()
        L = pricing.leontief()
        identity = linalg.identity(industries.N)
        check = [[sum((identity[i][k] - A[i][k]) * L[k][j] for k in range(industries.N))
                  for j in range(industries.N)] for i in range(industries.N)]
        for i in range(industries.N):
            for j in range(industries.N):
                self.assertAlmostEqual(check[i][j], identity[i][j], places=9)

    def test_full_exceeds_direct(self):
        l = pricing.direct_labour_vector()
        h = pricing.full_labour_content()
        for i, code in enumerate(industries.CODES):
            self.assertGreaterEqual(h[i], l[i] - 1e-12, code)

    def test_pump_example_matches_specification(self):
        """Сквозной пример спецификации: насос К100-65-200, ОКВЭД 28."""
        r = pricing.price_of("28", 186000.0)
        self.assertAlmostEqual(r["full_hours"], 94.67, delta=0.5)
        self.assertAlmostEqual(r["external_rub"], 78049, delta=200)
        self.assertAlmostEqual(r["production_price"], 189261, delta=2000)
        self.assertAlmostEqual(r["rent"], -0.018, delta=0.01)

    def test_donor_decomposition_sums_to_full_hours(self):
        r = pricing.price_of("28", 186000.0)
        self.assertAlmostEqual(sum(d["hours"] for d in r["donors"]), r["full_hours"], places=6)

    def test_shock_matches_specification(self):
        table = {row["code"]: row["percent"]
                 for row in analytics.shock_table(dict(energy=0.12, fx=0.08))}
        for code, expected in {"20": 5.02, "21": 4.26, "23": 5.05, "24": 5.22, "29": 3.54}.items():
            self.assertAlmostEqual(table[code], expected, delta=0.02, msg=code)

    def test_phi_feedback_only_outside_corridor(self):
        self.assertEqual(pricing.phi_adjustment(1.01), PHI)
        self.assertLess(pricing.phi_adjustment(1.10), PHI)


class TestEnterprises(unittest.TestCase):
    def test_registry_sizes_follow_209fz(self):
        for ent in enterprises.ENTERPRISES:
            if ent["size"] == "среднее":
                self.assertLessEqual(ent["headcount"], 1000, ent["name"])
                self.assertLessEqual(ent["revenue_bn"], 2.0, ent["name"])
            else:
                self.assertTrue(ent["headcount"] > 1000 or ent["revenue_bn"] > 2.0, ent["name"])

    def test_every_enterprise_is_inside_perimeter(self):
        for ent in enterprises.ENTERPRISES:
            self.assertIn(ent["cls"], industries.CODES, ent["name"])
            self.assertTrue(ent["okved"].startswith(ent["cls"]), ent["name"])
            self.assertTrue(ent["products"], ent["name"])

    def test_profile_and_dossier(self):
        d = costing.dossier("livgidromash", "К100-65-200")
        self.assertGreater(d["tokens_per_unit"], 0)
        self.assertEqual(len(d["steps"]), 8)
        self.assertAlmostEqual(d["price"]["labour_rub"] + d["price"]["external_rub"],
                               d["price"]["production_price"], places=6)

    def test_focus_industry_has_medium_and_large(self):
        focus = [e for e in enterprises.ENTERPRISES if e.get("focus")]
        self.assertGreaterEqual(len(focus), 4)
        self.assertTrue(any(e["size"] == "среднее" for e in focus))
        self.assertTrue(any(e["size"] == "крупное" for e in focus))


class TestIndexation(unittest.TestCase):
    def test_protective_contour_is_never_cut(self):
        r = indexation.indexation("livgidromash", cpi=0.074)
        for g in r["groups"]:
            self.assertGreaterEqual(g["index"], r["cpi"] - 1e-12, f"разряд {g['grade']}")

    def test_budget_constraint(self):
        r = indexation.indexation("chkz", cpi=0.074)
        if not r["constrained"]:
            self.assertLessEqual(r["cost_month"], r["fund_month"] + 1e-6)
        else:
            self.assertLess(r["scale"], 1.0)

    def test_high_inflation_triggers_constraint(self):
        r = indexation.indexation("chkz", cpi=0.60)
        self.assertTrue(r["constrained"] or r["deficit"] > 0)
        for g in r["groups"]:
            self.assertGreaterEqual(g["index"], 0.60 - 1e-9)

    def test_productive_contour_requires_base_growth(self):
        r = indexation.indexation("livgidromash", cpi=0.99)
        self.assertEqual(r["productive"], 0.0)

    def test_personal_contour_is_capped(self):
        r = indexation.indexation("severstal", cpi=0.074, zeta=10.0)
        for g in r["groups"]:
            self.assertLessEqual(abs(g["personal"]), 0.08 + 1e-9)


class TestApi(unittest.TestCase):
    def test_every_route_returns_serialisable_json(self):
        for path in api.ROUTES:
            data, error = api.dispatch(path, "energy=0.12&fx=0.08&phi=0.35")
            self.assertIsNone(error, path)
            payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
            self.assertGreater(len(payload), 100, path)

    def test_unknown_route(self):
        data, error = api.dispatch("/api/nope", "")
        self.assertIsNone(data)
        self.assertEqual(error[0], 404)

    def test_unknown_enterprise_is_reported(self):
        data, error = api.dispatch("/api/enterprise", "id=нет-такого")
        self.assertIsNone(data)
        self.assertEqual(error[0], 400)

    def test_csv_export_has_all_classes(self):
        body = api.calibration_csv({})
        lines = body.strip().splitlines()
        self.assertEqual(len(lines), 12)
        self.assertTrue(lines[0].startswith("Класс ОКВЭД;"))

    def test_phi_changes_base_and_unit(self):
        low, _ = api.dispatch("/api/overview", "phi=0.10")
        high, _ = api.dispatch("/api/overview", "phi=0.45")
        self.assertLess(low["B"], high["B"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
