"""Shared manual/bulk intention policy and conservative legacy ID reconciliation."""

from dataclasses import fields, replace

from .execution import (
    AdaptationField,
    AdaptationPresence,
    BlockData,
    IntervalData,
    InvalidExecution,
    StrengthData,
)

STRENGTH_INTENT = tuple(f.name for f in fields(StrengthData) if f.name.startswith("target_")) + (
    "exercise",
    "kind",
    "load_type",
    "tempo",
    "range_of_motion",
    "side",
    "group",
    "rest_seconds",
    "rm_reference",
)
ADAPTATION_FIELDS = (
    "actual_exercise",
    "actual_load_type",
    "actual_kind",
    "actual_tempo",
    "actual_range_of_motion",
    "actual_side",
    "actual_group",
)


def preserve_strength(current: StrengthData, candidate: StrengthData) -> None:
    if any(getattr(current, name) != getattr(candidate, name) for name in STRENGTH_INTENT):
        raise InvalidExecution(
            "La prescripción original no puede modificarse. Registra una adaptación real con motivo."
        )


def preserve_interval(current: IntervalData, candidate: IntervalData) -> None:
    if any(
        getattr(current, name) != getattr(candidate, name)
        for name in (
            "repetitions",
            "rest_seconds",
            "target_rpe",
        )
    ) or {m.name: m.value for m in current.target} != {m.name: m.value for m in candidate.target}:
        raise InvalidExecution("La prescripción original no puede modificarse.")


def validate_adaptation(row: StrengthData) -> None:
    if not isinstance(row.adaptation_reason, str):
        raise InvalidExecution("El motivo de adaptación debe ser texto.")
    adapted = any(getattr(row, name) is not None for name in ADAPTATION_FIELDS)
    if (adapted and not row.adaptation_reason.strip()) or len(row.adaptation_reason) > 1000:
        raise InvalidExecution("Una adaptación requiere un motivo de hasta 1000 caracteres.")
    if row.actual_exercise is not None and (
        type(row.actual_exercise) is not int or row.actual_exercise <= 0
    ):
        raise InvalidExecution("Ejercicio real inválido.")
    for value, choices in (
        (row.actual_load_type, {"external", "bodyweight", "assisted"}),
        (row.actual_kind, {"warmup", "work", "failed"}),
        (row.actual_side, {"both", "left", "right"}),
    ):
        if value is not None and (not isinstance(value, str) or value not in choices):
            raise InvalidExecution("Clasificación de adaptación inválida.")
    for value, maximum in (
        (row.actual_tempo, 30),
        (row.actual_range_of_motion, 80),
        (row.actual_group, 80),
    ):
        if value is not None and (not isinstance(value, str) or len(value) > maximum):
            raise InvalidExecution("Texto de adaptación demasiado largo.")


def reconcile_adaptation(
    previous: StrengthData | None,
    candidate: StrengthData,
    provided: frozenset[AdaptationField] | None = None,
) -> StrengthData:
    """Mutation-only presence; never store it in snapshots or observations.

    None denotes a full typed snapshot. JSON/POST boundaries always supply the
    actual key set, including an empty set for a legacy client. Clearing an
    existing override is not an observation: return-to-source must be recorded
    as an explicit concrete classification with a reason supplied in this change.
    """
    supplied = frozenset(AdaptationField) if provided is None else provided
    if not isinstance(supplied, frozenset) or any(
        not isinstance(f, AdaptationField) for f in supplied
    ):
        raise InvalidExecution("Presencia de adaptación inválida.")
    old = previous or StrengthData(candidate.exercise)
    result = replace(
        candidate,
        actual_exercise=candidate.actual_exercise
        if AdaptationField.EXERCISE in supplied
        else old.actual_exercise,
        actual_load_type=candidate.actual_load_type
        if AdaptationField.LOAD_TYPE in supplied
        else old.actual_load_type,
        actual_kind=candidate.actual_kind if AdaptationField.KIND in supplied else old.actual_kind,
        actual_tempo=candidate.actual_tempo
        if AdaptationField.TEMPO in supplied
        else old.actual_tempo,
        actual_range_of_motion=candidate.actual_range_of_motion
        if AdaptationField.RANGE_OF_MOTION in supplied
        else old.actual_range_of_motion,
        actual_side=candidate.actual_side if AdaptationField.SIDE in supplied else old.actual_side,
        actual_group=candidate.actual_group
        if AdaptationField.GROUP in supplied
        else old.actual_group,
        adaptation_reason=candidate.adaptation_reason
        if AdaptationField.REASON in supplied
        else old.adaptation_reason,
    )
    validate_adaptation(result)
    if previous is not None:
        if any(
            getattr(old, name) is not None
            and getattr(result, name) in (None, "")
            and getattr(old, name) != getattr(result, name)
            for name in ADAPTATION_FIELDS
        ):
            raise InvalidExecution(
                "No se elimina una adaptación con null o vacío; declara el valor real y su motivo explícito."
            )
        if old.adaptation_reason.strip() and not result.adaptation_reason.strip():
            raise InvalidExecution("El motivo observado no se elimina con null o vacío.")
    changed = any(getattr(old, name) != getattr(result, name) for name in ADAPTATION_FIELDS)
    if changed and (AdaptationField.REASON not in supplied or not result.adaptation_reason.strip()):
        raise InvalidExecution(
            "Cambiar una adaptación requiere un motivo explícito no vacío en este cambio."
        )
    return result


def identities[T: BlockData | StrengthData | IntervalData](
    previous: tuple[T, ...], incoming: tuple[T, ...], *, frozen: bool
) -> tuple[tuple[T | None, T], ...]:
    """No foreign lookup. ID-less clients address unchanged positions at a revision.

    Rows cannot disappear implicitly; an absent identity is not permission to erase
    pending results or to replace the original intention with a different row.
    """
    by_id = {row.id: (index, row) for index, row in enumerate(previous) if row.id is not None}
    used: set[int] = set()
    result: list[tuple[T | None, T]] = []
    for index, candidate in enumerate(incoming):
        match = (
            by_id.get(candidate.id)
            if candidate.id is not None
            else ((index, previous[index]) if index < len(previous) else None)
        )
        if candidate.id is not None and match is None:
            raise InvalidExecution("Identidad de bloque o fila no disponible en esta sesión.")
        old = None
        if match is not None:
            position, old = match
            if position in used or position != index:
                raise InvalidExecution("Identidades duplicadas o prescripción reordenada.")
            used.add(position)
            if candidate.source not in (None, old.source):
                raise InvalidExecution("La procedencia de la fila no puede modificarse.")
            candidate = replace(candidate, id=old.id, source=old.source)
            if isinstance(candidate, BlockData) and isinstance(old, BlockData):
                candidate = replace(candidate, order=old.order)
        elif candidate.source is not None:
            raise InvalidExecution("La procedencia solo se asigna al iniciar la prescripción.")
        result.append((old, candidate))
    if len(used) != len(previous):
        raise InvalidExecution("Conserva las filas existentes y sus resultados desconocidos.")
    return tuple(result)


def reconcile_blocks(
    previous: tuple[BlockData, ...],
    incoming: tuple[BlockData, ...],
    *,
    frozen: bool,
    adaptation_presence: AdaptationPresence | None = None,
) -> tuple[BlockData, ...]:
    if adaptation_presence is not None and (
        not isinstance(adaptation_presence, tuple)
        or any(
            not isinstance(rows, tuple)
            or any(not isinstance(presence, frozenset) for presence in rows)
            for rows in adaptation_presence
        )
    ):
        raise InvalidExecution("Presencia de adaptación inválida.")
    if adaptation_presence is not None and (
        len(adaptation_presence) != len(incoming)
        or any(
            len(presence) != len(block.sets)
            for presence, block in zip(adaptation_presence, incoming, strict=True)
        )
    ):
        raise InvalidExecution("Presencia de adaptación incompatible con las filas.")
    result = []
    for block_index, (old, block) in enumerate(identities(previous, incoming, frozen=frozen)):
        if (
            old is not None
            and frozen
            and (
                (old.sport, old.title) != (block.sport, block.title)
                or {m.name: m.value for m in old.target} != {m.name: m.value for m in block.target}
            )
        ):
            raise InvalidExecution("El bloque conserva su prescripción original.")
        sets = []
        for row_index, (old_set, row) in enumerate(
            identities(old.sets if old else (), block.sets, frozen=frozen)
        ):
            if old_set is not None and frozen:
                preserve_strength(old_set, row)
            row = reconcile_adaptation(
                old_set,
                row,
                adaptation_presence[block_index][row_index]
                if adaptation_presence is not None
                else None,
            )
            sets.append(row)
        intervals = []
        for old_interval, row_interval in identities(
            old.intervals if old else (), block.intervals, frozen=frozen
        ):
            if old_interval is not None and frozen:
                preserve_interval(old_interval, row_interval)
            intervals.append(row_interval)
        result.append(replace(block, sets=tuple(sets), intervals=tuple(intervals)))
    return tuple(result)
