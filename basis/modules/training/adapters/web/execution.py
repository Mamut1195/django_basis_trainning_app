"""HTTP presentation for training execution."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F, Q, Window
from django.db.models.functions import Coalesce, RowNumber
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from basis.adapters.web.framework import Conflict, owner, public_id, sync_session, write_required
from basis.shared.identifiers import SessionId

from ...domain.manual import SessionParent
from .. import manual_actions as mutations
from ..actions import session_snapshot
from ..models import (
    Block,
    PlannedSession,
    Session,
    StrengthSet,
)
from .forms import (
    BlockForm,
    MetricsForm,
    SessionForm,
)


@write_required
def session_new(request: HttpRequest) -> HttpResponse:
    form = SessionForm(request.POST or None)
    block_form = BlockForm(request.POST or None, prefix="block")
    if request.method == "POST" and form.is_valid() and block_form.is_valid():
        session_id = mutations.create_session(
            owner(request).pk,
            form.save(commit=False),
            block_form.cleaned_data["sport"],
            block_form.cleaned_data["title"],
        )
        return redirect("session-detail", pk=session_id)
    return render(
        request,
        "shared/form.html",
        {
            "title": "Registrar entrenamiento",
            "subtitle": "Puedes dejar los datos que no conozcas sin registrar.",
            "form": form,
            "extra_forms": [block_form],
        },
    )


@login_required
def session_detail(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    session = get_object_or_404(
        Session.objects.prefetch_related(
            "blocks__sets__exercise", "blocks__sets__actual_exercise", "blocks__intervals"
        ),
        pk=pk,
        owner=owner(request),
    )
    rows = [row for block in session.blocks.all() for row in block.sets.all()]
    keys = {
        (
            row.actual_exercise_id or row.exercise_id,
            row.actual_load_type or row.load_type,
            row.actual_side or row.side,
        )
        for row in rows
    }
    previous_by_key: dict[tuple[int, str, str], StrengthSet] = {}
    if keys:
        # One latest result per effective exercise/load/side, not one query per set.
        # Coalesce deliberately falls back only on NULL in historical observations.
        history = (
            StrengthSet.objects.filter(
                block__session__owner_id=session.owner_id,
                block__session__status="completed",
                block__session__date__lte=session.date,
                actual_reps__isnull=False,
            )
            .exclude(block__session=session)
            .annotate(
                reference_exercise=Coalesce("actual_exercise_id", "exercise_id"),
                reference_load_type=Coalesce("actual_load_type", "load_type"),
                reference_side=Coalesce("actual_side", "side"),
                reference_rank=Window(
                    expression=RowNumber(),
                    partition_by=[
                        Coalesce("actual_exercise_id", "exercise_id"),
                        Coalesce("actual_load_type", "load_type"),
                        Coalesce("actual_side", "side"),
                    ],
                    order_by=[
                        F("block__session__date").desc(),
                        F("block__session__created_at").desc(),
                        F("pk").desc(),
                    ],
                ),
            )
            .filter(
                reference_exercise__in={key[0] for key in keys},
                reference_load_type__in={key[1] for key in keys},
                reference_side__in={key[2] for key in keys},
                reference_rank=1,
            )
            .select_related("block__session")
            .order_by()
        )
        for previous in history:
            key = (
                previous.actual_exercise_id
                if previous.actual_exercise_id is not None
                else previous.exercise_id,
                previous.actual_load_type
                if previous.actual_load_type is not None
                else previous.load_type,
                previous.actual_side if previous.actual_side is not None else previous.side,
            )
            previous_by_key[key] = previous
    quick_sets = [
        (
            row,
            previous_by_key.get(
                (
                    row.actual_exercise_id or row.exercise_id,
                    row.actual_load_type or row.load_type,
                    row.actual_side or row.side,
                )
            ),
        )
        for row in rows
    ]
    strength_sets = [row for row in rows if row.block.sport == "strength"]
    strength_summary: list[dict[str, object]] = []
    if strength_sets:
        best: dict[int, tuple[Decimal, date, Decimal, int]] = {}
        mark_history = (
            StrengthSet.objects.filter(
                block__session__owner_id=session.owner_id,
                block__session__status="completed",
                exercise_id__in={row.exercise_id for row in strength_sets},
                actual_kg__gt=0,
                actual_reps__gt=0,
            )
            .select_related("block__session")
            .order_by("block__session__date", "pk")
        )
        for mark in mark_history:
            assert mark.actual_kg is not None and mark.actual_reps is not None
            session_row = mark.block.session
            if session_row is None:
                continue
            volume = mark.actual_kg * mark.actual_reps
            current = best.get(mark.exercise_id)
            if current is None or volume > current[0]:
                best[mark.exercise_id] = (
                    volume,
                    session_row.date,
                    mark.actual_kg,
                    mark.actual_reps,
                )
        for block in session.blocks.all():
            if block.sport != "strength":
                continue
            counts: dict[int, int] = {}
            targets: dict[int, tuple[int | None, Decimal | None]] = {}
            names: dict[int, str] = {}
            for set_row in block.sets.all():
                counts[set_row.exercise_id] = counts.get(set_row.exercise_id, 0) + 1
                targets.setdefault(set_row.exercise_id, (set_row.target_reps, set_row.target_kg))
                names[set_row.exercise_id] = set_row.exercise.nombre
            exercises: list[dict[str, object]] = []
            for exercise_id, count in counts.items():
                record = best.get(exercise_id)
                reps, kg = targets[exercise_id]
                reps_text = str(reps) if reps is not None else "—"
                kg_text = format(kg.normalize(), "f") if kg is not None else "—"
                exercises.append(
                    {
                        "name": names[exercise_id],
                        "sets": count,
                        "target": f"{reps_text} × {kg_text} kg",
                        "best": f"{record[2]} kg × {record[3]}" if record else None,
                        "best_date": record[1] if record else None,
                    }
                )
            strength_summary.append({"title": block.title, "exercises": exercises})
    return render(
        request,
        "training/execution/session.html",
        {
            "session": session,
            "snapshot": session_snapshot(session),
            "blocks": session.blocks.all(),
            "quick_sets": quick_sets,
            "strength_summary": strength_summary,
            "strength_total": len(strength_sets),
            "strength_exercise_count": len({row.exercise_id for row in strength_sets}),
        },
    )


@write_required
def session_edit(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    mutations.inspect_metadata(owner(request).pk, SessionParent(SessionId(pk)))
    session = get_object_or_404(Session, pk=pk, owner=owner(request))
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        snapshot = session_snapshot(session)
        snapshot.update(
            {k: str(v) if v is not None else None for k, v in form.cleaned_data.items()}
        )
        snapshot["duration_seconds"] = form.cleaned_data["duration_seconds"]
        snapshot["revision"] = int(request.POST.get("revision", 0))
        try:
            sync_session(owner(request), uuid.uuid4(), snapshot)
            return redirect("session-detail", pk=pk)
        except Conflict:
            form.add_error(None, "La sesión cambió. Recarga para revisar la versión actual.")
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "shared/form.html",
        {"title": "Editar sesión", "form": form, "revision": session.revision},
    )


def get_parent(
    request: HttpRequest, kind: str, pk: int | str | uuid.UUID | None
) -> Session | PlannedSession:
    ref = mutations.parse_parent(kind, pk)
    mutations.inspect_parent(owner(request).pk, ref)
    if isinstance(ref, SessionParent):
        return get_object_or_404(Session, pk=ref.id, owner=owner(request))
    return get_object_or_404(PlannedSession, pk=ref.id, owner=owner(request))


def block_redirect(block: Block) -> HttpResponse:
    return redirect(
        "session-detail" if block.session_id else "scheduled-detail",
        pk=block.session_id or block.planned_id,
    )


@write_required
def block_new(request: HttpRequest, kind: str, pk: int | str | uuid.UUID | None) -> HttpResponse:
    parent = get_parent(request, kind, pk)
    form = BlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        block_id = mutations.add_block(
            owner(request).pk,
            parent,
            request.POST.get("revision"),
            form.cleaned_data["sport"],
            form.cleaned_data["title"],
        )
        return block_redirect(get_object_or_404(Block, pk=block_id))
    return render(
        request,
        "shared/form.html",
        {"title": "Añadir bloque", "form": form, "revision": parent.revision},
    )


def owned_block(request: HttpRequest, pk: int) -> Block:
    return get_object_or_404(
        Block.objects.select_related("session", "planned__plan"),
        Q(session__owner=owner(request)) | Q(planned__owner=owner(request)),
        pk=pk,
    )


@write_required
def block_metrics(request: HttpRequest, pk: int) -> HttpResponse:
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    attr = "actual" if block.session_id else "target"
    form = MetricsForm(request.POST or None, sport=block.sport, initial=getattr(block, attr))
    if request.method == "POST" and form.is_valid():
        mutations.save_metrics(
            owner(request).pk, block, request.POST.get("revision"), form.cleaned_data
        )
        return block_redirect(block)
    return render(
        request,
        "shared/form.html",
        {
            "title": block.title,
            "subtitle": "Resultado real" if block.session_id else "Prescripción",
            "revision": parent.revision,
            "form": form,
        },
    )


@login_required
@require_GET
def snapshot_api(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    session = get_object_or_404(
        Session.objects.prefetch_related("blocks__sets", "blocks__intervals"),
        pk=pk,
        owner=owner(request),
    )
    return JsonResponse({"account": str(public_id(request)), "session": session_snapshot(session)})
