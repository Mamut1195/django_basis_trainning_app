from __future__ import annotations

import json
import uuid
from hashlib import sha256
from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner, write_required
from basis.modules.billing.public import ProviderUnavailable
from basis.modules.coach.adapters.actions import cancel, enqueue
from basis.modules.coach.adapters.models import AIJob, PlanProposal
from basis.modules.coach.adapters.proposal_actions import (
    accept_proposal,
    comparison,
    edit_and_accept_proposal,
    reject_proposal,
    review_proposal,
)
from basis.modules.coach.adapters.proposals import review_key
from basis.modules.coach.adapters.web.forms import ProposalReviewForm
from basis.modules.coach.domain.jobs import CoachInvalid, JobNotFound


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
    return _job_result(request, pk)


@login_required
@require_POST
def job_cancel(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    try:
        cancel(owner(request), pk)
    except JobNotFound:
        raise Http404 from None
    except CoachInvalid as exc:
        return _job_result(request, pk, conflict=str(exc))
    return redirect("job-detail", pk=pk)


def _job_result(request: HttpRequest, pk: uuid.UUID, *, conflict: str = "") -> HttpResponse:
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
            "cancellation_conflict": conflict,
        },
        status=409 if conflict else 200,
    )


@write_required
def proposal_review(request: HttpRequest, pk: int) -> HttpResponse:
    proposal = get_object_or_404(PlanProposal, pk=pk, owner=owner(request))
    if request.method == "GET" and proposal.status != "pending":
        return render(request, "coach/proposals/review.html", {"proposal": proposal})
    key = review_key(proposal)
    token = signing.dumps({"draft": key, "proposal": pk}, salt="coach.proposal-review")
    form: ProposalReviewForm | None = None
    changes: list[tuple[str, str, str]] = []
    error = ""
    compared = False
    status = 200

    def candidate_key(content: object) -> str:
        return sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    try:
        decision = request.POST.get("decision") if request.method == "POST" else None
        expected: str | None = None
        receipt: dict[str, object] = {}
        if decision in ("accept", "reject"):
            try:
                receipt = cast(
                    dict[str, object],
                    signing.loads(
                        request.POST.get("review_token", ""),
                        salt="coach.proposal-review",
                        max_age=3600,
                    ),
                )
                if receipt.get("proposal") != pk:
                    raise signing.BadSignature
                expected = str(receipt["draft"])
            except (signing.BadSignature, KeyError, TypeError):
                raise ValidationError(
                    "La revisión expiró o no es válida. Recarga y compara de nuevo."
                ) from None
        if decision == "reject":
            reject_proposal(owner(request), pk, expected)
            return redirect("coach")
        if proposal.status == "accepted" and decision == "accept":
            # A retry returns the committed result without parsing old content or
            # requiring the athlete's profile to still match the old draft.
            if receipt.get("candidate") != candidate_key(proposal.content):
                raise ValidationError(
                    "Esta comparación no corresponde al resultado aceptado. Recarga la revisión."
                )
            plan = accept_proposal(owner(request), pk)
            return redirect("plan-detail", pk=plan.pk)
        review_proposal(owner(request), pk, expected_review=key)
        form = ProposalReviewForm(
            request.POST or None, content=proposal.content, owner=owner(request)
        )
        content: object = proposal.content
        if request.method == "POST":
            if decision not in ("preview", "accept"):
                raise ValidationError("Selecciona comparar, aceptar o descartar.")
            if form.is_valid():
                content = form.to_content()
                review_proposal(owner(request), pk, content, expected or key)
                if decision == "accept":
                    if receipt.get("candidate") != candidate_key(content):
                        raise ValidationError(
                            "Cambiaste campos después de comparar. Compara de nuevo antes de aceptar."
                        )
                    if not form.cleaned_data["constraints_reviewed"]:
                        raise ValidationError(
                            "Revisa equipo, limitaciones y datos faltantes antes de aceptar."
                        )
                    plan = edit_and_accept_proposal(owner(request), pk, content, expected)
                    return redirect("plan-detail", pk=plan.pk)
                token = signing.dumps(
                    {"draft": key, "proposal": pk, "candidate": candidate_key(content)},
                    salt="coach.proposal-review",
                )
                compared = True
            else:
                status = 400
        changes = comparison(owner(request), proposal, content)
    except ValidationError as exc:
        error = " ".join(exc.messages)
        status = 409 if request.method == "POST" else 400
    return render(
        request,
        "coach/proposals/review.html",
        {
            "proposal": proposal,
            "form": form,
            "changes": changes,
            "review_error": error,
            "review_token": token,
            "compared": compared,
            "preferences": proposal.job.context.get("preferences") if form is not None else None,
        },
        status=status,
    )
