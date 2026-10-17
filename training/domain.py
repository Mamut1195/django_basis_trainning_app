"""Versioned, unit-explicit manual sport variables. None always means unknown."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

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
    choices: tuple = ()


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
VARIABLES = {
    "strength": {},
    "cardio": COMMON,
    "running": {
        **COMMON,
        **{k: OUTDOOR[k] for k in ("ascent_m", "descent_m")},
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


def validate_metrics(sport, data):
    if sport not in VARIABLES or not isinstance(data, dict):
        raise ValidationError("Disciplina o variables inválidas.")
    unknown = set(data) - set(VARIABLES[sport])
    if unknown:
        raise ValidationError("Variables no admitidas: " + ", ".join(sorted(unknown)))
    result = {}
    for key, value in data.items():
        if value is None or value == "":
            continue
        spec = VARIABLES[sport][key]
        if spec.kind in ("text", "choice"):
            if (
                not isinstance(value, str)
                or len(value) > 500
                or (spec.choices and value not in spec.choices)
            ):
                raise ValidationError({key: "Texto o selección inválida."})
            result[key] = value.strip()
            continue
        try:
            if isinstance(value, bool):
                raise InvalidOperation
            number = Decimal(str(value))
            if (
                not number.is_finite()
                or number < (-500 if spec.kind == "altitude" else 0)
                or number > spec.maximum
                or (spec.kind == "integer" and number != int(number))
            ):
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError({key: "Valor fuera de rango."}) from None
        result[key] = str(number)

    def n(key):
        return Decimal(result[key]) if key in result else None

    if n("duration_seconds") is not None and n("moving_seconds") is not None:
        if n("moving_seconds") + (n("pause_seconds") or 0) > n("duration_seconds"):
            raise ValidationError("Movimiento y pausas no pueden superar el tiempo transcurrido.")
    if n("max_altitude_m") is not None:
        if any(
            n(k) is not None and n(k) > n("max_altitude_m")
            for k in ("start_altitude_m", "end_altitude_m")
        ):
            raise ValidationError("La altitud máxima debe incluir inicio y final.")
    if (
        n("max_heart_rate_bpm") is not None
        and n("heart_rate_bpm") is not None
        and n("heart_rate_bpm") > n("max_heart_rate_bpm")
    ):
        raise ValidationError("La frecuencia media supera la máxima.")
    difficulty = [
        bool(result.get(k)) for k in ("difficulty_scale", "difficulty_grade", "difficulty_source")
    ]
    if any(difficulty) and not all(difficulty):
        raise ValidationError("Indica escala, grado y fuente de dificultad juntos.")
    return result


def pace_seconds(data, per_metres=1000):
    distance = Decimal(data["distance_m"]) if data.get("distance_m") is not None else None
    duration = (
        Decimal(data["duration_seconds"]) if data.get("duration_seconds") is not None else None
    )
    return round(duration / distance * per_metres, 2) if distance and duration is not None else None


def internal_load(duration_seconds, reported_rpe):
    if duration_seconds is None or reported_rpe is None:
        return None
    return (Decimal(str(duration_seconds)) / 60 * Decimal(str(reported_rpe))).quantize(
        Decimal("0.01")
    )
