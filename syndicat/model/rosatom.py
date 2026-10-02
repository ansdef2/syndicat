# -*- coding: utf-8 -*-
"""Территориальная сетка: предприятия группы Госкорпорации «Росатом».

Только данные, без расчёта: расчёт - в territories.py.

Наименования, города, регионы, статус ЗАТО и коды ОКВЭД - фактические.
ВСЕ КОЛИЧЕСТВЕННЫЕ ПОКАЗАТЕЛИ (численность, фонды, объёмы выпуска, цены,
внутригрупповые поставки, население городов) - ДЕМОНСТРАЦИОННАЯ КАЛИБРОВКА
МОДЕЛИ, а не данные отчётности. Они подобраны так, чтобы воспроизводить
структуру цепочки «добыча → конверсия → обогащение → фабрикация топлива →
генерация» и порядок величин, и подлежат замене годовым отчётом
Госкорпорации, отчётностью предприятий (формы П-1, П-4) и данными Росстата
по муниципальным образованиям (БДПМО).

Поставки внутри группы заданы в натуральных единицах: (получатель, объём, вид).
Вид "intermediate" - промежуточное потребление (входит в матрицу A группы),
"capital" - поставка оборудования в основные фонды получателя (в матрицу A
не входит, но учитывается во внутригрупповом обороте и в инвестициях
в территорию).
"""

GROUP = "Госкорпорация «Росатом»"

DISCLAIMER = ("Наименования, города, регионы, статус ЗАТО и коды ОКВЭД - фактические. "
              "Численность, фонды, объёмы выпуска, цены, внутригрупповые поставки "
              "и население - демонстрационная калибровка модели, подлежащая замене "
              "годовым отчётом Госкорпорации, отчётностью предприятий и данными "
              "Росстата по муниципальным образованиям.")

# Дивизионы в порядке технологической цепочки
DIVISIONS = [
    dict(key="mining", name="Горнорудный дивизион", short="Добыча"),
    dict(key="fuel", name="Топливный дивизион (ТВЭЛ)", short="Топливо"),
    dict(key="radiochem", name="Радиохимия и изотопы", short="Радиохимия"),
    dict(key="machine", name="Машиностроительный дивизион (Атомэнергомаш)", short="Машиностроение"),
    dict(key="power", name="Электроэнергетический дивизион (Росэнергоатом)", short="Генерация"),
]

# Города присутствия. population - DEMO, округлённо.
CITIES = {
    "krasnokamensk": dict(name="Краснокаменск", region="Забайкальский край", zato=False, population=50000),
    "seversk": dict(name="Северск", region="Томская область", zato=True, population=105000),
    "novouralsk": dict(name="Новоуральск", region="Свердловская область", zato=True, population=79000),
    "zelenogorsk": dict(name="Зеленогорск", region="Красноярский край", zato=True, population=60000),
    "angarsk": dict(name="Ангарск", region="Иркутская область", zato=False, population=220000),
    "elektrostal": dict(name="Электросталь", region="Московская область", zato=False, population=155000),
    "novosibirsk": dict(name="Новосибирск", region="Новосибирская область", zato=False, population=1630000),
    "glazov": dict(name="Глазов", region="Удмуртская Республика", zato=False, population=89000),
    "ozersk": dict(name="Озёрск", region="Челябинская область", zato=True, population=80000),
    "zheleznogorsk": dict(name="Железногорск", region="Красноярский край", zato=True, population=85000),
    "volgodonsk": dict(name="Волгодонск", region="Ростовская область", zato=False, population=165000),
    "podolsk": dict(name="Подольск", region="Московская область", zato=False, population=310000),
    "spb": dict(name="Санкт-Петербург", region="г. Санкт-Петербург", zato=False, population=5600000),
    "petrozavodsk": dict(name="Петрозаводск", region="Республика Карелия", zato=False, population=280000),
    "udomlya": dict(name="Удомля", region="Тверская область", zato=False, population=28000),
    "desnogorsk": dict(name="Десногорск", region="Смоленская область", zato=False, population=27000),
    "polyarnye_zori": dict(name="Полярные Зори", region="Мурманская область", zato=False, population=14000),
    "sosnovy_bor": dict(name="Сосновый Бор", region="Ленинградская область", zato=False, population=66000),
    "novovoronezh": dict(name="Нововоронеж", region="Воронежская область", zato=False, population=30000),
    "kurchatov": dict(name="Курчатов", region="Курская область", zato=False, population=37000),
    "zarechny": dict(name="Заречный", region="Свердловская область", zato=False, population=32000),
    "balakovo": dict(name="Балаково", region="Саратовская область", zato=False, population=185000),
}

_NPP = "филиал АО «Концерн Росэнергоатом»"
_ELECTRICITY_PRICE = 2100   # руб./МВт·ч, DEMO: средняя цена с учётом мощности


def _npp(id_, name, city, headcount, assets_bn, mwh, oee):
    return dict(id=id_, name=f"{name} ({_NPP})", short=name, division="power", stage=5,
                city_id=city, okved="35.11", cls="35", size="крупное",
                headcount=headcount, prod_share=0.70, assets_bn=assets_bn, oee=oee,
                quality=0.995, avg_grade=5.8, localization=0.97,
                products=[dict(sku=f"ЭЭ-{id_}", name="Электроэнергия на оптовый рынок",
                               unit="МВт·ч", volume=mwh, market_price=_ELECTRICITY_PRICE,
                               norm_hours=0.15, cycle_days=1, grade=6,
                               export_share=0.0, supplies=[])])


ENTERPRISES = [
    # ------------------------------------------------------------ добыча
    dict(id="ppgho", name="ПАО «Приаргунское производственное горно-химическое объединение»",
         short="ППГХО", division="mining", stage=1, city_id="krasnokamensk",
         okved="07.21", cls="07", size="крупное", headcount=5200, prod_share=0.74,
         assets_bn=40.0, oee=0.70, quality=0.975, avg_grade=4.8, localization=0.97,
         products=[
             dict(sku="U3O8", name="Закись-окись урана (концентрат)", unit="т U",
                  volume=1400, market_price=18_500_000, norm_hours=4800, cycle_days=60,
                  grade=5, export_share=1.0,
                  supplies=[("skhk", 770, "intermediate"), ("aekhk", 70, "intermediate")]),
         ]),
    # ------------------------------------------------- конверсия и обогащение
    dict(id="skhk", name="АО «Сибирский химический комбинат»", short="СХК",
         division="fuel", stage=2, city_id="seversk", okved="24.46", cls="24",
         size="крупное", headcount=4800, prod_share=0.70, assets_bn=70.0, oee=0.80,
         quality=0.985, avg_grade=5.3, localization=0.95,
         products=[
             dict(sku="UF6-СХК", name="Конверсия урана в гексафторид", unit="т U",
                  volume=12000, market_price=1_300_000, norm_hours=210, cycle_days=10,
                  grade=5, export_share=1.0,
                  supplies=[("uekhk", 4800, "intermediate"), ("ekhz", 3600, "intermediate")]),
             dict(sku="ЕРР-СХК", name="Обогащение урана", unit="тыс. ЕРР",
                  volume=4500, market_price=7_000_000, norm_hours=900, cycle_days=20,
                  grade=6, export_share=1.0,
                  supplies=[("msz", 1350, "intermediate"), ("nzhk", 450, "intermediate")]),
         ]),
    dict(id="aekhk", name="АО «Ангарский электролизный химический комбинат»", short="АЭХК",
         division="fuel", stage=2, city_id="angarsk", okved="24.46", cls="24",
         size="крупное", headcount=2100, prod_share=0.70, assets_bn=25.0, oee=0.74,
         quality=0.980, avg_grade=5.1, localization=0.95,
         products=[
             dict(sku="UF6-АЭХК", name="Конверсия урана в гексафторид", unit="т U",
                  volume=5000, market_price=1_300_000, norm_hours=230, cycle_days=10,
                  grade=5, export_share=1.0,
                  supplies=[("uekhk", 1500, "intermediate"), ("ekhz", 1000, "intermediate")]),
             dict(sku="ЕРР-АЭХК", name="Обогащение урана", unit="тыс. ЕРР",
                  volume=2000, market_price=7_000_000, norm_hours=850, cycle_days=20,
                  grade=6, export_share=1.0,
                  supplies=[("msz", 400, "intermediate")]),
         ]),
    dict(id="uekhk", name="АО «Уральский электрохимический комбинат»", short="УЭХК",
         division="fuel", stage=3, city_id="novouralsk", okved="24.46", cls="24",
         size="крупное", headcount=4800, prod_share=0.72, assets_bn=90.0, oee=0.86,
         quality=0.990, avg_grade=5.6, localization=0.98,
         products=[
             dict(sku="ЕРР-УЭХК", name="Обогащение урана", unit="тыс. ЕРР",
                  volume=7000, market_price=7_000_000, norm_hours=950, cycle_days=20,
                  grade=6, export_share=1.0,
                  supplies=[("msz", 2100, "intermediate"), ("nzhk", 350, "intermediate")]),
         ]),
    dict(id="ekhz", name="АО «ПО «Электрохимический завод»", short="ЭХЗ",
         division="fuel", stage=3, city_id="zelenogorsk", okved="24.46", cls="24",
         size="крупное", headcount=3400, prod_share=0.72, assets_bn=60.0, oee=0.84,
         quality=0.989, avg_grade=5.5, localization=0.97,
         products=[
             dict(sku="ЕРР-ЭХЗ", name="Обогащение урана", unit="тыс. ЕРР",
                  volume=4200, market_price=7_000_000, norm_hours=900, cycle_days=20,
                  grade=6, export_share=1.0,
                  supplies=[("msz", 1260, "intermediate"), ("nzhk", 210, "intermediate")]),
             dict(sku="ИЗО-ЭХЗ", name="Стабильные изотопы", unit="партия",
                  volume=300, market_price=15_000_000, norm_hours=1400, cycle_days=45,
                  grade=7, export_share=0.9, supplies=[]),
         ]),
    dict(id="chmz", name="АО «Чепецкий механический завод»", short="ЧМЗ",
         division="fuel", stage=3, city_id="glazov", okved="24.45", cls="24",
         size="крупное", headcount=2600, prod_share=0.70, assets_bn=22.0, oee=0.76,
         quality=0.982, avg_grade=5.2, localization=0.96,
         products=[
             dict(sku="Zr-ЧМЗ", name="Циркониевый прокат и трубы-оболочки", unit="т",
                  volume=2600, market_price=7_500_000, norm_hours=1150, cycle_days=40,
                  grade=6, export_share=0.8,
                  supplies=[("msz", 1300, "intermediate"), ("nzhk", 650, "intermediate")]),
             dict(sku="Ca-ЧМЗ", name="Кальций металлический", unit="т",
                  volume=1500, market_price=1_200_000, norm_hours=380, cycle_days=15,
                  grade=5, export_share=0.6, supplies=[]),
         ]),
    # ------------------------------------------------- фабрикация топлива
    dict(id="msz", name="ПАО «Машиностроительный завод»", short="МСЗ",
         division="fuel", stage=4, city_id="elektrostal", okved="24.46", cls="24",
         size="крупное", headcount=7200, prod_share=0.72, assets_bn=45.0, oee=0.82,
         quality=0.992, avg_grade=5.5, localization=0.96,
         products=[
             dict(sku="ТВС-1000", name="ТВС для реакторов ВВЭР-1000/1200", unit="шт.",
                  volume=700, market_price=70_000_000, norm_hours=9200, cycle_days=60,
                  grade=6, export_share=1.0,
                  supplies=[("kalinin", 120, "intermediate"), ("balakovo", 120, "intermediate"),
                            ("rostov", 80, "intermediate"), ("novovoronezh", 60, "intermediate"),
                            ("leningrad", 40, "intermediate")]),
             dict(sku="ТВС-РБМК", name="ТВС для реакторов РБМК-1000", unit="шт.",
                  volume=600, market_price=25_000_000, norm_hours=3600, cycle_days=45,
                  grade=6, export_share=0.0,
                  supplies=[("leningrad", 150, "intermediate"), ("smolensk", 250, "intermediate"),
                            ("kursk", 200, "intermediate")]),
             dict(sku="РК-440", name="Рабочие кассеты ВВЭР-440", unit="шт.",
                  volume=400, market_price=20_000_000, norm_hours=2900, cycle_days=45,
                  grade=6, export_share=1.0,
                  supplies=[("kola", 100, "intermediate"), ("novovoronezh", 30, "intermediate")]),
         ]),
    dict(id="nzhk", name="ПАО «Новосибирский завод химконцентратов»", short="НЗХК",
         division="fuel", stage=4, city_id="novosibirsk", okved="24.46", cls="24",
         size="крупное", headcount=2500, prod_share=0.70, assets_bn=18.0, oee=0.78,
         quality=0.988, avg_grade=5.3, localization=0.94,
         products=[
             dict(sku="ТВС-1000-Н", name="ТВС для реакторов ВВЭР-1000", unit="шт.",
                  volume=300, market_price=70_000_000, norm_hours=9600, cycle_days=60,
                  grade=6, export_share=1.0,
                  supplies=[("kalinin", 30, "intermediate"), ("balakovo", 30, "intermediate"),
                            ("rostov", 70, "intermediate"), ("novovoronezh", 50, "intermediate"),
                            ("leningrad", 30, "intermediate")]),
             dict(sku="Li7", name="Литий-7 и его соединения", unit="т",
                  volume=200, market_price=18_000_000, norm_hours=1500, cycle_days=30,
                  grade=6, export_share=0.7, supplies=[]),
         ]),
    # ------------------------------------------------- радиохимия и изотопы
    dict(id="mayak", name="ФГУП «ПО «Маяк»", short="ПО «Маяк»",
         division="radiochem", stage=4, city_id="ozersk", okved="24.46", cls="24",
         size="крупное", headcount=7500, prod_share=0.66, assets_bn=85.0, oee=0.70,
         quality=0.990, avg_grade=5.6, localization=0.98,
         products=[
             dict(sku="ОЯТ-М", name="Переработка отработавшего ядерного топлива", unit="т ОЯТ",
                  volume=220, market_price=80_000_000, norm_hours=26000, cycle_days=120,
                  grade=6, export_share=0.5,
                  supplies=[("kola", 66, "intermediate"), ("novovoronezh", 44, "intermediate"),
                            ("beloyarsk", 22, "intermediate")]),
             dict(sku="ИЗО-М", name="Радиоизотопная продукция", unit="партия",
                  volume=2200, market_price=12_000_000, norm_hours=1300, cycle_days=30,
                  grade=6, export_share=0.85, supplies=[]),
             dict(sku="ИИ-М", name="Источники ионизирующего излучения", unit="партия",
                  volume=600, market_price=20_000_000, norm_hours=3000, cycle_days=40,
                  grade=6, export_share=0.7, supplies=[]),
         ]),
    dict(id="ghk", name="ФГУП «Горно-химический комбинат»", short="ГХК",
         division="radiochem", stage=4, city_id="zheleznogorsk", okved="24.46", cls="24",
         size="крупное", headcount=4800, prod_share=0.68, assets_bn=60.0, oee=0.72,
         quality=0.990, avg_grade=5.7, localization=0.97,
         products=[
             dict(sku="МОКС", name="МОКС-топливо для реактора БН-800", unit="ТВС",
                  volume=100, market_price=60_000_000, norm_hours=26000, cycle_days=90,
                  grade=7, export_share=0.0,
                  supplies=[("beloyarsk", 100, "intermediate")]),
             dict(sku="ОЯТ-Х", name="Хранение и переработка ОЯТ", unit="т ОЯТ",
                  volume=400, market_price=30_000_000, norm_hours=7000, cycle_days=60,
                  grade=6, export_share=0.0,
                  supplies=[("kalinin", 80, "intermediate"), ("balakovo", 80, "intermediate"),
                            ("rostov", 80, "intermediate"), ("leningrad", 40, "intermediate"),
                            ("smolensk", 20, "intermediate"), ("kursk", 20, "intermediate")]),
             dict(sku="ИЗО-Г", name="Изотопная и радиохимическая продукция", unit="партия",
                  volume=1500, market_price=12_000_000, norm_hours=2400, cycle_days=40,
                  grade=6, export_share=0.6, supplies=[]),
         ]),
    # ------------------------------------------------- машиностроение
    dict(id="atommash", name="Филиал АО «АЭМ-технологии» «Атоммаш»", short="Атоммаш",
         division="machine", stage=4, city_id="volgodonsk", okved="25.30", cls="25",
         size="крупное", headcount=3600, prod_share=0.70, assets_bn=30.0, oee=0.72,
         quality=0.986, avg_grade=5.8, localization=0.93,
         products=[
             dict(sku="КР-1200", name="Корпус реактора ВВЭР-1200", unit="шт.",
                  volume=3, market_price=3_000_000_000, norm_hours=480000, cycle_days=540,
                  grade=7, export_share=1.0,
                  supplies=[("leningrad", 1, "capital"), ("kursk", 1, "capital")]),
             dict(sku="ПГВ-1000", name="Парогенератор ПГВ-1000МКП", unit="шт.",
                  volume=16, market_price=700_000_000, norm_hours=110000, cycle_days=360,
                  grade=6, export_share=1.0,
                  supplies=[("leningrad", 4, "capital"), ("kursk", 4, "capital")]),
         ]),
    dict(id="zio", name="АО «ЗиО-Подольск»", short="ЗиО-Подольск",
         division="machine", stage=4, city_id="podolsk", okved="25.30", cls="25",
         size="крупное", headcount=3300, prod_share=0.70, assets_bn=18.0, oee=0.70,
         quality=0.984, avg_grade=5.6, localization=0.94,
         products=[
             dict(sku="ОРУ", name="Оборудование реакторной и машинной установки (комплект)",
                  unit="комплект", volume=40, market_price=450_000_000, norm_hours=68000,
                  cycle_days=300, grade=6, export_share=1.0,
                  supplies=[("leningrad", 6, "capital"), ("kursk", 6, "capital")]),
         ]),
    dict(id="ckbm", name="АО «ЦКБМ»", short="ЦКБМ", division="machine", stage=4,
         city_id="spb", okved="28.13", cls="28", size="крупное", headcount=1800,
         prod_share=0.66, assets_bn=9.0, oee=0.71, quality=0.988, avg_grade=6.0,
         localization=0.90,
         products=[
             dict(sku="ГЦНА-1391", name="Главный циркуляционный насосный агрегат", unit="шт.",
                  volume=24, market_price=400_000_000, norm_hours=72000, cycle_days=300,
                  grade=7, export_share=1.0,
                  supplies=[("leningrad", 4, "capital"), ("kursk", 4, "capital")]),
         ]),
    dict(id="petrozavodskmash", name="АО «Петрозаводскмаш»", short="Петрозаводскмаш",
         division="machine", stage=4, city_id="petrozavodsk", okved="25.30", cls="25",
         size="крупное", headcount=1300, prod_share=0.72, assets_bn=7.0, oee=0.70,
         quality=0.980, avg_grade=5.2, localization=0.95,
         products=[
             dict(sku="ЕМК", name="Корпуса ёмкостного и теплообменного оборудования", unit="т",
                  volume=5200, market_price=1_400_000, norm_hours=310, cycle_days=180,
                  grade=6, export_share=0.9,
                  supplies=[("leningrad", 600, "capital"), ("kursk", 600, "capital")]),
         ]),
    # ------------------------------------------------- генерация
    _npp("kalinin", "Калининская АЭС", "udomlya", 3600, 180.0, 29_800_000, 0.88),
    _npp("smolensk", "Смоленская АЭС", "desnogorsk", 3700, 120.0, 22_300_000, 0.84),
    _npp("kola", "Кольская АЭС", "polyarnye_zori", 2300, 90.0, 12_500_000, 0.74),
    _npp("leningrad", "Ленинградская АЭС", "sosnovy_bor", 5200, 320.0, 32_600_000, 0.86),
    _npp("novovoronezh", "Нововоронежская АЭС", "novovoronezh", 3900, 290.0, 28_100_000, 0.85),
    _npp("kursk", "Курская АЭС", "kurchatov", 4100, 260.0, 22_300_000, 0.83),
    _npp("beloyarsk", "Белоярская АЭС", "zarechny", 2600, 200.0, 13_500_000, 0.86),
    _npp("balakovo", "Балаковская АЭС", "balakovo", 3700, 170.0, 29_800_000, 0.88),
    _npp("rostov", "Ростовская АЭС", "volgodonsk", 3300, 210.0, 29_800_000, 0.87),
]

# Совместимость с моделью периметра: город, группа и выручка выводятся из данных.
for _e in ENTERPRISES:
    _e["group"] = GROUP
    _e["city"] = f'{CITIES[_e["city_id"]]["name"]}, {CITIES[_e["city_id"]]["region"]}'
    _e["revenue_bn"] = sum(p["volume"] * p["market_price"] for p in _e["products"]) / 1e9

BY_ID = {e["id"]: e for e in ENTERPRISES}
