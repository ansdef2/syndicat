"""Слой 2. Двойное экспоненциальное сглаживание (Хольт) + ограничитель шага.

Одинарного сглаживания недостаточно: отраслевой прибавочный продукт имеет
устойчивый тренд, и EWMA систематически отстаёт. Коэффициенты задаются через
полупериод, а не подбором: α = 1 − 2^(−1/h).
"""

import math
import random
from dataclasses import dataclass, field

from .constants import ALPHA, BETA, MAX_STEP


@dataclass
class HoltState:
    """Состояние двойного сглаживания: уровень L и тренд T."""

    level: float
    trend: float = 0.0
    alpha: float = ALPHA
    beta: float = BETA
    history: list = field(default_factory=list)

    def update(self, observation: float) -> float:
        prev_level = self.level
        self.level = self.alpha * observation + (1 - self.alpha) * (self.level + self.trend)
        self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * self.trend
        self.history.append(dict(observation=observation, level=self.level, trend=self.trend))
        return self.forecast()

    def forecast(self, steps: int = 1) -> float:
        return self.level + steps * self.trend


def clip_step(new: float, old: float, limit: float = MAX_STEP) -> float:
    """Механический ограничитель месячного шага базы: ±2% (якорь ожиданий)."""
    if old is None or old <= 0:
        return new
    ratio = new / old
    return old * min(max(ratio, 1 - limit), 1 + limit)


def observation_path(anchor: float, months: int, seed: int,
                     drift: float = 0.0035, sigma: float = 0.06):
    """Демонстрационный ряд наблюдений удельного прибавочного продукта.

    Детерминирован при фиксированном seed: один и тот же прогон платформы
    даёт один и тот же ряд. На калибровке заменяется фактическим рядом
    s_j(t) = [V_j(t) − W_j(t) − D_j(t)] / H_j(t) по данным формы П-1/П-4.
    """
    rng = random.Random(seed)
    return [anchor * (1.0 + drift * m) * (1.0 + rng.gauss(0.0, sigma))
            for m in range(months)]


def run_holt(observations, level0: float, trend0: float,
             alpha: float = ALPHA, beta: float = BETA):
    """Прогон сглаживания по ряду наблюдений. Возвращает состояние и трассу."""
    state = HoltState(level=level0, trend=trend0, alpha=alpha, beta=beta)
    trace = []
    for m, obs in enumerate(observations):
        forecast = state.update(obs)
        trace.append(dict(month=m, observation=obs, level=state.level,
                          trend=state.trend, forecast=forecast))
    return state, trace


def halflife_of(coef: float) -> float:
    """Обратное преобразование: полупериод по коэффициенту сглаживания."""
    if coef <= 0 or coef >= 1:
        return float("inf")
    return -1.0 / math.log2(1.0 - coef)
