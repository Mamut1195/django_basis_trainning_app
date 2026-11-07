"""Read-only personal records page: every exercise and every sport."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from basis.adapters.web.framework import owner
from basis.bootstrap.records import exercise_choices
from basis.shared.identifiers import AccountId

from ..records import grouped_sports, sport_records, strength_records


@login_required
@require_safe
def all_records(request: HttpRequest) -> HttpResponse:
    account = AccountId(owner(request).pk)
    query = (request.GET.get("q") or "").strip()[:80]
    strength = strength_records(account, exercise_choices(), query)
    return render(
        request,
        "training/progress/records.html",
        {
            "query": query,
            "marked": [record for record in strength if record.value is not None],
            "unmarked": [record for record in strength if record.value is None],
            "sports": grouped_sports(sport_records(account)),
        },
    )
