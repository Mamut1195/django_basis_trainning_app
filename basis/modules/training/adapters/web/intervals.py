"""HTTP presentation for training intervals."""

from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from basis.adapters.web.framework import owner, write_required

from .. import manual_actions as mutations
from ..models import (
    Interval,
)
from .execution import block_redirect, get_parent, owned_block
from .forms import (
    IntervalForm,
    MetricsForm,
)


@write_required
def interval_edit(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(
        Interval.objects.select_related("block__session", "block__planned__plan"),
        Q(block__session__owner=owner(request)) | Q(block__planned__owner=owner(request)),
        pk=pk,
    )
    block = row.block
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = IntervalForm(request.POST or None, instance=row, block=block)
    attr = "actual" if block.session_id else "target"
    metrics = MetricsForm(
        request.POST or None, sport=block.sport, initial=getattr(row, attr), prefix="metrics"
    )
    for key in mutations.edit_form_policy(owner(request).pk, parent).interval_read_only:
        form.fields[key].disabled = True
    if request.method == "POST" and form.is_valid() and metrics.is_valid():
        row = form.save(commit=False)
        setattr(row, attr, metrics.cleaned_data)
        mutations.save_interval(
            owner(request).pk, row, request.POST.get("revision"), creating=False
        )
        return block_redirect(block)
    return render(
        request,
        "shared/form.html",
        {
            "title": "Registrar intervalo",
            "form": form,
            "extra_forms": [metrics],
            "revision": parent.revision,
        },
    )


@write_required
def interval_new(request: HttpRequest, pk: int) -> HttpResponse:
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = IntervalForm(request.POST or None, block=block)
    target = MetricsForm(request.POST or None, sport=block.sport, prefix="target")
    actual = (
        MetricsForm(request.POST or None, sport=block.sport, prefix="actual")
        if block.session_id
        else None
    )
    if (
        request.method == "POST"
        and form.is_valid()
        and target.is_valid()
        and (not actual or actual.is_valid())
    ):
        row = form.save(commit=False)
        row.target = target.cleaned_data
        row.actual = actual.cleaned_data if actual else {}
        mutations.save_interval(owner(request).pk, row, request.POST.get("revision"), creating=True)
        return block_redirect(block)
    return render(
        request,
        "shared/form.html",
        {
            "title": "Añadir intervalo",
            "revision": parent.revision,
            "form": form,
            "extra_forms": [target, actual] if actual else [target],
        },
    )
