"""Synthetic athletes exercise the week decision without a provider or a database."""

from decimal import Decimal
from unittest import TestCase

from basis.modules.coach.domain.adaptation import ObservedSession, adapt
from basis.modules.coach.domain.prompts import INSTRUCTIONS_VERSION, PLAN_FORMAT, SYSTEM


class AdaptationTests(TestCase):
    def test_hiking_and_cycling_stay_separate_and_protect_the_heavier_day(self) -> None:
        decision = adapt(
            (
                ObservedSession("hiking", "elapsed", 10_800, Decimal(4)),
                ObservedSession("cycling", "elapsed", 3_600, Decimal(6)),
            ),
            goal="Progresar en ciclismo",
            progress_sport="cycling",
            availability=(2, 4, 6),
            pain=False,
        )

        self.assertEqual(decision.action, "propose")
        self.assertEqual(decision.protects, ("hiking",))
        self.assertEqual(decision.progression, "una sola subida en Ciclismo")
        loads = {(row.sport, row.protocol): row.load for row in decision.loads}
        self.assertEqual(
            loads,
            {("hiking", "elapsed"): Decimal("720.00"), ("cycling", "elapsed"): Decimal("360.00")},
        )
        self.assertIn("720.00 UA", decision.message)
        self.assertIn("360.00 UA", decision.message)
        self.assertIn("No las sumo", decision.message)
        self.assertNotIn("1080", decision.message)

    def test_missing_rpe_is_a_question_and_not_zero(self) -> None:
        decision = adapt(
            (ObservedSession("cycling", "elapsed", 3_600, None),),
            goal="Progresar en ciclismo",
            progress_sport="cycling",
            availability=(2, 4),
            pain=False,
        )

        self.assertEqual(decision.action, "ask")
        self.assertIsNone(decision.loads[0].load)
        self.assertEqual(decision.loads[0].missing_rpe, 1)
        self.assertIn("No lo tomo como cero", decision.message)
        self.assertIsNone(decision.progression)

    def test_elapsed_and_moving_hiking_are_not_one_number(self) -> None:
        decision = adapt(
            (
                ObservedSession("hiking", "elapsed", 10_800, Decimal(4)),
                ObservedSession("hiking", "moving", 7_200, Decimal(4)),
            ),
            goal="Progresar en hiking",
            progress_sport="hiking",
            availability=(6, 7),
            pain=False,
        )

        loads = {row.protocol: row.load for row in decision.loads}
        self.assertEqual(loads, {"elapsed": Decimal("720.00"), "moving": Decimal("480.00")})
        self.assertNotIn("1200", decision.message)

    def test_pain_stops_the_proposal(self) -> None:
        decision = adapt(
            (ObservedSession("cycling", "elapsed", 3_600, Decimal(5)),),
            goal="Progresar en ciclismo",
            progress_sport="cycling",
            availability=(2,),
            pain=True,
        )

        self.assertEqual(decision.action, "stop")
        self.assertIn("valoración profesional", decision.message)
        self.assertIsNone(decision.progression)

    def test_instructions_require_the_same_rules(self) -> None:
        self.assertEqual(INSTRUCTIONS_VERSION, "basis-coach-633-v3")
        self.assertIn("No sumes cargas", SYSTEM)
        self.assertIn("no uses\ncero", SYSTEM)
        self.assertIn("una sola progresión", SYSTEM)
        self.assertIn("qué proteges", PLAN_FORMAT)
