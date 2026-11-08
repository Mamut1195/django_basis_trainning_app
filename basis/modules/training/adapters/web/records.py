"""Read-only personal records page: every exercise and every sport."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from basis.adapters.web.framework import owner
from basis.bootstrap.records import exercise_choices
from basis.shared.identifiers import AccountId

from ..records import ensure_records, grouped_sports, stored_sports, stored_strength


@login_required
@require_safe
def all_records(request: HttpRequest) -> HttpResponse:
    account = AccountId(owner(request).pk)
    query = (request.GET.get("q") or "").strip()[:80]
    choices = exercise_choices()
    ensure_records(account, choices)
    strength = stored_strength(account, choices, query)
    return render(
        request,
        "training/progress/records.html",
        {
            "query": query,
            "marked": [record for record in strength if record.value is not None],
            "unmarked": [record for record in strength if record.value is None],
            "sports": grouped_sports(stored_sports(account)),
        },
    )
