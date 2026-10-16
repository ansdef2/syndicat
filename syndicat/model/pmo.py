# -*- coding: utf-8 -*-
"""Открытые данные муниципального слоя: каталог показателей ПМО и загрузка панели.

Источник - База данных показателей муниципальных образований Росстата (БД ПМО).
Панель хранится в формате выгрузки «муниципалитет × показатель × год»:

  syndicat/data/pmo/panel.csv     синтетическая панель 2017-2024 (pmo_synth.py)
  syndicat/data/pmo/activity.csv  история активности предприятий, индекс 2024 = 1
  syndicat/data/pmo/real.csv      НЕОБЯЗАТЕЛЬНО: реальная выгрузка ПМО; её строки
                                  замещают синтетические с тем же ключом
  syndicat/data/pmo/real-activity.csv  НЕОБЯЗАТЕЛЬНО: реальная история выпуска

Колонки panel.csv и real.csv:
  municipality;oktmo;indicator;year;value;unit;source
municipality - идентификатор города из rosatom.CITIES, indicator - ключ из CATALOG,
денежные показатели - в тыс. руб., как в БД ПМО. Колонки activity.csv:
  enterprise;year;index;source

Каждое значение несёт источник: «ПМО» (реальная выгрузка), «отчётность»
(публичная отчётность предприятия) или «синтетика». Модель читает панель
одинаково, поэтому замена синтетики реальными данными не требует правки кода.
"""

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "pmo")
PANEL_CSV = os.path.join(DATA_DIR, "panel.csv")
ACTIVITY_CSV = os.path.join(DATA_DIR, "activity.csv")
REAL_CSV = os.path.join(DATA_DIR, "real.csv")
REAL_ACTIVITY_CSV = os.path.join(DATA_DIR, "real-activity.csv")

YEARS = list(range(2017, 2025))     # отчётные годы панели
BASE_YEAR = YEARS[-1]               # последний отчётный год - базовый год модели

# relation: как показатель связан с предприятием реального сектора в моногороде
#   прямая     - показатель формируется деятельностью предприятия
#   косвенная  - отражает влияние через доходы, бюджет, миграцию
# scope: «ПМО» - есть в БД ПМО; «вне ПМО» - отчётность предприятия (форма 4-ОС и др.)
CATALOG = [
    dict(key="population", name="Численность населения на 1 января", unit="чел.",
         section="Население", relation="косвенная", scope="ПМО",
         role="миграция за рабочими местами; база расходов бюджета"),
    dict(key="migration", name="Миграционный прирост (убыль)", unit="чел.",
         section="Население", relation="косвенная", scope="ПМО",
         role="реакция населения на изменение занятости"),
    dict(key="employees", name="Среднесписочная численность работников организаций",
         unit="чел.", section="Труд", relation="прямая", scope="ПМО",
         role="занятость: предприятие и смежный сектор города"),
    dict(key="avg_wage", name="Среднемесячная номинальная начисленная заработная плата "
                              "работников организаций", unit="руб.", section="Труд",
         relation="прямая", scope="ПМО", role="доходы работников"),
    dict(key="payroll", name="Фонд начисленной заработной платы всех работников организаций",
         unit="тыс. руб.", section="Труд", relation="прямая", scope="ПМО",
         role="база НДФЛ местного и регионального бюджетов"),
    dict(key="shipped", name="Отгружено товаров собственного производства, выполнено работ "
                             "и услуг собственными силами", unit="тыс. руб.",
         section="Производство", relation="прямая", scope="ПМО",
         role="активность предприятия и выход продукции на рынок"),
    dict(key="investment", name="Инвестиции в основной капитал за счёт всех источников "
                                "финансирования", unit="тыс. руб.", section="Инвестиции",
         relation="прямая", scope="ПМО", role="воспроизводство фондов, ввод мощностей"),
    dict(key="fin_result", name="Сальдированный финансовый результат (прибыль минус убыток) "
                                "деятельности организаций", unit="тыс. руб.",
         section="Финансы организаций", relation="прямая", scope="ПМО",
         role="прибавочный продукт предприятия, налог на прибыль"),
    dict(key="retail", name="Оборот розничной торговли", unit="тыс. руб.",
         section="Торговля", relation="косвенная", scope="ПМО",
         role="расходы домохозяйств: мультипликатор доходов работников"),
    dict(key="tax_revenue", name="Налоговые и неналоговые доходы местного бюджета",
         unit="тыс. руб.", section="Местный бюджет", relation="косвенная", scope="ПМО",
         role="собственные доходы города"),
    dict(key="ndfl_local", name="Налог на доходы физических лиц в доходах местного бюджета",
         unit="тыс. руб.", section="Местный бюджет", relation="прямая", scope="ПМО",
         role="канал ФОТ → бюджет города"),
    dict(key="transfers", name="Безвозмездные поступления от других бюджетов бюджетной "
                               "системы", unit="тыс. руб.", section="Местный бюджет",
         relation="косвенная", scope="ПМО", role="межбюджетное выравнивание"),
    dict(key="budget_revenue", name="Доходы местного бюджета, фактически исполненные",
         unit="тыс. руб.", section="Местный бюджет", relation="косвенная", scope="ПМО",
         role="собственные доходы и трансферты"),
    dict(key="budget_expenditure", name="Расходы местного бюджета, фактически исполненные",
         unit="тыс. руб.", section="Местный бюджет", relation="косвенная", scope="ПМО",
         role="расходные обязательства города"),
    dict(key="budget_balance", name="Профицит (+), дефицит (−) местного бюджета",
         unit="тыс. руб.", section="Местный бюджет", relation="косвенная", scope="ПМО",
         role="итог бюджетной политики"),
    dict(key="emissions", name="Выбросы загрязняющих атмосферу веществ, отходящих "
                               "от стационарных источников", unit="т",
         section="Охрана окружающей среды", relation="прямая", scope="ПМО",
         role="негативный эффект производства"),
    dict(key="env_costs", name="Текущие затраты на охрану окружающей среды предприятий",
         unit="тыс. руб.", section="Охрана окружающей среды", relation="прямая",
         scope="вне ПМО", role="бережливое и безотходное производство: текущие затраты"),
    dict(key="lean_capex", name="Инвестиции в бережливое и безотходное производство",
         unit="тыс. руб.", section="Охрана окружающей среды", relation="прямая",
         scope="вне ПМО", role="бережливое и безотходное производство: инвестиции"),
]
BY_KEY = {c["key"]: c for c in CATALOG}

PANEL_COLUMNS = ["municipality", "oktmo", "indicator", "year", "value", "unit", "source"]
ACTIVITY_COLUMNS = ["enterprise", "year", "index", "source"]


def _read(path: str) -> list:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _num(value: str) -> float:
    return float(str(value).replace(" ", "").replace(",", "."))


def load_panel() -> dict:
    """Панель {(город, показатель): {год: (значение, источник)}} с наложением реальных данных."""
    panel = {}
    for path in (PANEL_CSV, REAL_CSV):
        for row in _read(path):
            if row["indicator"] not in BY_KEY or not row.get("value"):
                continue
            key = (row["municipality"], row["indicator"])
            panel.setdefault(key, {})[int(row["year"])] = (_num(row["value"]), row["source"])
    return panel


def load_activity() -> dict:
    """История активности {предприятие: {год: (индекс, источник)}}, индекс 2024 = 1."""
    out = {}
    for path in (ACTIVITY_CSV, REAL_ACTIVITY_CSV):
        for row in _read(path):
            out.setdefault(row["enterprise"], {})[int(row["year"])] = (_num(row["index"]), row["source"])
    return out


def series(panel: dict, city: str, key: str) -> dict:
    """Ряд показателя по годам: {год: значение}."""
    return {y: v for y, (v, _) in panel.get((city, key), {}).items()}


def provenance(panel: dict) -> dict:
    """Сколько значений панели пришло из каждого источника."""
    counts = {}
    for values in panel.values():
        for _, source in values.values():
            counts[source] = counts.get(source, 0) + 1
    return counts


def write_panel(rows: list, path: str = PANEL_CSV) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(PANEL_COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in PANEL_COLUMNS])


def write_activity(rows: list, path: str = ACTIVITY_CSV) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(ACTIVITY_COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in ACTIVITY_COLUMNS])
