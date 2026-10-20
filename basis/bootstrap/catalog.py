"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.modules.catalog.adapters.django import (
    DjangoCatalogAuthorization,
    DjangoCatalogRepository,
)
from basis.modules.catalog.public import (
    Catalog,
)


def catalog() -> Catalog:
    return Catalog(DjangoCatalogRepository(), DjangoCatalogAuthorization(), DjangoUnitOfWork)
