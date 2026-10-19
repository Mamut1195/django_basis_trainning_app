"""Pure progress/adherence/trekking rules require neither Django nor a database."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.training.application.progress import AddStage, CreateTrip, Progress, ReadProgress
from basis.modules.training.domain.execution import DurationProtocol, Metric, MetricName
from basis.modules.training.domain.progress import (
    ProgressBlock,
    ProgressSession,
    ScheduledProgress,
    report,
    summarize_trip,
)
from basis.modules.training.domain.trekking import (
    InvalidTrekking,
    StageData,
    StageNeighbour,
    TripData,
    validate_stage,
)
from basis.shared.identifiers import AccountId, SessionId, TrekStageId, TrekTripId
from tests_architecture.progress_contract import ProgressContract

TODAY = date(2026, 10, 19)
OWNER = AccountId(4)
SESSION = SessionId(UUID(int=1))


class Clock:
    def today(self) -> date:
        return TODAY

    def now(self) -> datetime:
        return datetime(2026, 10, 19, tzinfo=timezone.utc)


class Memory:
    def __init__(self) -> None:
        self.committed = False
        self.rows: list[TripData] = []
        self.fail = False

    def __enter__(self) -> "Memory":
        self.committed = False
        self.before = self.rows.copy()
        return self

    def __exit__(self, *exc: object) -> None:
        if not self.committed or exc[0] is not None:
            self.rows = self.before

    def commit(self) -> None:
        self.committed = True

    def require(self, owner: AccountId) -> None:
        if owner != OWNER:
            raise PermissionError

    def sessions(self, owner: AccountId) -> tuple[ProgressSession, ...]:
        return ()

    def scheduled(self, owner: AccountId, today: date) -> tuple[ScheduledProgress, ...]:
        return ()

    def stages(self, owner: AccountId, trip: TrekTripId) -> tuple[ProgressSession, ...]:
        return ()

    def create_trip(self, command: CreateTrip) -> TrekTripId:
        self.rows.append(command.data)
        if self.fail:
            raise ValueError("persistence failure")
        return TrekTripId(len(self.rows))

    def add_stage(self, command: AddStage) -> TrekStageId:
        return TrekStageId(1)


class ProgressTests(ProgressContract, TestCase):
    def setUp(self) -> None:
        self.store = Memory()
        self.owner = OWNER
        self.service = Progress(self.store, self.store, lambda: self.store, Clock())
        self.count_trips = lambda: len(self.store.rows)

    def test_unknown_zero_protocols_and_authoritative_block_totals(self) -> None:
        hiking = ProgressBlock("hiking", (Metric(MetricName.DISTANCE_M, Decimal(0)),))
        strength = ProgressBlock("strength", set_volumes=(None, Decimal(0), Decimal(25)))
        rows = (
            ProgressSession(
                SESSION, True, DurationProtocol.ELAPSED, 60, Decimal(0), (hiking, hiking, strength)
            ),
            ProgressSession(
                SessionId(UUID(int=2)),
                True,
                DurationProtocol.MOVING,
                None,
                None,
                (ProgressBlock("running"),),
            ),
            ProgressSession(
                SessionId(UUID(int=3)), False, DurationProtocol.ELAPSED, 60, Decimal(5)
            ),
        )
        result = report(rows, (), TODAY)
        self.assertEqual(result.sessions, 2)
        self.assertEqual([s.sport for s in result.sports], ["hiking", "strength", "running"])
        self.assertEqual(result.sports[0].sessions, 1)
        self.assertEqual(result.sports[0].distance_m, Decimal(0))
        self.assertIsNone(result.sports[0].ascent_m)
        self.assertEqual(result.sports[1].external_volume_kg, Decimal(25))
        self.assertEqual((result.loads[0].value, result.loads[0].known), (Decimal(0), 1))
        self.assertEqual((result.loads[1].known, result.loads[1].missing), (0, 1))

    def test_adherence_preserves_strict_historical_replacement_cutoff(self) -> None:
        earlier = date(2026, 10, 18)
        scheduled = (
            ScheduledProgress(earlier, False, TODAY),
            ScheduledProgress(TODAY, False, TODAY),
            ScheduledProgress(TODAY, True, TODAY),
            ScheduledProgress(date(2026, 10, 20), True, None),
        )
        result = report((), scheduled, TODAY)
        self.assertEqual(
            (result.scheduled_past, result.completed_scheduled, result.adherence_percent),
            (2, 1, 50.0),
        )
        self.assertIsNone(report((), (), TODAY).adherence_percent)

    def test_trekking_totals_include_only_completed_hiking_and_keep_unknowns(self) -> None:
        hiking = ProgressBlock(
            "hiking",
            (Metric(MetricName.DISTANCE_M, Decimal(12)), Metric(MetricName.ASCENT_M, Decimal(0))),
        )
        running = ProgressBlock("running", (Metric(MetricName.DISTANCE_M, Decimal(999)),))
        result = summarize_trip(
            (
                ProgressSession(SESSION, True, DurationProtocol.ELAPSED, blocks=(hiking, running)),
                ProgressSession(SESSION, False, DurationProtocol.ELAPSED, blocks=(hiking,)),
            )
        )
        self.assertEqual((result.stages, result.completed), (2, 1))
        self.assertEqual(
            [v.value for v in result.totals], [Decimal(12), Decimal(0), None, None, None]
        )

    def test_stage_ownership_hiking_and_date_order(self) -> None:
        validate_stage(OWNER, OWNER, True, 2, TODAY, (StageNeighbour(1, TODAY),))
        for owner, hiking, neighbours in (
            (AccountId(9), True, ()),
            (OWNER, False, ()),
            (OWNER, True, (StageNeighbour(3, date(2026, 10, 18)),)),
        ):
            with self.assertRaises(InvalidTrekking):
                validate_stage(OWNER, owner, hiking, 2, TODAY, neighbours)

    def test_write_commit_error_rollback_authorization_and_controlled_clock(self) -> None:
        store = Memory()
        service = Progress(store, store, lambda: store, Clock())
        self.assertEqual(service.create_trip(CreateTrip(OWNER, TripData("Trip"))), 1)
        self.assertTrue(store.committed)
        store.fail = True
        with self.assertRaises(ValueError):
            service.create_trip(CreateTrip(OWNER, TripData("Failed")))
        self.assertEqual(len(store.rows), 1)
        with self.assertRaises(PermissionError):
            service.create_trip(CreateTrip(AccountId(9), TripData("Foreign")))
        self.assertEqual(service.read(ReadProgress(OWNER)).scheduled_past, 0)
        self.assertEqual(
            service.add_stage(AddStage(OWNER, TrekTripId(1), StageData(SESSION, 1))), 1
        )
