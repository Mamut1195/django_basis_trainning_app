"""Versioned, unit-explicit manual sport variables. None always means unknown."""

from dataclasses import dataclass
from decimal import Decimal

from .execution import Metric, MetricName

SPORTS = [
    ("strength", "Fuerza"),
    ("cardio", "Cardio"),
    ("running", "Running"),
    ("cycling", "Ciclismo"),
    ("swimming", "Natación"),
    ("hiking", "Hiking / senderismo"),
]
SPORT_LABELS = dict(SPORTS)


@dataclass(frozen=True)
class Variable:
    label: str
    unit: str = ""
    maximum: int = 1000000
    kind: str = "number"
    choices: tuple[str, ...] = ()


COMMON = {
    "duration_seconds": Variable("Duración transcurrida", "s"),
    "distance_m": Variable("Distancia", "m"),
    "heart_rate_bpm": Variable("Frecuencia cardíaca media medida", "lpm", 250),
    "max_heart_rate_bpm": Variable("Frecuencia cardíaca máxima medida", "lpm", 250),
    "session_type": Variable("Tipo de sesión", kind="text"),
    "surface": Variable("Superficie", kind="text"),
}
OUTDOOR = {
    "moving_seconds": Variable("Tiempo en movimiento", "s"),
    "pause_seconds": Variable("Pausas excluidas", "s"),
    "ascent_m": Variable("Ascenso acumulado", "m"),
    "descent_m": Variable("Descenso acumulado", "m"),
    "start_altitude_m": Variable("Altitud inicial", "m", 9000, "altitude"),
    "max_altitude_m": Variable("Altitud máxima", "m", 9000, "altitude"),
    "end_altitude_m": Variable("Altitud final", "m", 9000, "altitude"),
    "pack_kg": Variable("Peso de mochila", "kg", 150),
    "terrain": Variable("Terreno", kind="text"),
    "difficulty_scale": Variable("Escala de dificultad declarada", kind="text"),
    "difficulty_grade": Variable("Grado declarado", kind="text"),
    "difficulty_source": Variable("Fuente del grado", kind="text"),
    "equipment": Variable("Equipo", kind="text"),
}
VARIABLES: dict[str, dict[str, Variable]] = {
    "strength": {},
    "cardio": COMMON,
    "running": {
        **COMMON,
        **{k: OUTDOOR[k] for k in ("ascent_m", "descent_m", "pause_seconds")},
        "cadence_spm": Variable("Cadencia medida", "pasos/min", 300),
    },
    "cycling": {
        **COMMON,
        "ascent_m": OUTDOOR["ascent_m"],
        "descent_m": OUTDOOR["descent_m"],
        "power_w": Variable("Potencia media medida", "W", 3000),
        "cadence_rpm": Variable("Cadencia medida", "rpm", 250),
        "environment": Variable("Entorno", kind="choice", choices=("indoor", "outdoor")),
    },
    "swimming": {
        **{k: v for k, v in COMMON.items() if k != "surface"},
        "stroke": Variable("Estilo", kind="text"),
        "pool_length_m": Variable("Longitud de piscina", "m", 100),
        "laps": Variable("Largos", "", 10000, "integer"),
        "strokes": Variable("Brazadas medidas", "", 100000, "integer"),
        "drill": Variable("Técnica / ejercicio", kind="text"),
    },
    "hiking": {**COMMON, **OUTDOOR},
}


class InvalidSportMetrics(ValueError):
    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


def validate_metric(sport: str, metric: Metric) -> Metric:
    key, value = metric.name, metric.value
    spec = VARIABLES[sport][key]
    if spec.kind in ("text", "choice"):
        if (
            not isinstance(value, str)
            or len(value) > 500
            or (spec.choices and value not in spec.choices)
        ):
            raise InvalidSportMetrics("Texto o selección inválida.", key)
        return Metric(key, value.strip())
    else:
        if (
            not isinstance(value, Decimal)
            or not value.is_finite()
            or value < (-500 if spec.kind == "altitude" else 0)
            or value > spec.maximum
            or (spec.kind == "integer" and value != value.to_integral_value())
        ):
            raise InvalidSportMetrics("Valor fuera de rango.", key)
        return Metric(key, value)


def validate_sport_metrics(sport: str, data: tuple[Metric, ...]) -> tuple[Metric, ...]:
    if sport not in VARIABLES:
        raise InvalidSportMetrics("Disciplina o variables inválidas.")
    unknown = {metric.name.value for metric in data} - set(VARIABLES[sport])
    if unknown:
        raise InvalidSportMetrics("Variables no admitidas: " + ", ".join(sorted(unknown)))
    result: dict[MetricName, Decimal | str] = {}
    for metric in data:
        normalized = validate_metric(sport, metric)
        result[normalized.name] = normalized.value

    def n(key: MetricName) -> Decimal | None:
        value = result.get(key)
        return value if isinstance(value, Decimal) else None

    duration, moving, pause = (
        n(MetricName.DURATION_SECONDS),
        n(MetricName.MOVING_SECONDS),
        n(MetricName.PAUSE_SECONDS),
    )
    if (
        duration is not None
        and (moving is not None or pause is not None)
        and (moving or 0) + (pause or 0) > duration
    ):
        raise InvalidSportMetrics("Movimiento y pausas no pueden superar el tiempo transcurrido.")
    altitude = n(MetricName.MAX_ALTITUDE_M)
    if altitude is not None:
        for name in (MetricName.START_ALTITUDE_M, MetricName.END_ALTITUDE_M):
            endpoint = n(name)
            if endpoint is not None and endpoint > altitude:
                raise InvalidSportMetrics("La altitud máxima debe incluir inicio y final.")
    hr, maximum = n(MetricName.HEART_RATE_BPM), n(MetricName.MAX_HEART_RATE_BPM)
    if hr is not None and maximum is not None and hr > maximum:
        raise InvalidSportMetrics("La frecuencia media supera la máxima.")
    difficulty = [
        bool(result.get(key))
        for key in (
            MetricName.DIFFICULTY_SCALE,
            MetricName.DIFFICULTY_GRADE,
            MetricName.DIFFICULTY_SOURCE,
        )
    ]
    if any(difficulty) and not all(difficulty):
        raise InvalidSportMetrics("Indica escala, grado y fuente de dificultad juntos.")
    return tuple(Metric(key, value) for key, value in result.items())


def pace_seconds(
    distance_m: Decimal | None, duration_seconds: Decimal | None, per_metres: int = 1000
) -> Decimal | None:
    return (
        round(duration_seconds / distance_m * per_metres, 2)
        if distance_m and duration_seconds is not None
        else None
    )


def internal_load(duration_seconds: int | None, reported_rpe: Decimal | None) -> Decimal | None:
    duration = None if duration_seconds is None else Decimal(str(duration_seconds))
    return decimal_internal_load(duration, reported_rpe)


def decimal_internal_load(
    duration_seconds: Decimal | None, reported_rpe: Decimal | None
) -> Decimal | None:
    if duration_seconds is None or reported_rpe is None:
        return None
    return (duration_seconds / 60 * reported_rpe).quantize(Decimal("0.01"))
