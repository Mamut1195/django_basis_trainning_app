from __future__ import annotations

import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner, write_required
from basis.modules.billing.public import ProviderUnavailable
from basis.modules.coach.adapters.actions import enqueue
from basis.modules.coach.adapters.models import AIJob, PlanProposal
from basis.modules.coach.adapters.proposal_actions import edit_and_accept_proposal, reject_proposal
from basis.modules.coach.adapters.web.forms import ProposalReviewForm


@login_required
def coach(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "coach/consultations/index.html",
        {
            "jobs": AIJob.objects.filter(owner=owner(request)).order_by("-created_at")[:20],
            "plans": presentation.current_plans(owner(request).pk),
            "ai_enabled": settings.AI_ENABLED and bool(settings.DEEPSEEK_API_KEY),
            "request_key": uuid.uuid4(),
        },
    )


@login_required
@require_POST
def coach_ask(request: HttpRequest) -> HttpResponse:

    try:
        job = enqueue(
            owner(request),
            request.POST.get("kind"),
            request.POST.get("prompt", ""),
            request.POST.get("request_key"),
            request.POST.get("base_plan") or None,
        )
        return redirect("job-detail", pk=job.pk)
    except (ValidationError, ProviderUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect("coach")


@login_required
def job_detail(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    job = get_object_or_404(AIJob, pk=pk, owner=owner(request))
    template = (
        "coach/jobs/_result.html" if request.headers.get("HX-Request") else "coach/jobs/detail.html"
    )
    display_answer = job.answer if job.kind == "short" else ""
    if job.kind == "plan" and job.answer:
        try:
            content = json.loads(job.answer)
            display_answer = content.get("question", "") if isinstance(content, dict) else ""
        except ValueError:
            pass
    return render(
        request,
        template,
        {
            "job": job,
            "display_answer": display_answer,
            "proposal": PlanProposal.objects.filter(job=job, owner=owner(request)).first(),
        },
    )


@write_required
def proposal_review(request: HttpRequest, pk: int) -> HttpResponse:

    proposal = get_object_or_404(PlanProposal, pk=pk, owner=owner(request))
    form = ProposalReviewForm(request.POST or None, content=proposal.content, owner=owner(request))
    if request.method == "POST":
        if request.POST.get("decision") == "reject":
            reject_proposal(owner(request), proposal.pk)
            return redirect("coach")
        if form.is_valid():
            try:
                plan = edit_and_accept_proposal(owner(request), proposal.pk, form.to_content())
                return redirect("plan-detail", pk=plan.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, "coach/proposals/review.html", {"proposal": proposal, "form": form})
