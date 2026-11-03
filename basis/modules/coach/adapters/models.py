import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from basis.adapters.django.persistence import Owned


class UsagePeriod(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    is_trial = models.BooleanField(default=False)
    spent = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    reserved = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    short_count = models.PositiveIntegerField(default=0)
    plan_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "key"], name="usage_owner_period"),
            models.CheckConstraint(
                condition=models.Q(spent__gte=0, reserved__gte=0), name="usage_nonnegative"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        is_trial=True,
                        spent__lte=Decimal("0.03") - models.F("reserved"),
                        short_count__lte=5,
                        plan_count__lte=1,
                    )
                    | models.Q(
                        is_trial=False,
                        spent__lte=1 - models.F("reserved"),
                        short_count__lte=200,
                        plan_count__lte=8,
                    )
                ),
                name="usage_within_budget",
            ),
        ]


class TrialFund(models.Model):
    month = models.CharField(max_length=7, unique=True)
    spent = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    reserved = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    cap = models.DecimalField(max_digits=12, decimal_places=8, default=5)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    spent__gte=0,
                    reserved__gte=0,
                    cap__gte=0,
                    spent__lte=models.F("cap") - models.F("reserved"),
                ),
                name="fund_within_budget",
            )
        ]


class AIJob(Owned):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(default=uuid.uuid4)
    kind = models.CharField(
        max_length=10, choices=[("short", "Consulta breve"), ("plan", "Propuesta de plan")]
    )
    prompt = models.TextField()
    context = models.JSONField(default=dict)
    status = models.CharField(max_length=15, default="pending")
    usage_period = models.ForeignKey(UsagePeriod, on_delete=models.PROTECT)
    trial_fund = models.ForeignKey(TrialFund, null=True, blank=True, on_delete=models.PROTECT)
    reservation = models.DecimalField(max_digits=12, decimal_places=8)
    cost = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    requested_model = models.CharField(max_length=100)
    base_plan = models.ForeignKey(
        "basis_training.TrainingPlan", on_delete=models.PROTECT, null=True, blank=True
    )
    reported_model = models.CharField(max_length=100, blank=True)
    pricing_version = models.CharField(max_length=30, default="flash-peak-2026-10-17")
    pricing_snapshot = models.JSONField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    cache_hit_tokens = models.PositiveIntegerField(null=True, blank=True)
    answer = models.TextField(blank=True)
    error = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["owner", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["owner", "request_key"], name="ai_request_idempotent"),
            models.CheckConstraint(
                condition=models.Q(reservation__gte=0)
                & (
                    models.Q(cost__isnull=True)
                    | models.Q(cost__gte=0, cost__lte=models.F("reservation"))
                ),
                name="job_cost_within_reservation",
            ),
        ]


class AIReconciliation(models.Model):
    """Append-only decisions; database guards also reject bulk update/delete."""

    job = models.ForeignKey(AIJob, on_delete=models.PROTECT, related_name="reconciliations")
    key = models.CharField(max_length=100)
    actor = models.CharField(max_length=150)
    reference = models.CharField(max_length=500)
    evidence = models.TextField()
    decision = models.CharField(max_length=10)
    confirmed_no_charge = models.BooleanField(default=False)
    reported_model = models.TextField(blank=True)
    token_usage = models.JSONField(null=True)
    outcome = models.CharField(max_length=10)
    reason = models.CharField(max_length=150, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=8, null=True)
    job_status = models.CharField(max_length=15)
    created_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "key"], name="ai_reconciliation_idempotent")
        ]


class PlanProposal(Owned):
    job = models.OneToOneField(AIJob, on_delete=models.PROTECT)
    base_plan = models.ForeignKey(
        "basis_training.TrainingPlan", on_delete=models.PROTECT, null=True, blank=True
    )
    content = models.JSONField()
    status = models.CharField(max_length=12, default="pending")
    accepted_plan = models.OneToOneField(
        "basis_training.TrainingPlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="proposal",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        self.same_owner(self.job, self.base_plan, self.accepted_plan)


class AIServiceState(models.Model):
    key = models.CharField(max_length=20, primary_key=True, default="deepseek")
    blocked = models.BooleanField(default=False)
    reason = models.CharField(max_length=150, blank=True)
