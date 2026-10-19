"""Shared progress repository contract for memory and Django implementations."""

from typing import Callable

from basis.modules.training.public import CreateTrip, Progress, ReadTrip, TripData
from basis.shared.identifiers import AccountId


class ProgressContract:
    service: Progress
    owner: AccountId
    count_trips: Callable[[], int]

    def test_contract_committed_trip_is_readable_without_inventing_measurements(self) -> None:
        before = self.count_trips()
        trip = self.service.create_trip(CreateTrip(self.owner, TripData("Contract trip", "Notes")))
        assert self.count_trips() == before + 1
        summary = self.service.trip(ReadTrip(self.owner, trip))
        assert summary.stages == 0 and summary.completed == 0
        assert all(metric.value is None for metric in summary.totals)
