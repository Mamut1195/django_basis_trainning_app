"""Owner-selected export rows; foreign persistence schemas never leave this adapter."""

from basis.adapters.django.export import export_section
from basis.shared.export import ExportSection
from basis.shared.identifiers import AccountId

from .models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    User,
    UserExerciseRM,
    Wellness,
    WorkoutData,
)


class DjangoAthleteExport:
    def read(self, owner: AccountId) -> tuple[ExportSection, ...]:
        return (
            export_section(
                User.objects.filter(account_id=owner), "athlete", "daily_trainning_app.user"
            ),
            export_section(
                AthleteSettings.objects.filter(owner_id=owner),
                "athletesettings",
                "training.athletesettings",
            ),
            export_section(
                Measurement.objects.filter(owner_id=owner), "measurement", "training.measurement"
            ),
            export_section(
                SportProfile.objects.filter(owner_id=owner), "sportprofile", "training.sportprofile"
            ),
            export_section(
                Wellness.objects.filter(owner_id=owner), "wellness", "training.wellness"
            ),
            export_section(
                WorkoutData.objects.filter(user__account_id=owner),
                "workoutdata",
                "daily_trainning_app.workoutdata",
            ),
            export_section(
                UserExerciseRM.objects.filter(user__account_id=owner),
                "userexerciserm",
                "daily_trainning_app.userexerciserm",
            ),
        )
