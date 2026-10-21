"""HTTP presentation for training execution."""

from __future__ import annotations

import uuid

from django.contrib.auth.decorators import login_required
from django.db.models import Q
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
    return render(
        request,
        "training/execution/session.html",
        {"session": session, "snapshot": session_snapshot(session), "blocks": session.blocks.all()},
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
