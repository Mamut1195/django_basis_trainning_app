"""Catalog business limits are enforced before a permissive persistence writer."""

from dataclasses import replace
from unittest import TestCase

from basis.modules.catalog.application.catalog import Catalog, SaveExercise
from basis.modules.catalog.domain.catalog import (
    ClassificationData,
    ExerciseData,
    InvalidCatalogData,
)
from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId
from tests_architecture.test_billing import Memory

DATA = ExerciseData(ClassificationId(1), "squat", None, "", "Bajo", "", (), "", "", False)


class PermissiveCatalog:
    writes = 0

    def classification(self, id: ClassificationId) -> ClassificationData:
        return ClassificationData("Strength")

    def exercise(self, id: ExerciseId) -> ExerciseData:
        return DATA

    def save_classification(
        self, data: ClassificationData, id: ClassificationId | None
    ) -> ClassificationId:
        return ClassificationId(1)

    def save_exercise(self, data: ExerciseData, id: ExerciseId | None) -> ExerciseId:
        self.writes += 1
        return ExerciseId(1)

    def delete_classification(self, id: ClassificationId) -> None:
        raise NotImplementedError

    def delete_exercise(self, id: ExerciseId) -> None:
        raise NotImplementedError


class Authorization:
    def require_write(self, actor: AccountId) -> None:
        pass


class CatalogPolicyTests(TestCase):
    def test_muscle_count_and_length_are_rejected_before_permissive_writer(self) -> None:
        repository, work = PermissiveCatalog(), Memory()
        service = Catalog(repository, Authorization(), lambda: work)
        for muscles in (("leg",) * 31, ("a" * 81,)):
            with self.subTest(muscles=muscles), self.assertRaises(InvalidCatalogData) as failure:
                service.save_exercise(
                    SaveExercise(AccountId(1), replace(DATA, musculos_principales=muscles))
                )
            self.assertEqual(failure.exception.field, "musculos_principales")
            self.assertEqual(str(failure.exception), "Usa una lista de nombres musculares.")
        self.assertEqual(repository.writes, 0)
        service.save_exercise(
            SaveExercise(AccountId(1), replace(DATA, musculos_principales=("a" * 80,) * 30))
        )
        self.assertEqual(repository.writes, 1)
        self.assertTrue(work.committed)
