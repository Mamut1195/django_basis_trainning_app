"""H1: inclusive sibling dates in plan creation, editing and private templates."""

from dataclasses import replace
from datetime import timedelta
from unittest import TestCase
from uuid import UUID

from basis.modules.training.application.planning import AddCycle, CycleCreationContext, Planning
from basis.modules.training.domain.plan_editor import edit_definition, template_definition
from basis.modules.training.domain.planning import (
    CycleDefinition,
    CycleKind,
    InvalidPlanning,
    PlanDefinition,
    PlanHeader,
    PlanSnapshot,
    validate_cycle,
    validate_definition,
)
from basis.shared.identifiers import AccountId, GoalId, LineageId, PlanId
from tests_architecture.test_planning import (
    TODAY,
    Authorization,
    Clock,
    MemoryWork,
    PermissiveWrites,
)

OVERLAP = "Los ciclos con el mismo padre no pueden solaparse en fechas."


def sibling_plan(kind: CycleKind) -> tuple[PlanDefinition, CycleDefinition]:
    """Ancestors cover 30 days; the existing sibling covers days 0 through 9."""
    end = TODAY + timedelta(days=29)
    ancestors: list[CycleDefinition] = []
    parent = None
    for ancestor in CycleKind:
        if ancestor == kind:
            break
        key = ancestor.value
        ancestors.append(CycleDefinition(key, parent, ancestor, key, TODAY, end))
        parent = key
    first = CycleDefinition("first", parent, kind, "Primero", TODAY, TODAY + timedelta(days=9))
    following = replace(
        first, key="next", title="Siguiente", start_date=TODAY + timedelta(days=10), end_date=end
    )
    return (
        PlanDefinition(GoalId(1), "H1", TODAY, end, cycles=(*ancestors, first)),
        following,
    )


def snapshot(data: PlanDefinition) -> PlanSnapshot:
    return PlanSnapshot(
        PlanHeader(PlanId(1), AccountId(1), LineageId(UUID(int=1)), 1, None),
        data,
        frozenset(),
        False,
    )


class SiblingPlanningTests(TestCase):
    def test_add_cycle_rejects_overlap_before_a_permissive_writer(self) -> None:
        repository = PermissiveWrites()
        service = Planning(repository, Authorization(), lambda: MemoryWork(repository), Clock())
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            parent = data.cycles[-2] if len(data.cycles) > 1 else None
            repository.cycle_read = CycleCreationContext(
                data.start_date, data.end_date, parent, True, siblings=data.cycles
            )
            command = AddCycle(AccountId(1), PlanId(1), following)
            with self.subTest(kind=kind):
                before = list(repository.writes)
                with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                    service.add_cycle(
                        replace(
                            command, data=replace(following, start_date=TODAY + timedelta(days=9))
                        )
                    )
                self.assertEqual(repository.writes, before)
                service.add_cycle(command)
                self.assertEqual(repository.writes, [*before, "cycle"])

    def test_create_adjacent_siblings_at_every_level_in_either_order(self) -> None:
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            for reverse in (False, True):
                with self.subTest(kind=kind, reverse=reverse):
                    cycles = (*data.cycles, following)
                    validate_definition(replace(data, cycles=cycles[::-1] if reverse else cycles))

    def test_create_rejects_all_inclusive_overlap_shapes_at_every_level(self) -> None:
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            for start, end in ((9, 29), (5, 15), (0, 9), (1, 8), (0, 29), (9, 9)):
                for reverse in (False, True):
                    with self.subTest(kind=kind, start=start, end=end, reverse=reverse):
                        candidate = replace(
                            following,
                            start_date=TODAY + timedelta(days=start),
                            end_date=TODAY + timedelta(days=end),
                        )
                        cycles = (*data.cycles, candidate)
                        with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                            validate_definition(
                                replace(data, cycles=cycles[::-1] if reverse else cycles)
                            )

    def test_edit_ignores_itself_and_rejects_a_shared_endpoint(self) -> None:
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            data = replace(data, cycles=(*data.cycles, following))
            for start, accepted in ((10, True), (9, False)):
                with self.subTest(kind=kind, start=start):
                    candidate = replace(following, start_date=TODAY + timedelta(days=start))
                    if accepted:
                        result = edit_definition(
                            snapshot(data),
                            TODAY,
                            data.title,
                            data.start_date,
                            data.end_date,
                            "",
                            candidate,
                        )
                        self.assertEqual(result.cycles[-1], candidate)
                    else:
                        with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                            edit_definition(
                                snapshot(data),
                                TODAY,
                                data.title,
                                data.start_date,
                                data.end_date,
                                "",
                                candidate,
                            )

    def test_move_checks_destination_siblings_and_allows_different_parents(self) -> None:
        data, following = sibling_plan(CycleKind.MESO)
        source = CycleDefinition(
            "source", "first", CycleKind.MICRO, "Origen", TODAY, TODAY + timedelta(days=4)
        )
        target = replace(
            source,
            key="target",
            parent=following.key,
            start_date=TODAY + timedelta(days=10),
            end_date=TODAY + timedelta(days=14),
        )
        data = replace(data, cycles=(*data.cycles, following, source, target))
        validate_definition(data)
        for start, accepted in ((15, True), (14, False)):
            with self.subTest(start=start):
                moved = replace(
                    source,
                    parent=following.key,
                    start_date=TODAY + timedelta(days=start),
                    end_date=TODAY + timedelta(days=19),
                )
                if accepted:
                    result = edit_definition(
                        snapshot(data), TODAY, data.title, data.start_date, data.end_date, "", moved
                    )
                    self.assertIn(moved, result.cycles)
                else:
                    with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                        edit_definition(
                            snapshot(data),
                            TODAY,
                            data.title,
                            data.start_date,
                            data.end_date,
                            "",
                            moved,
                        )

    def test_template_preserves_adjacency_and_rejects_legacy_overlap(self) -> None:
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            for offset, accepted in ((10, True), (9, False)):
                with self.subTest(kind=kind, offset=offset):
                    candidate = replace(following, start_date=TODAY + timedelta(days=offset))
                    legacy = replace(data, cycles=(*data.cycles, candidate))
                    start = TODAY + timedelta(days=60)
                    if accepted:
                        copied = template_definition(snapshot(legacy), GoalId(2), "Copia", start)
                        self.assertEqual(copied.cycles[-1].start_date, start + timedelta(days=10))
                        validate_definition(copied)
                    else:
                        with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                            template_definition(snapshot(legacy), GoalId(2), "Copia", start)

    def test_cycle_validation_ignores_itself_and_other_parents(self) -> None:
        data, _ = sibling_plan(CycleKind.MICRO)
        cycle = data.cycles[-1]
        validate_cycle(
            cycle,
            data.start_date,
            data.end_date,
            data.cycles[-2],
            siblings=(cycle, replace(cycle, key="other", parent="another-parent")),
        )

    def test_overlap_diagnostic_names_both_cycles_types_dates_and_remedy(self) -> None:
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            following = replace(following, start_date=TODAY + timedelta(days=9))
            for cycles in ((*data.cycles, following), (following, *data.cycles)):
                with self.subTest(kind=kind, first=cycles[0].key):
                    with self.assertRaises(InvalidPlanning) as raised:
                        validate_definition(replace(data, cycles=cycles))
                    error = raised.exception
                    self.assertEqual(error.messages[0], OVERLAP)
                    for cycle in (data.cycles[-1], following):
                        self.assertIn(
                            f'"{cycle.title}" ({kind.value}, '
                            f"{cycle.start_date} a {cycle.end_date})",
                            str(error),
                        )
                    self.assertIn(
                        "Ajusta las fechas para que uno termine antes de que empiece el otro",
                        str(error),
                    )
                    self.assertIn("inicio y final están incluidas", str(error))

    def test_legacy_edit_and_shifted_template_keep_diagnostic_dates(self) -> None:
        for kind in CycleKind:
            data, following = sibling_plan(kind)
            following = replace(following, start_date=TODAY + timedelta(days=9))
            legacy = snapshot(replace(data, cycles=(*data.cycles, following)))
            with self.subTest(kind=kind, operation="edit"):
                with self.assertRaises(InvalidPlanning) as raised:
                    edit_definition(legacy, TODAY, data.title, data.start_date, data.end_date, "")
                self.assertIn(f'"Primero" ({kind.value}, {TODAY}', str(raised.exception))
                self.assertIn(
                    f'"Siguiente" ({kind.value}, {following.start_date}', str(raised.exception)
                )
            start = TODAY + timedelta(days=60)
            with self.subTest(kind=kind, operation="template"):
                with self.assertRaises(InvalidPlanning) as raised:
                    template_definition(legacy, GoalId(2), "Copia", start)
                self.assertIn(f'"Primero" ({kind.value}, {start}', str(raised.exception))
                self.assertIn(
                    f'"Siguiente" ({kind.value}, {start + timedelta(days=9)}',
                    str(raised.exception),
                )
