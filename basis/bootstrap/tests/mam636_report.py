"""Evidence accounting for MAM-636; independent of Django and model judgments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

Status = Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"]
Dimension = Literal["numeric", "structure", "sport", "operation"]
DIMENSIONS: tuple[Dimension, ...] = ("numeric", "structure", "sport", "operation")
STATUSES: tuple[Status, ...] = ("PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN")


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def aggregate(statuses: list[Status]) -> Status:
    for status in statuses:
        if type(status) is not str or status not in STATUSES:
            raise ValueError("Unknown evidence status")
    if "FAIL" in statuses:
        return "FAIL"
    if not statuses or all(s == "NOT_RUN" for s in statuses):
        return "NOT_RUN"
    if "INCONCLUSIVE" in statuses or "NOT_RUN" in statuses:
        return "INCONCLUSIVE"
    return "PASS"


def same_evidence(actual: object, expected: object) -> bool:
    """Exact structural equality; no cross-type numeric equivalence is authorized."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict) and isinstance(expected, dict):
        return len(actual) == len(expected) and all(
            any(
                same_evidence(key, other) and same_evidence(value, expected[other])
                for other in expected
            )
            for key, value in actual.items()
        )
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            same_evidence(a, e) for a, e in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


@dataclass(frozen=True)
class CorpusCase:
    id: str
    discipline: str
    scenario: str
    request: str
    expected: tuple[str, ...]


def load_corpus(path: Path) -> tuple[CorpusCase, ...]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "coach_evaluation_v1":
        raise ValueError("Unsupported corpus version")
    rows: object = value.get("cases")
    if not isinstance(rows, list):
        raise ValueError("Corpus cases must be a list")
    result: list[CorpusCase] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Corpus case must be an object")
        strings = [row.get(k) for k in ("id", "discipline", "scenario", "request")]
        expected = row.get("expected")
        if not all(isinstance(v, str) and v for v in strings) or not isinstance(expected, list):
            raise ValueError("Missing case inputs")
        if not expected or not all(isinstance(v, str) and v for v in expected):
            raise ValueError("Missing expectations")
        result.append(CorpusCase(*cast(tuple[str, str, str, str], tuple(strings)), tuple(expected)))
    if len({c.id for c in result}) != len(result):
        raise ValueError("Duplicate case IDs")
    return tuple(result)


@dataclass(frozen=True)
class Observation:
    expectation: int
    dimension: Dimension
    name: str
    status: Status
    actual: object
    expected: object
    reason: str


@dataclass
class CaseResult:
    case: CorpusCase
    fixture: dict[str, object] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    artifacts: dict[str, object] = field(default_factory=dict)
    duration_ns: int | None = None

    def check(
        self, expectation: int, dimension: Dimension, name: str, actual: object, expected: object
    ) -> None:
        self.observe(
            expectation,
            dimension,
            name,
            "PASS" if same_evidence(actual, expected) else "FAIL",
            actual,
            expected,
            "Observed through the executed service/ORM/HTTP path; SIMULATED transport only.",
        )

    def observe(
        self,
        expectation: int,
        dimension: Dimension,
        name: str,
        status: Status,
        actual: object = None,
        expected: object = None,
        reason: str = "",
    ) -> None:
        observation = Observation(expectation, dimension, name, status, actual, expected, reason)
        self.validate_observation(observation)
        self.observations.append(observation)

    def validate_observation(self, observation: Observation) -> None:
        if type(observation.expectation) is not int or not 1 <= observation.expectation <= len(
            self.case.expected
        ):
            raise ValueError("Unknown expectation")
        if type(observation.dimension) is not str or observation.dimension not in DIMENSIONS:
            raise ValueError("Unknown evidence dimension")
        aggregate([observation.status])
        if observation.status == "PASS" and (observation.actual is None or not observation.reason):
            raise ValueError("PASS requires located evidence and a reason")

    def validate(self) -> None:
        for observation in self.observations:
            self.validate_observation(observation)

    def export(self) -> dict[str, object]:
        self.validate()
        expectations: list[dict[str, object]] = []
        for i, text in enumerate(self.case.expected, 1):
            observations = [o for o in self.observations if o.expectation == i]
            expectations.append(
                {
                    "id": i,
                    "text": text,
                    "status": aggregate([o.status for o in observations]),
                    "evidence": [asdict(o) for o in observations],
                    "reason": ""
                    if observations
                    else "Typed sporting fixture not implemented/executed in this bounded system slice; original scenario retained.",
                }
            )
        dimensions: dict[str, object] = {}
        for dimension in DIMENSIONS:
            observations = [o for o in self.observations if o.dimension == dimension]
            dimensions[dimension] = {
                "status": aggregate([o.status for o in observations]),
                "evidence_names": [o.name for o in observations],
                "reason": ""
                if observations
                else {
                    "numeric": "No executed sporting numeric oracle; no model calculation used.",
                    "structure": "No proposal fixture executed for this case.",
                    "sport": "Controlled responses do not evaluate a model; human review PENDING.",
                    "operation": "Typed fixture not implemented/executed in this bounded system slice.",
                }[dimension],
            }
        statuses = [cast(Status, e["status"]) for e in expectations]
        return {
            "case_id": self.case.id,
            "discipline": self.case.discipline,
            "scenario": self.case.scenario,
            "request": self.case.request,
            "status": aggregate(statuses),
            "mode": "SIMULATED",
            "sport_review": "PENDING",
            "fixture": self.fixture,
            "expectations": expectations,
            "dimensions": dimensions,
            "artifacts": self.artifacts,
            "artifacts_sha256": digest(self.artifacts),
            "duration_ns": self.duration_ns,
        }


def require_technical_success(results: list[CaseResult]) -> None:
    for result in results:
        result.validate()
    failures = [
        f"{r.case.id}/{o.name}" for r in results for o in r.observations if o.status == "FAIL"
    ]
    if failures:
        raise AssertionError("Technical evaluation failed: " + ", ".join(failures))


def coverage(results: list[CaseResult]) -> dict[str, object]:
    exports = [r.export() for r in results]
    expectations = [o for r in results for o in r.case.expected]
    return {
        "case_denominator": len(results),
        "cases_executed": sum(r.duration_ns is not None for r in results),
        "cases_all_expectations_pass": sum(e["status"] == "PASS" for e in exports),
        "expectation_denominator": len(expectations),
        "expectations_pass": sum(
            aggregate([o.status for o in r.observations if o.expectation == i]) == "PASS"
            for r in results
            for i in range(1, len(r.case.expected) + 1)
        ),
        "observations": {
            s: sum(o.status == s for r in results for o in r.observations)
            for s in ("PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN")
        },
        "accepted_sporting_cases": 0,
    }
