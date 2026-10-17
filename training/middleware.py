class PrivateResponsesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(("/static/", "/manifest.webmanifest", "/service-worker.js")):
            response["Cache-Control"] = "private, no-store"
            response["Vary"] = "Cookie, HX-Request"
        return response

    def process_exception(self, request, exception):
        from django.core.exceptions import ValidationError
        from django.shortcuts import render
        from rest_framework.exceptions import PermissionDenied

        from .services import Conflict

        if isinstance(exception, (ValidationError, PermissionDenied, Conflict)):
            text = "El registro cambió. Recarga la página para revisar la versión actual."
            if isinstance(exception, ValidationError):
                text = " ".join(exception.messages)
            elif isinstance(exception, PermissionDenied):
                text = str(exception.detail)
            status = (
                403
                if isinstance(exception, PermissionDenied)
                else 409
                if isinstance(exception, Conflict)
                else 400
            )
            return render(
                request,
                "training/notice.html",
                {"title": "Revisa el registro", "text": text},
                status=status,
            )
