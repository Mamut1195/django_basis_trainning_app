"""Coach tools: schema validation, honest coverage and JSON-ready results."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from basis.modules.coach.application.tools import Toolbox
from basis.modules.coach.domain.tools import (
    BY_NAME,
    TOOL_SPECS,
    ToolError,
    parse_call,
    tool_catalog,
)
from basis.modules.training.public import Adherence, LoadSample

WEEKS = (date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19), date(2026, 10, 26))


def sample(
    week: int, load: Decimal, *, sport: str = "running", protocol: str = "elapsed"
) -> LoadSample:
    rpe = Decimal(5)
    seconds = int(load * 60 / rpe)
    return LoadSample(WEEKS[week], sport, protocol, seconds, rpe)


def toolbox() -> Toolbox:
    samples = (
        sample(0, Decimal("500")),
        sample(1, Decimal("500")),
        sample(2, Decimal("500")),
        sample(3, Decimal("720")),
        sample(3, Decimal("360"), sport="cycling", protocol="elapsed"),
    )
    return Toolbox(
        samples=samples,
        adherence=Adherence(eligible=4, completed=3, percent=Decimal("75.00")),
        recent_rpe=(Decimal("6"), None, None),
    )


class CatalogTests(TestCase):
    def test_names_are_unique_and_documented(self) -> None:
        names = [spec.name for spec in TOOL_SPECS]
        self.assertEqual(len(names), len(set(names)))
        for spec in TOOL_SPECS:
            self.assertTrue(spec.description)
            schema = spec.schema()
            parameters = schema["parameters"]
            assert isinstance(parameters, dict)
            self.assertFalse(parameters["additionalProperties"])

    def test_catalog_is_json_ready_and_ordered(self) -> None:
        catalog = tool_catalog()
        self.assertEqual([row["name"] for row in catalog], [spec.name for spec in TOOL_SPECS])
        self.assertIn("parameters", catalog[0])

    def test_unknown_name_or_argument_is_rejected(self) -> None:
        with self.assertRaises(ToolError):
            parse_call("get_everything", {})
        with self.assertRaises(ToolError):
            parse_call(
                "get_load_trend",
                {"sport": "running", "protocol": "elapsed", "weeks": 4, "extra": 1},
            )

    def test_types_and_required_arguments(self) -> None:
        with self.assertRaises(ToolError):
            parse_call("get_load_trend", {"sport": "running"})
        with self.assertRaises(ToolError):
            parse_call("estimate_1rm", {"weight_kg": "100", "reps": 5, "rir": 2})
        with self.assertRaises(ToolError):
            parse_call("estimate_1rm", {"weight_kg": 100.5, "reps": True, "rir": 2})
        self.assertEqual(BY_NAME["estimate_1rm"].args[0].type, "number")


class LoadToolTests(TestCase):
    def test_trend_is_per_sport_and_protocol(self) -> None:
        result = toolbox().call(
            "get_load_trend",
            {"sport": "running", "protocol": "elapsed", "weeks": 2},
        )
        self.assertTrue(result.ok)
        rows = result.data["weeks"]
        assert isinstance(rows, list)
        self.assertEqual([row["load"] for row in rows], ["500.00", "720.00"])
        self.assertNotIn("1080", str(result.to_json()))

    def test_summary_compares_current_week_with_three_previous(self) -> None:
        result = toolbox().call("get_load_summary", {"sport": "running", "protocol": "elapsed"})
        self.assertEqual(result.data["current_load"], "720.00")
        self.assertEqual(result.data["baseline_load"], "500.00")
        self.assertEqual(result.data["ratio"], "1.440")

    def test_insufficient_weeks_are_reported_not_invented(self) -> None:
        partial = Toolbox(
            samples=(sample(2, Decimal("500")), sample(3, Decimal("720"))),
            adherence=Adherence(0, 0, None),
            recent_rpe=(),
        )
        result = partial.call("get_load_summary", {"sport": "running", "protocol": "elapsed"})
        self.assertTrue(result.ok)
        self.assertIsNone(result.data["baseline_load"])
        self.assertIsNone(result.data["ratio"])
        self.assertTrue(result.notes)

    def test_empty_sport_returns_an_error_result(self) -> None:
        result = toolbox().call(
            "get_load_trend", {"sport": "swimming", "protocol": "moving", "weeks": 4}
        )
        self.assertFalse(result.ok)
        self.assertTrue(result.notes)

    def test_weeks_out_of_range(self) -> None:
        with self.assertRaises(ToolError):
            toolbox().call(
                "get_load_trend", {"sport": "running", "protocol": "elapsed", "weeks": 99}
            )


class OtherToolTests(TestCase):
    def test_adherence(self) -> None:
        result = toolbox().call("get_adherence", {})
        self.assertEqual(result.data["percent"], "75.00")
        self.assertEqual(result.data["completed"], 3)

    def test_missing_rpe_is_counted(self) -> None:
        result = toolbox().call("get_missing_rpe", {})
        self.assertEqual(result.data["missing_sessions"], 2)
        self.assertTrue(result.notes)

    def test_estimate_1rm(self) -> None:
        result = toolbox().call("estimate_1rm", {"weight_kg": 100, "reps": 5, "rir": 2})
        self.assertTrue(result.ok)
        self.assertEqual(result.data["one_rep_max_kg"], "123.33")
        self.assertIn("estimación", result.notes[0])

    def test_estimate_1rm_out_of_range_is_an_error(self) -> None:
        result = toolbox().call("estimate_1rm", {"weight_kg": 100, "reps": 20, "rir": 2})
        self.assertFalse(result.ok)

    def test_results_serialize_with_units(self) -> None:
        payload = (
            toolbox()
            .call("get_load_summary", {"sport": "running", "protocol": "elapsed"})
            .to_json()
        )
        units = payload["units"]
        assert isinstance(units, dict)
        self.assertEqual(units["load"], "UA")
        self.assertIsInstance(payload["notes"], list)
