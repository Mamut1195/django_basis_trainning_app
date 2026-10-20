"""HTTP presentation for training strength."""

from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from basis.adapters.web.framework import owner, write_required

from .. import manual_actions as mutations
from ..models import (
    StrengthSet,
)
from .execution import block_redirect, get_parent, owned_block
from .forms import (
    StrengthSetForm,
)


@write_required
def set_edit(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(
        StrengthSet.objects.select_related("block__session", "block__planned__plan"),
        Q(block__session__owner=owner(request)) | Q(block__planned__owner=owner(request)),
        pk=pk,
    )
    block = row.block
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = StrengthSetForm(request.POST or None, instance=row, block=block)
    for key in mutations.edit_form_policy(owner(request).pk, parent).strength_read_only:
        if key in form.fields:
            form.fields[key].disabled = True
    if request.method == "POST" and form.is_valid():
        mutations.save_strength(
            owner(request).pk, form.save(commit=False), request.POST.get("revision"), creating=False
        )
        return block_redirect(block)
    return render(
        request,
        "shared/form.html",
        {"title": "Registrar resultado de serie", "form": form, "revision": parent.revision},
    )


@write_required
def set_new(request: HttpRequest, pk: int) -> HttpResponse:
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = StrengthSetForm(request.POST or None, block=block)
    if request.method == "POST" and form.is_valid():
        mutations.save_strength(
            owner(request).pk, form.save(commit=False), request.POST.get("revision"), creating=True
        )
        return block_redirect(block)
    return render(
        request,
        "shared/form.html",
        {"title": "Añadir serie", "form": form, "revision": parent.revision},
    )
