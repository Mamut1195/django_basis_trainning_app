"""Catalog values and access policy."""

from dataclasses import dataclass

from basis.shared.identifiers import ClassificationId


class CatalogDenied(Exception):
    pass


@dataclass(frozen=True)
class ClassificationData:
    nombre: str


@dataclass(frozen=True)
class ExerciseData:
    classification: ClassificationId
    nombre: str
    video: str | None
    descripcion: str
    nivel_fatiga: str
    patron_movimiento: str
    musculos_principales: tuple[str, ...]
    equipo: str
    variante: str
    archivado: bool


def catalog_allowed(authenticated: bool, staff: bool, read_only: bool) -> bool:
    return authenticated and (read_only or staff)


def valid_muscle_names(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= 30
        and all(isinstance(name, str) and len(name) <= 80 for name in value)
    )


class InvalidCatalogData(Exception):
    field = "musculos_principales"


def validate_exercise(data: ExerciseData) -> None:
    if not valid_muscle_names(list(data.musculos_principales)):
        raise InvalidCatalogData("Usa una lista de nombres musculares.")
