"""Idempotent seed for a complete, classified strength exercise library.

Names are normalized by the catalog model. Existing rows are never renamed or updated;
the command only creates what is missing. Muscle names and patterns are the vocabulary
used by ``basis.modules.training.domain.analysis`` for volume and gaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from django.core.management.base import BaseCommand, CommandParser

from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.shared.text import normalized_name

CLASSIFICATION: Final = "Fuerza"
PATTERNS: Final = (
    "empuje_horizontal",
    "empuje_vertical",
    "traccion_horizontal",
    "traccion_vertical",
    "sentadilla",
    "bisagra",
    "core_antiextension",
    "core_antirotacion",
    "core_flexion",
    "acarreo",
    "aislamiento",
    "gemelo",
)
MUSCLES: Final = (
    "Pecho",
    "Espalda",
    "Hombros",
    "Bíceps",
    "Tríceps",
    "Antebrazo",
    "Abdomen",
    "Cuádriceps",
    "Isquiotibiales",
    "Glúteos",
    "Gemelos",
    "Aductores",
)


@dataclass(frozen=True)
class LibraryExercise:
    nombre: str
    patron: str
    fatiga: str
    musculos: tuple[str, ...]
    equipo: str


EXERCISES: Final[tuple[LibraryExercise, ...]] = (
    LibraryExercise(
        "Press de banca con barra",
        "empuje_horizontal",
        "Medio",
        ("Pecho", "Tríceps", "Hombros"),
        "Barra",
    ),
    LibraryExercise(
        "Press de banca con mancuernas",
        "empuje_horizontal",
        "Medio",
        ("Pecho", "Tríceps"),
        "Mancuernas",
    ),
    LibraryExercise(
        "Press inclinado con mancuernas",
        "empuje_horizontal",
        "Medio",
        ("Pecho", "Hombros", "Tríceps"),
        "Mancuernas",
    ),
    LibraryExercise("Aperturas en polea", "aislamiento", "Bajo", ("Pecho",), "Polea"),
    LibraryExercise(
        "Fondos en paralelas",
        "empuje_horizontal",
        "Alto",
        ("Pecho", "Tríceps", "Hombros"),
        "Peso corporal",
    ),
    LibraryExercise(
        "Flexiones", "empuje_horizontal", "Bajo", ("Pecho", "Tríceps", "Abdomen"), "Peso corporal"
    ),
    LibraryExercise(
        "Dominadas", "traccion_vertical", "Alto", ("Espalda", "Bíceps"), "Peso corporal"
    ),
    LibraryExercise("Jalón al pecho", "traccion_vertical", "Bajo", ("Espalda", "Bíceps"), "Polea"),
    LibraryExercise(
        "Remo con barra", "traccion_horizontal", "Medio", ("Espalda", "Bíceps"), "Barra"
    ),
    LibraryExercise(
        "Remo con mancuerna", "traccion_horizontal", "Bajo", ("Espalda", "Bíceps"), "Mancuernas"
    ),
    LibraryExercise(
        "Remo en polea baja", "traccion_horizontal", "Bajo", ("Espalda", "Bíceps"), "Polea"
    ),
    LibraryExercise("Pull-over en polea", "aislamiento", "Bajo", ("Espalda",), "Polea"),
    LibraryExercise("Face pull", "traccion_horizontal", "Bajo", ("Espalda", "Hombros"), "Polea"),
    LibraryExercise(
        "Remo invertido", "traccion_horizontal", "Medio", ("Espalda", "Bíceps"), "Peso corporal"
    ),
    LibraryExercise(
        "Press militar con barra", "empuje_vertical", "Alto", ("Hombros", "Tríceps"), "Barra"
    ),
    LibraryExercise(
        "Press con mancuernas sentado",
        "empuje_vertical",
        "Medio",
        ("Hombros", "Tríceps"),
        "Mancuernas",
    ),
    LibraryExercise("Press Arnold", "empuje_vertical", "Medio", ("Hombros",), "Mancuernas"),
    LibraryExercise("Elevaciones laterales", "aislamiento", "Bajo", ("Hombros",), "Mancuernas"),
    LibraryExercise("Elevaciones laterales en polea", "aislamiento", "Bajo", ("Hombros",), "Polea"),
    LibraryExercise("Elevaciones frontales", "aislamiento", "Bajo", ("Hombros",), "Mancuernas"),
    LibraryExercise("Pájaros", "aislamiento", "Bajo", ("Hombros", "Espalda"), "Mancuernas"),
    LibraryExercise("Curl con barra", "aislamiento", "Bajo", ("Bíceps",), "Barra"),
    LibraryExercise("Curl con mancuernas", "aislamiento", "Bajo", ("Bíceps",), "Mancuernas"),
    LibraryExercise("Curl martillo", "aislamiento", "Bajo", ("Bíceps", "Antebrazo"), "Mancuernas"),
    LibraryExercise("Curl en banco predicador", "aislamiento", "Bajo", ("Bíceps",), "Barra"),
    LibraryExercise("Curl en polea", "aislamiento", "Bajo", ("Bíceps",), "Polea"),
    LibraryExercise("Extensión en polea", "aislamiento", "Bajo", ("Tríceps",), "Polea"),
    LibraryExercise("Press francés", "aislamiento", "Medio", ("Tríceps",), "Barra"),
    LibraryExercise(
        "Fondos en banco", "empuje_horizontal", "Bajo", ("Tríceps", "Hombros"), "Peso corporal"
    ),
    LibraryExercise("Patada de tríceps", "aislamiento", "Bajo", ("Tríceps",), "Mancuernas"),
    LibraryExercise("Extensión sobre la cabeza", "aislamiento", "Bajo", ("Tríceps",), "Mancuernas"),
    LibraryExercise("Curl de muñeca", "aislamiento", "Bajo", ("Antebrazo",), "Mancuernas"),
    LibraryExercise("Extensión de muñeca", "aislamiento", "Bajo", ("Antebrazo",), "Mancuernas"),
    LibraryExercise(
        "Paseo del granjero", "acarreo", "Alto", ("Antebrazo", "Abdomen", "Espalda"), "Mancuernas"
    ),
    LibraryExercise("Plancha", "core_antiextension", "Bajo", ("Abdomen",), "Peso corporal"),
    LibraryExercise("Plancha lateral", "core_antirotacion", "Bajo", ("Abdomen",), "Peso corporal"),
    LibraryExercise("Crunch", "core_flexion", "Bajo", ("Abdomen",), "Peso corporal"),
    LibraryExercise(
        "Elevación de piernas colgado", "core_flexion", "Medio", ("Abdomen",), "Peso corporal"
    ),
    LibraryExercise(
        "Rueda abdominal", "core_antiextension", "Medio", ("Abdomen",), "Rueda abdominal"
    ),
    LibraryExercise("Dead bug", "core_antiextension", "Bajo", ("Abdomen",), "Peso corporal"),
    LibraryExercise("Pallof press", "core_antirotacion", "Bajo", ("Abdomen",), "Polea"),
    LibraryExercise("Hollow hold", "core_antiextension", "Bajo", ("Abdomen",), "Peso corporal"),
    LibraryExercise(
        "Sentadilla con barra", "sentadilla", "Alto", ("Cuádriceps", "Glúteos", "Abdomen"), "Barra"
    ),
    LibraryExercise("Sentadilla frontal", "sentadilla", "Alto", ("Cuádriceps", "Abdomen"), "Barra"),
    LibraryExercise(
        "Prensa de piernas", "sentadilla", "Medio", ("Cuádriceps", "Glúteos"), "Máquina"
    ),
    LibraryExercise(
        "Zancadas con mancuernas", "sentadilla", "Medio", ("Cuádriceps", "Glúteos"), "Mancuernas"
    ),
    LibraryExercise(
        "Sentadilla búlgara", "sentadilla", "Medio", ("Cuádriceps", "Glúteos"), "Mancuernas"
    ),
    LibraryExercise("Extensión de rodilla", "aislamiento", "Bajo", ("Cuádriceps",), "Máquina"),
    LibraryExercise(
        "Subida al cajón", "sentadilla", "Medio", ("Cuádriceps", "Glúteos"), "Mancuernas"
    ),
    LibraryExercise(
        "Peso muerto rumano", "bisagra", "Alto", ("Isquiotibiales", "Glúteos", "Espalda"), "Barra"
    ),
    LibraryExercise("Curl femoral tumbado", "aislamiento", "Bajo", ("Isquiotibiales",), "Máquina"),
    LibraryExercise("Curl femoral sentado", "aislamiento", "Bajo", ("Isquiotibiales",), "Máquina"),
    LibraryExercise(
        "Buenos días", "bisagra", "Medio", ("Isquiotibiales", "Glúteos", "Espalda"), "Barra"
    ),
    LibraryExercise("Curl nórdico", "aislamiento", "Alto", ("Isquiotibiales",), "Peso corporal"),
    LibraryExercise("Hip thrust", "bisagra", "Medio", ("Glúteos", "Isquiotibiales"), "Barra"),
    LibraryExercise(
        "Puente de glúteo", "bisagra", "Bajo", ("Glúteos", "Isquiotibiales"), "Peso corporal"
    ),
    LibraryExercise("Patada de glúteo en polea", "aislamiento", "Bajo", ("Glúteos",), "Polea"),
    LibraryExercise("Abducción de cadera", "aislamiento", "Bajo", ("Glúteos",), "Máquina"),
    LibraryExercise(
        "Sentadilla sumo", "sentadilla", "Medio", ("Glúteos", "Cuádriceps"), "Mancuernas"
    ),
    LibraryExercise("Elevación de gemelos de pie", "gemelo", "Bajo", ("Gemelos",), "Máquina"),
    LibraryExercise("Elevación de gemelos sentado", "gemelo", "Bajo", ("Gemelos",), "Máquina"),
    LibraryExercise("Elevación de gemelos en prensa", "gemelo", "Bajo", ("Gemelos",), "Máquina"),
    LibraryExercise(
        "Elevación de gemelos unilateral", "gemelo", "Bajo", ("Gemelos",), "Peso corporal"
    ),
    LibraryExercise("Aductor en máquina", "aislamiento", "Bajo", ("Aductores",), "Máquina"),
    LibraryExercise(
        "Plancha Copenhague",
        "core_antirotacion",
        "Medio",
        ("Aductores", "Abdomen"),
        "Peso corporal",
    ),
    LibraryExercise(
        "Zancada lateral",
        "sentadilla",
        "Medio",
        ("Aductores", "Cuádriceps", "Glúteos"),
        "Mancuernas",
    ),
)


class Command(BaseCommand):
    help = "Crea la biblioteca de ejercicios de fuerza sin duplicar ni renombrar existentes."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Cuenta lo que se crearía sin escribir en la base.",
        )

    def handle(self, *args: object, **options: object) -> None:
        dry_run = bool(options["dry_run"])
        name = normalized_name(CLASSIFICATION)
        classification, _ = Classification.objects.get_or_create(
            nombre__iexact=name, defaults={"nombre": name}
        )
        created = 0
        skipped = 0
        for item in EXERCISES:
            canonical = normalized_name(item.nombre)
            if Exercise.objects.filter(
                nombre__iexact=canonical, classification=classification
            ).exists():
                skipped += 1
                continue
            if not dry_run:
                Exercise.objects.create(
                    nombre=canonical,
                    classification=classification,
                    patron_movimiento=item.patron,
                    musculos_principales=list(item.musculos),
                    equipo=item.equipo,
                    nivel_fatiga=item.fatiga,
                    variante="",
                    descripcion="",
                )
            created += 1
        verb = "Se crearían" if dry_run else "Se crearon"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {created} ejercicios; {skipped} ya existían en la clasificación {name}."
            )
        )
