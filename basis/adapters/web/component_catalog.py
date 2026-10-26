"""Development-only synthetic Cotton examples; no persistence or domain operations."""

from django import forms
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods


class CatalogForm(forms.Form):
    nombre = forms.CharField(label="Nombre ficticio", max_length=80)
    correo = forms.EmailField(label="Correo ficticio")


def development_only() -> None:
    if not settings.DEBUG:
        raise Http404


@never_cache
@require_http_methods(["GET", "POST"])
def catalog(request: HttpRequest) -> HttpResponse:
    development_only()
    form = CatalogForm(request.POST if request.method == "POST" else None)
    accepted = request.method == "POST" and form.is_valid()
    return render(
        request,
        "shared/component_catalog.html",
        {
            "form": form,
            "accepted": accepted,
            "variants": ("default", "primary", "subtle", "danger", "ghost", "text"),
            "sizes": ("xs", "sm", "md", "lg", "xl", "2xl"),
            "tones": ("info", "success", "warning", "error"),
            "appearances": ("soft", "solid", "outline"),
        },
    )


@never_cache
@require_GET
def fragment(request: HttpRequest) -> HttpResponse:
    development_only()
    return render(request, "shared/_component_fragment.html")
