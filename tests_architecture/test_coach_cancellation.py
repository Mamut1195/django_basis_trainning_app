"""Cancellation against the transactional in-memory adapter."""

from unittest import TestCase

from basis.modules.coach.application.jobs import CoachConfiguration, Jobs
from basis.modules.coach.domain.jobs import Job, JobNotFound
from basis.shared.identifiers import JobId
from tests_architecture.coach_cancellation_contract import CancellationContract
from tests_architecture.test_coach_jobs import OTHER, OWNER, Locks, Memory, Ports, Profiles


class CancellationMemory(Memory):
    def __enter__(self) -> "CancellationMemory":
        super().__enter__()
        return self

    def job(self, job: JobId) -> Job:
        try:
            return super().job(job)
        except KeyError:
            raise JobNotFound from None


class FakeCancellationTests(CancellationContract, TestCase):
    def setUp(self) -> None:
        memory, ports = CancellationMemory(), Ports()
        self.owner, self.other = OWNER, OTHER
        self.service = Jobs(
            memory,
            Locks(),
            ports,
            Profiles(),
            ports,
            ports,
            ports,
            ports,
            lambda: memory,
            CoachConfiguration(True, True, "deepseek-v4-flash"),
        )
