from django.http import HttpResponse

class RenderHealthMiddleware:
    """
    Ensure Render health checks always succeed
    before tenant middleware runs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ["/healthz/", "/health/"]:
            return HttpResponse("OK", content_type="text/plain")

        return self.get_response(request)
