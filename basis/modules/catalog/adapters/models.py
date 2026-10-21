from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db import NotSupportedError, connections, models, router, transaction
from django.db.models.base import ModelBase
from django.utils.translation import gettext_lazy as _

from basis.adapters.django.persistence import ValidatedModel
from basis.modules.catalog.public import valid_muscle_names
from basis.shared.text import normalized_name as normalize_text


@contextmanager
def _serialize_catalog_writes(using: str, table_name: str, primary_key: str) -> Iterator[None]:
    """Database-owned serialization, including an empty catalog and new rows."""
    with transaction.atomic(using=using):
        connection = connections[using]
        table = connection.ops.quote_name(table_name)
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                # Self-conflicting, transaction-scoped table lock. Locking only
                # the edited row cannot protect edges on different exercises.
                cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
            elif connection.vendor == "sqlite":
                # SQLite has no SELECT FOR UPDATE/table-lock clause. A real
                # write statement reserves its database writer before reads,
                # even if the catalog is empty. A stale outer read transaction
                # may fail SQLITE_BUSY; never retry/bypass validation here.
                pk = connection.ops.quote_name(primary_key)
                cursor.execute(f"UPDATE {table} SET {pk} = {pk} WHERE 0")
            else:
                raise NotSupportedError("Catalog writes require PostgreSQL or SQLite.")
        yield


class Classification(ValidatedModel):
    nombre = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))

    def clean(self) -> None:
        """Normaliza y limpia el nombre antes de guardarlo."""
        self.nombre = normalize_text(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Indica un nombre."})

    def __str__(self) -> str:
        return self.nombre

    class Meta:
        verbose_name = _("Classification")
        verbose_name_plural = _("Classifications")


class Exercise(models.Model):
    _lineage_parents: dict[int, int | None] | None = None

    patron_movimiento = models.CharField(max_length=100, blank=True)
    musculos_principales = models.JSONField(default=list, blank=True)
    equipo = models.CharField(max_length=300, blank=True)
    variante = models.CharField(max_length=150, blank=True)
    variante_de = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="variantes",
        verbose_name=_("Variante de"),
        help_text="Ejercicio de origen; no transfiere prescripciones, cargas ni RM.",
    )
    archivado = models.BooleanField(default=False)
    NIVEL_FATIGA_CHOICES = [
        ("Bajo", _("Low")),
        ("Medio", _("Medium")),
        ("Alto", _("High")),
    ]

    nombre = models.CharField(max_length=255, verbose_name=_("Name"))
    video = models.URLField(blank=True, null=True, verbose_name=_("Video"))
    descripcion = models.TextField(blank=True, verbose_name=_("Description"))
    classification = models.ForeignKey(
        Classification, on_delete=models.PROTECT, verbose_name=_("Classification")
    )
    nivel_fatiga = models.CharField(
        max_length=10,
        choices=NIVEL_FATIGA_CHOICES,
        default="Medio",
        verbose_name=_("Fatigue Level"),
    )

    def clean(self) -> None:
        self.nombre = normalize_text(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Indica un nombre."})

        if not valid_muscle_names(self.musculos_principales):
            raise ValidationError({"musculos_principales": "Usa una lista de nombres musculares."})

        # Archived ancestors remain valid historical identities. A family must
        # never point back to itself, even through several intermediate variants.
        ancestor = self.variante_de_id
        parents = self._lineage_parents
        if ancestor is not None and parents is None:
            using = self._state.db or router.db_for_write(type(self), instance=self)
            parents = dict(Exercise.objects.using(using).values_list("pk", "variante_de_id"))
        visited = {self.pk} if self.pk is not None else set()
        while ancestor is not None:
            if ancestor in visited:
                raise ValidationError(
                    {"variante_de": "La filiación de variantes no admite ciclos."}
                )
            visited.add(ancestor)
            assert parents is not None
            ancestor = parents.get(ancestor)

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        using = using or router.db_for_write(type(self), instance=self)
        previous_database = self._state.db
        pk = self._meta.pk
        assert pk is not None and pk.column is not None
        try:
            with _serialize_catalog_writes(using, self._meta.db_table, pk.column):
                # Route FK validation and lineage reads to the same database as
                # the write/lock, including save(using=...) on an unsaved row.
                self._state.db = using
                if self.variante_de_id is not None:
                    rows = Exercise.objects.using(using)
                    if connections[using].vendor == "postgresql":
                        # At stronger snapshot isolation this fails closed if a
                        # row changed since the outer transaction's snapshot;
                        # it must not validate against a stale pre-lock graph.
                        rows = rows.select_for_update()
                    self._lineage_parents = dict(rows.values_list("pk", "variante_de_id"))
                self.full_clean()
                super().save(
                    force_insert=force_insert,
                    force_update=force_update,
                    using=using,
                    update_fields=update_fields,
                )
        except Exception:
            self._state.db = previous_database
            raise
        finally:
            self._lineage_parents = None

    def __str__(self) -> str:
        return self.nombre

    class Meta:
        verbose_name = _("Exercise")
        verbose_name_plural = _("Exercises")
