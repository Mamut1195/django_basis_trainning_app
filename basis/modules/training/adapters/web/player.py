"""Small owner-scoped presentation adapter for the session player."""

from __future__ import annotations

import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from basis.adapters.web.framework import Conflict, owner, sync_session, write_required
from basis.bootstrap.records import exercise_choices
from basis.shared.identifiers import AccountId

from .. import manual_actions as mutations
from ..actions import session_snapshot
from ..models import Session, StrengthSet
from ..records import rebuild


class QuickSetForm(forms.ModelForm[StrengthSet]):
    class Meta:
        model = StrengthSet
        fields = [
            "actual_reps",
            "actual_kg",
            "actual_rpe",
            "actual_rir",
            "actual_isometric_seconds",
            "actual_distance_m",
        ]


@write_required
@require_POST
def save_set(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(
        StrengthSet.objects.select_related("block__session"),
        pk=pk,
        block__session__owner=owner(request),
    )
    form = QuickSetForm(request.POST, instance=row)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    try:
        mutations.save_strength(
            owner(request).pk,
            form.save(commit=False),
            request.POST.get("revision"),
            creating=False,
            provided_fields=QuickSetForm.Meta.fields,
        )
    except Conflict:
        return JsonResponse({"error": "La sesión cambió. Recarga y revisa tus datos."}, status=409)
    except ValidationError as error:
        return JsonResponse({"error": str(error)}, status=400)
    row.refresh_from_db()
    session = row.block.session
    assert session is not None
    session.refresh_from_db()
    if request.headers.get("Accept") != "application/json":
        return redirect("session-detail", pk=session.pk)
    return JsonResponse(
        {
            "revision": session.revision,
            "values": {
                field: str(getattr(row, field)) if getattr(row, field) is not None else ""
                for field in QuickSetForm.Meta.fields
            },
        }
    )


@write_required
@require_POST
def complete(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    session = get_object_or_404(Session, pk=pk, owner=owner(request))
    if request.POST.get("confirm") != "on":
        messages.error(request, "Confirma que revisaste los datos antes de cerrar.")
        return redirect("session-detail", pk=pk)
    try:
        revision = int(request.POST.get("revision", ""))
    except ValueError:
        messages.error(request, "Recarga la sesión antes de cerrar.")
        return redirect("session-detail", pk=pk)
    snapshot = session_snapshot(session)
    snapshot["revision"] = revision
    snapshot["status"] = "completed"
    try:
        sync_session(owner(request), uuid.uuid4(), snapshot)
    except Conflict:
        messages.error(
            request,
            "La sesión cambió mientras la revisabas. Ya cargamos la versión más reciente; revisa y vuelve a cerrar.",
        )
        return redirect("session-detail", pk=pk)
    except ValidationError as error:
        messages.error(request, str(error))
        return redirect("session-detail", pk=pk)
    rebuild(AccountId(owner(request).pk), exercise_choices())
    return redirect("session-detail", pk=pk)
