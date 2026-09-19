# -*- coding: utf-8 -*-
"""Реестр экономических субъектов периметра ОКВЭД 20-30.

Наименования, местоположение и отраслевая принадлежность - фактические.
Категория размера определена по критериям Федерального закона № 209-ФЗ:

    среднее  - 251-1000 работников, годовой доход до 2 млрд руб.;
    крупное  - свыше 1000 работников либо доход свыше 2 млрд руб.

ВСЕ КОЛИЧЕСТВЕННЫЕ ПОКАЗАТЕЛИ (численность, выручка, основные фонды, фонд
рабочего времени, OEE, качество, нормативная трудоёмкость, цены изделий) -
ДЕМОНСТРАЦИОННАЯ КАЛИБРОВКА МОДЕЛИ, а не данные отчётности предприятий.
На этапе 2 дорожной карты они замещаются формами П-1, П-4, бухгалтерской
отчётностью и нормировочными справочниками самого предприятия.
"""

from . import industries as ind
from .constants import HOURS_PER_MONTH
from .tokens import calibrate, cycle_coef, emission, emission_breakdown, skill_coef

DISCLAIMER = ("Наименование, регион и класс ОКВЭД - фактические. "
              "Численность, выручка, фонды, трудоёмкость и цены - "
              "демонстрационная калибровка модели, подлежащая замене "
              "отчётностью предприятия (формы П-1, П-4) на этапе 2.")

# id, наименование, группа, город, ОКВЭД (подкласс), класс периметра,
# размер, численность, доля производственного персонала, выручка (млрд руб./год),
# основные фонды (млрд руб.), OEE, качество q, средний разряд,
# локализация, изделия
ENTERPRISES = [
    dict(id="nknh", name="ПАО «Нижнекамскнефтехим»", group="СИБУР",
         city="Нижнекамск, Республика Татарстан", okved="20.16", cls="20",
         size="крупное", headcount=16800, prod_share=0.72, revenue_bn=248.0,
         assets_bn=311.0, oee=0.83, quality=0.982, avg_grade=5.2, localization=0.88,
         products=[
             dict(sku="ПЭНД 273-83", name="Полиэтилен низкого давления, марка 273-83",
                  unit="т", norm_hours=3.4, market_price=118000, cycle_days=3, grade=5),
             dict(sku="СКИ-3", name="Каучук синтетический изопреновый СКИ-3",
                  unit="т", norm_hours=5.8, market_price=162000, cycle_days=6, grade=6),
         ]),
    dict(id="himprom", name="ПАО «Химпром»", group="Ренова",
         city="Новочебоксарск, Чувашская Республика", okved="20.13", cls="20",
         size="крупное", headcount=4300, prod_share=0.70, revenue_bn=19.4,
         assets_bn=14.2, oee=0.76, quality=0.973, avg_grade=4.9, localization=0.93,
         products=[
             dict(sku="NaOH-99", name="Сода каустическая твёрдая, сорт высший",
                  unit="т", norm_hours=9.2, market_price=42000, cycle_days=2, grade=5),
         ]),
    dict(id="biocad", name="АО «Биокад»", group="Biocad",
         city="Стрельна, Санкт-Петербург", okved="21.20", cls="21",
         size="крупное", headcount=3100, prod_share=0.58, revenue_bn=36.5,
         assets_bn=21.8, oee=0.71, quality=0.991, avg_grade=6.1, localization=0.74,
         products=[
             dict(sku="MAB-400", name="Препарат моноклональных антител, флакон 400 мг",
                  unit="уп.", norm_hours=1.9, market_price=38000, cycle_days=28, grade=7),
         ]),
    dict(id="ufavita", name="ОАО «Фармстандарт-УфаВИТА»", group="Фармстандарт",
         city="Уфа, Республика Башкортостан", okved="21.20", cls="21",
         size="крупное", headcount=1450, prod_share=0.66, revenue_bn=11.2,
         assets_bn=5.4, oee=0.79, quality=0.987, avg_grade=5.0, localization=0.81,
         products=[
             dict(sku="TAB-500", name="Таблетированная форма, упаковка 20 шт.",
                  unit="уп.", norm_hours=0.05, market_price=420, cycle_days=14, grade=4),
         ]),
    dict(id="gaztrubplast", name="АО «Завод АНД Газтрубпласт»", group="ПОЛИПЛАСТИК",
         city="Москва", okved="22.21", cls="22",
         size="крупное", headcount=1320, prod_share=0.74, revenue_bn=14.8,
         assets_bn=6.1, oee=0.81, quality=0.976, avg_grade=4.4, localization=0.94,
         products=[
             dict(sku="ПЭ100-SDR17-110", name="Труба ПЭ100 SDR17 d110 напорная",
                  unit="м", norm_hours=0.018, market_price=412, cycle_days=2, grade=4),
             dict(sku="ПП-R-PN10-110", name="Труба ПП-R PN10 d110",
                  unit="м", norm_hours=0.021, market_price=468, cycle_days=2, grade=4),
         ]),
    dict(id="kursk_rti", name="АО «Курскрезинотехника»", group="—",
         city="Курск", okved="22.19", cls="22",
         size="крупное", headcount=2600, prod_share=0.77, revenue_bn=9.6,
         assets_bn=4.3, oee=0.72, quality=0.964, avg_grade=4.6, localization=0.96,
         products=[
             dict(sku="ЛК-800", name="Лента конвейерная резинотканевая 800 мм",
                  unit="м", norm_hours=0.42, market_price=5400, cycle_days=3, grade=5),
         ]),
    dict(id="sebryakov", name="ОАО «Себряковцемент»", group="—",
         city="Михайловка, Волгоградская область", okved="23.51", cls="23",
         size="крупное", headcount=1900, prod_share=0.75, revenue_bn=16.3,
         assets_bn=12.9, oee=0.85, quality=0.981, avg_grade=4.8, localization=0.99,
         products=[
             dict(sku="ЦЕМ-I-42.5Н", name="Портландцемент ЦЕМ I 42,5Н, навал",
                  unit="т", norm_hours=0.62, market_price=6900, cycle_days=1, grade=4),
         ]),
    dict(id="severstal", name="ПАО «Северсталь»", group="Северсталь",
         city="Череповец, Вологодская область", okved="24.10", cls="24",
         size="крупное", headcount=24600, prod_share=0.74, revenue_bn=728.0,
         assets_bn=612.0, oee=0.88, quality=0.984, avg_grade=5.4, localization=0.91,
         products=[
             dict(sku="ГК-2.0x1250", name="Рулон горячекатаный 2,0×1250, Ст3сп",
                  unit="т", norm_hours=1.9, market_price=62000, cycle_days=4, grade=5),
         ]),
    dict(id="vmz", name="АО «Выксунский металлургический завод»", group="ОМК",
         city="Выкса, Нижегородская область", okved="24.20", cls="24",
         size="крупное", headcount=12400, prod_share=0.76, revenue_bn=298.0,
         assets_bn=214.0, oee=0.84, quality=0.979, avg_grade=5.3, localization=0.95,
         products=[
             dict(sku="ЭСВ-530x8", name="Труба электросварная 530×8, сталь 09Г2С",
                  unit="т", norm_hours=3.1, market_price=78000, cycle_days=5, grade=5),
         ]),
    dict(id="kovrov_mz", name="АО «Ковровский механический завод»", group="ТВЭЛ",
         city="Ковров, Владимирская область", okved="25.40", cls="25",
         size="крупное", headcount=2200, prod_share=0.71, revenue_bn=8.9,
         assets_bn=6.7, oee=0.74, quality=0.988, avg_grade=5.6, localization=0.98,
         products=[
             dict(sku="УЗЛ-МХ", name="Узел механической обработки, серийная позиция",
                  unit="шт.", norm_hours=11.4, market_price=34500, cycle_days=12, grade=6),
         ]),
    dict(id="mikron", name="ПАО «Микрон»", group="Элемент",
         city="Зеленоград, Москва", okved="26.11", cls="26",
         size="крупное", headcount=1600, prod_share=0.61, revenue_bn=12.4,
         assets_bn=18.3, oee=0.69, quality=0.993, avg_grade=6.3, localization=0.67,
         products=[
             dict(sku="ЧИП-М180", name="Чип-модуль, технология 180 нм",
                  unit="шт.", norm_hours=0.0032, market_price=95, cycle_days=45, grade=6),
         ]),
    dict(id="cheaz", name="АО «Чебоксарский электроаппаратный завод»", group="ЧЭАЗ",
         city="Чебоксары, Чувашская Республика", okved="27.12", cls="27",
         size="крупное", headcount=2450, prod_share=0.69, revenue_bn=13.1,
         assets_bn=5.2, oee=0.73, quality=0.977, avg_grade=5.5, localization=0.89,
         products=[
             dict(sku="НКУ-0.4", name="Шкаф НКУ 0,4 кВ, комплектная сборка",
                  unit="шт.", norm_hours=46.0, market_price=320000, cycle_days=25, grade=6),
         ]),
    # --- фокусная отрасль: класс 28, насосное и компрессорное оборудование ---
    dict(id="livgidromash", name="АО «ГМС Ливгидромаш»", group="Группа ГМС",
         city="Ливны, Орловская область", okved="28.13", cls="28",
         size="крупное", headcount=2700, prod_share=0.72, revenue_bn=11.8,
         assets_bn=6.9, oee=0.75, quality=0.981, avg_grade=5.4, localization=0.92,
         focus=True,
         products=[
             dict(sku="К100-65-200", name="Насос консольный К100-65-200",
                  unit="шт.", norm_hours=62.5, market_price=186000, cycle_days=45, grade=6),
             dict(sku="ЦНС180-212", name="Насос секционный ЦНС 180-212",
                  unit="шт.", norm_hours=402.0, market_price=1460000, cycle_days=75, grade=6),
             dict(sku="АХ50-32-160", name="Насос химический АХ 50-32-160",
                  unit="шт.", norm_hours=44.0, market_price=128000, cycle_days=35, grade=5),
         ]),
    dict(id="chkz", name="ООО «Челябинский компрессорный завод»", group="ЧКЗ",
         city="Челябинск", okved="28.13", cls="28",
         size="среднее", headcount=640, prod_share=0.68, revenue_bn=1.85,
         assets_bn=0.94, oee=0.71, quality=0.969, avg_grade=5.1, localization=0.78,
         focus=True,
         products=[
             dict(sku="ВК-30", name="Компрессор винтовой ВК-30, 30 кВт",
                  unit="шт.", norm_hours=118.0, market_price=720000, cycle_days=30, grade=6),
             dict(sku="ВК-7.5", name="Компрессор винтовой ВК-7,5",
                  unit="шт.", norm_hours=41.0, market_price=240000, cycle_days=21, grade=5),
         ]),
    dict(id="ptpa", name="АО «Пензтяжпромарматура»", group="ПТПА",
         city="Пенза", okved="28.14", cls="28",
         size="среднее", headcount=910, prod_share=0.73, revenue_bn=1.96,
         assets_bn=1.32, oee=0.70, quality=0.974, avg_grade=5.7, localization=0.95,
         focus=True,
         products=[
             dict(sku="ЗКЛ-200-16", name="Задвижка клиновая Ду200 Ру16",
                  unit="шт.", norm_hours=34.0, market_price=148000, cycle_days=28, grade=6),
             dict(sku="КШ-300", name="Кран шаровой Ду300 Ру25",
                  unit="шт.", norm_hours=96.0, market_price=520000, cycle_days=40, grade=6),
         ]),
    dict(id="uralmash", name="ПАО «Уралмашзавод»", group="УЗТМ-КАРТЭКС",
         city="Екатеринбург, Свердловская область", okved="28.92", cls="28",
         size="крупное", headcount=4600, prod_share=0.70, revenue_bn=42.0,
         assets_bn=27.5, oee=0.66, quality=0.986, avg_grade=6.0, localization=0.93,
         focus=True,
         products=[
             dict(sku="КСД-1750", name="Дробилка конусная КСД-1750",
                  unit="шт.", norm_hours=3850.0, market_price=22500000, cycle_days=150, grade=6),
         ]),
    dict(id="kamaz", name="ПАО «КАМАЗ»", group="КАМАЗ",
         city="Набережные Челны, Республика Татарстан", okved="29.10", cls="29",
         size="крупное", headcount=24800, prod_share=0.78, revenue_bn=386.0,
         assets_bn=188.0, oee=0.80, quality=0.971, avg_grade=4.9, localization=0.86,
         products=[
             dict(sku="54901", name="Седельный тягач KAMAZ-54901",
                  unit="шт.", norm_hours=318.0, market_price=9800000, cycle_days=22, grade=5),
         ]),
    dict(id="tvz", name="АО «Тверской вагоностроительный завод»", group="Трансмашхолдинг",
         city="Тверь", okved="30.20", cls="30",
         size="крупное", headcount=6200, prod_share=0.75, revenue_bn=64.0,
         assets_bn=31.0, oee=0.68, quality=0.983, avg_grade=5.8, localization=0.90,
         products=[
             dict(sku="61-4517", name="Вагон пассажирский купейный, модель 61-4517",
                  unit="шт.", norm_hours=9600.0, market_price=78000000, cycle_days=180, grade=6),
         ]),
]

BY_ID = {e["id"]: e for e in ENTERPRISES}

# Структура производственного персонала по разрядам ЕТКС (доли).
# Смещается вокруг среднего разряда предприятия.
GRADE_SCALE = [2, 3, 4, 5, 6, 7]


def personnel_profile(ent: dict) -> list:
    """Раскладка производственного персонала по разрядам вокруг среднего."""
    avg = ent["avg_grade"]
    weights = [1.0 / (1.0 + (g - avg) ** 2) for g in GRADE_SCALE]
    total_w = sum(weights)
    prod_staff = ent["headcount"] * ent["prod_share"]
    rows = []
    for g, w in zip(GRADE_SCALE, weights):
        share = w / total_w
        headcount = round(prod_staff * share)
        # тарифная ставка разряда от средней зарплаты класса ОКВЭД
        base_wage = ind.INDUSTRIES[ent["cls"]]["wage"]
        wage = base_wage * skill_coef(g) / skill_coef(round(avg))
        rows.append(dict(grade=g, headcount=headcount, share=share,
                         wage_month=wage, skill_coef=skill_coef(g)))
    return rows


def hours_month(ent: dict) -> float:
    """Фонд отработанного времени производственного персонала, чел.-ч/мес."""
    return ent["headcount"] * ent["prod_share"] * HOURS_PER_MONTH


def profile(ent_id: str, phi: float = None) -> dict:
    """Полный расчётный профиль предприятия: эмиссия ТЧЧ, фонды, показатели."""
    from .constants import PHI
    phi = PHI if phi is None else phi
    ent = BY_ID[ent_id]
    calib = calibrate(phi)
    row = calib["industries"][ent["cls"]]
    B, k = calib["B"], row["k"]

    hours = hours_month(ent)
    k_skill = skill_coef(round(ent["avg_grade"]))
    k_cycle = cycle_coef(ind.INDUSTRIES[ent["cls"]]["cycle"])
    tokens_month = emission(t_fact=hours, t_norm=hours * ent["oee"] / 0.75,
                            grade=round(ent["avg_grade"]),
                            cycle_days=ind.INDUSTRIES[ent["cls"]]["cycle"],
                            quality=ent["quality"], k_ind=k)
    tokens_rub = tokens_month * B

    staff = personnel_profile(ent)
    payroll = sum(r["headcount"] * r["wage_month"] for r in staff)
    revenue_month = ent["revenue_bn"] * 1e9 / 12.0
    vds_month = revenue_month * ind.INDUSTRIES[ent["cls"]]["psi"]
    surplus_month = vds_month * row["capital_share"]
    socialised = phi * surplus_month

    return dict(
        enterprise=dict(**{key: ent[key] for key in
                           ("id", "name", "group", "city", "okved", "cls", "size",
                            "headcount", "prod_share", "revenue_bn", "assets_bn",
                            "oee", "quality", "avg_grade", "localization")},
                        industry=ind.name(ent["cls"]), industry_short=ind.short(ent["cls"]),
                        focus=ent.get("focus", False), products=ent["products"]),
        B=B, k=k, mu=row["mu"], base_hour=row["base"],
        hours_month=hours, tokens_month=tokens_month, tokens_rub=tokens_rub,
        tokens_per_hour=tokens_month / hours if hours else 0.0,
        k_skill=k_skill, k_cycle=k_cycle,
        payroll_month=payroll, revenue_month=revenue_month,
        vds_month=vds_month, surplus_month=surplus_month, socialised_month=socialised,
        capital_per_worker=ent["assets_bn"] * 1e9 / ent["headcount"],
        revenue_per_worker=ent["revenue_bn"] * 1e9 / ent["headcount"],
        vds_per_hour=vds_month / hours if hours else 0.0,
        staff=staff,
        disclaimer=DISCLAIMER,
    )


def product_emission(ent: dict, product: dict, k: float) -> dict:
    """Эмиссия ТЧЧ на изделие с расшифровкой множителей."""
    t_norm = product["norm_hours"]
    t_fact = t_norm / max(ent["oee"], 0.3) * 0.82   # факт с учётом простоев
    return emission_breakdown(t_fact=t_fact, t_norm=t_norm,
                              grade=product.get("grade", round(ent["avg_grade"])),
                              cycle_days=product.get("cycle_days", 30),
                              quality=ent["quality"], k_ind=k)


def list_enterprises(phi: float = None) -> list:
    """Сводка по реестру - для таблицы и сравнительных диаграмм."""
    out = []
    for ent in ENTERPRISES:
        p = profile(ent["id"], phi)
        out.append(dict(
            id=ent["id"], name=ent["name"], short=ent["name"].split("«")[-1].rstrip("»"),
            group=ent["group"], city=ent["city"], okved=ent["okved"], cls=ent["cls"],
            industry_short=ind.short(ent["cls"]), size=ent["size"],
            headcount=ent["headcount"], revenue_bn=ent["revenue_bn"],
            assets_bn=ent["assets_bn"], oee=ent["oee"], quality=ent["quality"],
            avg_grade=ent["avg_grade"], localization=ent["localization"],
            focus=ent.get("focus", False),
            hours_month=p["hours_month"], tokens_month=p["tokens_month"],
            tokens_rub=p["tokens_rub"], tokens_per_hour=p["tokens_per_hour"],
            payroll_month=p["payroll_month"], vds_per_hour=p["vds_per_hour"],
            capital_per_worker=p["capital_per_worker"],
            revenue_per_worker=p["revenue_per_worker"],
            k=p["k"], products=len(ent["products"]),
        ))
    return out
