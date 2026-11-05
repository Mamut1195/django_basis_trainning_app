"""Deterministic implementations of the coach tool catalog.

Every result is computed from recorded sessions. The toolbox never reads the database:
the caller supplies owner-scoped samples and adherence, which keeps the model's view
identical to the numbers shown in the app.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from basis.modules.training.public import (
    Adherence,
    LoadSample,
    estimated_1rm_rir,
    load_ratio,
    rolling_mean,
    weekly_loads,
)

from ..domain.tools import (
    ToolError,
    ToolResult,
    parse_call,
    result_error,
)


class Toolbox:
    def __init__(
        self,
        *,
        samples: Sequence[LoadSample],
        adherence: Adherence,
        recent_rpe: Sequence[Decimal | None],
    ) -> None:
        self._samples = tuple(samples)
        self._adherence = adherence
        self._recent_rpe = tuple(recent_rpe)

    def call(self, name: str, args: Mapping[str, object]) -> ToolResult:
        parsed = parse_call(name, args)
        if name == "get_load_trend":
            return self._load_trend(parsed)
        if name == "get_load_summary":
            return self._load_summary(parsed)
        if name == "get_adherence":
            return self._adherence_result()
        if name == "get_missing_rpe":
            return self._missing_rpe()
        return self._estimate_1rm(parsed)

    def _filtered(self, sport: str, protocol: str) -> list[LoadSample]:
        return [
            sample
            for sample in self._samples
            if sample.sport == sport and sample.protocol == protocol
        ]

    def _load_trend(self, args: Mapping[str, object]) -> ToolResult:
        sport = args["sport"]
        protocol = args["protocol"]
        weeks = args["weeks"]
        assert isinstance(sport, str) and isinstance(protocol, str) and isinstance(weeks, int)
        if not 1 <= weeks <= 12:
            raise ToolError("Semanas fuera de rango: usa de 1 a 12.")
        rows = weekly_loads(tuple(self._filtered(sport, protocol)))[-weeks:]
        data = {
            "sport": sport,
            "protocol": protocol,
            "weeks": [
                {
                    "week_start": row.week_start.isoformat(),
                    "load": f"{row.load:.2f}",
                    "sessions": row.sessions,
                    "known": row.known,
                    "missing": row.missing,
                }
                for row in rows
            ],
        }
        notes: tuple[str, ...] = () if rows else ("Sin sesiones de ese deporte y protocolo.",)
        return ToolResult(
            tool="get_load_trend",
            ok=bool(rows),
            data=data,
            units={"load": "UA", "load_formula": "min × RPE"},
            coverage={
                "weeks": len(rows),
                "known": sum(row.known for row in rows),
                "missing": sum(row.missing for row in rows),
            },
            notes=notes,
        )

    def _load_summary(self, args: Mapping[str, object]) -> ToolResult:
        sport = args["sport"]
        protocol = args["protocol"]
        assert isinstance(sport, str) and isinstance(protocol, str)
        rows = weekly_loads(tuple(self._filtered(sport, protocol)))
        if not rows:
            return result_error("get_load_summary", "Sin sesiones de ese deporte y protocolo.")
        current = rows[-1]
        previous = [row.load for row in rows[:-1][-4:]]
        baseline = rolling_mean(previous, 4, minimum=3)
        ratio = load_ratio(current.load, baseline)
        data: dict[str, object] = {
            "sport": sport,
            "protocol": protocol,
            "current_week": current.week_start.isoformat(),
            "current_load": f"{current.load:.2f}",
            "baseline_load": f"{baseline:.2f}" if baseline is not None else None,
            "ratio": f"{ratio:.3f}" if ratio is not None else None,
        }
        notes: tuple[str, ...] = (
            ()
            if ratio is not None
            else ("Faltan semanas con dato para una base de 3 de 4 semanas.",)
        )
        return ToolResult(
            tool="get_load_summary",
            ok=True,
            data=data,
            units={"load": "UA", "ratio": "veces la base"},
            coverage={
                "weeks": len(rows),
                "known": current.known,
                "missing": current.missing,
            },
            notes=notes,
        )

    def _adherence_result(self) -> ToolResult:
        percent = self._adherence.percent
        return ToolResult(
            tool="get_adherence",
            ok=True,
            data={
                "eligible": self._adherence.eligible,
                "completed": self._adherence.completed,
                "percent": f"{percent:.2f}" if percent is not None else None,
            },
            units={"percent": "%"},
            coverage={"eligible": self._adherence.eligible},
            notes=() if percent is not None else ("Sin sesiones programadas elegibles.",),
        )

    def _missing_rpe(self) -> ToolResult:
        missing = sum(1 for value in self._recent_rpe if value is None)
        return ToolResult(
            tool="get_missing_rpe",
            ok=True,
            data={"missing_sessions": missing, "sessions": len(self._recent_rpe)},
            coverage={"sessions": len(self._recent_rpe)},
            notes=("Preguntar el RPE; no se asume cero.",) if missing else (),
        )

    def _estimate_1rm(self, args: Mapping[str, object]) -> ToolResult:
        weight = args["weight_kg"]
        reps = args["reps"]
        rir = args["rir"]
        assert isinstance(weight, (int, float)) and not isinstance(weight, bool)
        assert isinstance(reps, int) and isinstance(rir, int)
        estimate = estimated_1rm_rir(Decimal(str(weight)), reps, rir)
        if estimate is None:
            return result_error(
                "estimate_1rm", "Peso, repeticiones o RIR fuera del rango admitido."
            )
        return ToolResult(
            tool="estimate_1rm",
            ok=True,
            data={"one_rep_max_kg": f"{estimate:.2f}"},
            units={"one_rep_max_kg": "kg"},
            notes=("Es una estimación con RIR, no un máximo medido.",),
        )
