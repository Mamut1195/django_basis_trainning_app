"""Tool surface for the coach: names, arguments, validation and result envelopes.

The model never queries the database and never does arithmetic. It requests a tool with
typed arguments and receives numbers computed by the deterministic layer, with units and
coverage. Unknown tools or arguments are rejected before any data is read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

ArgType = Literal["string", "integer", "number"]


class ToolError(Exception):
    """Invalid tool name, argument or value."""


@dataclass(frozen=True)
class ToolArg:
    name: str
    type: ArgType
    description: str
    required: bool = True
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: tuple[ToolArg, ...] = ()

    def schema(self) -> dict[str, object]:
        properties: dict[str, object] = {}
        required: list[str] = []
        for arg in self.args:
            shape: dict[str, object] = {"type": arg.type, "description": arg.description}
            if arg.choices:
                shape["enum"] = list(arg.choices)
            properties[arg.name] = shape
            if arg.required:
                required.append(arg.name)
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "get_load_trend",
        "Carga interna por semana ISO de un deporte y protocolo. Unidades: UA (min × RPE).",
        (
            ToolArg("sport", "string", "Deporte registrado, por ejemplo running o hiking."),
            ToolArg("protocol", "string", "Protocolo de duración: elapsed o moving."),
            ToolArg("weeks", "integer", "Semanas hacia atrás; entre 1 y 12."),
        ),
    ),
    ToolSpec(
        "get_load_summary",
        "Última semana frente a la base de hasta 4 semanas anteriores del mismo deporte y protocolo.",
        (
            ToolArg("sport", "string", "Deporte registrado."),
            ToolArg("protocol", "string", "Protocolo de duración: elapsed o moving."),
        ),
    ),
    ToolSpec(
        "get_adherence",
        "Sesiones programadas elegibles, completadas y porcentaje del período.",
    ),
    ToolSpec(
        "get_missing_rpe",
        "Sesiones recientes sin RPE. Un dato ausente no se cuenta como cero.",
    ),
    ToolSpec(
        "estimate_1rm",
        "1RM estimado con Epley ajustado por repeticiones en reserva (RIR).",
        (
            ToolArg("weight_kg", "number", "Peso levantado en kg."),
            ToolArg("reps", "integer", "Repeticiones realizadas; entre 1 y 12."),
            ToolArg("rir", "integer", "Repeticiones en reserva; entre 0 y 10."),
        ),
    ),
)

BY_NAME: Mapping[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}


def parse_call(name: str, args: Mapping[str, object]) -> dict[str, object]:
    """Validate the name, the allowed keys and the value types."""
    spec = BY_NAME.get(name)
    if spec is None:
        raise ToolError(f"Herramienta desconocida: {name}")
    allowed = {arg.name: arg for arg in spec.args}
    unknown = set(args) - set(allowed)
    if unknown:
        raise ToolError("Argumentos no admitidos: " + ", ".join(sorted(unknown)))
    parsed: dict[str, object] = {}
    for arg in spec.args:
        if arg.name not in args:
            if arg.required:
                raise ToolError(f"Falta el argumento: {arg.name}")
            continue
        value = args[arg.name]
        if value is None:
            if arg.required:
                raise ToolError(f"El argumento {arg.name} no puede ser nulo.")
            continue
        if arg.type == "string":
            if not isinstance(value, str) or not value.strip() or len(value) > 80:
                raise ToolError(f"El argumento {arg.name} debe ser texto no vacío.")
            if arg.choices and value not in arg.choices:
                raise ToolError(f"Valor no admitido para {arg.name}: {value}")
            parsed[arg.name] = value.strip()
        elif arg.type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ToolError(f"El argumento {arg.name} debe ser entero.")
            parsed[arg.name] = value
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ToolError(f"El argumento {arg.name} debe ser numérico.")
            parsed[arg.name] = value
    return parsed


@dataclass(frozen=True)
class ToolResult:
    """JSON-ready result. Decimals travel as strings to avoid float drift."""

    tool: str
    ok: bool
    data: Mapping[str, object] = field(default_factory=dict)
    units: Mapping[str, str] = field(default_factory=dict)
    coverage: Mapping[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "data": dict(self.data),
            "units": dict(self.units),
            "coverage": dict(self.coverage),
            "notes": list(self.notes),
        }


def tool_catalog() -> tuple[dict[str, object], ...]:
    """Schemas for the provider request, in a stable order."""
    return tuple(spec.schema() for spec in TOOL_SPECS)


def result_error(tool: str, message: str) -> ToolResult:
    return ToolResult(tool=tool, ok=False, data={}, notes=(message,))
