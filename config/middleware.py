from django.http import JsonResponse


class HealthCheckMiddleware:
    """Answer kubelet probes before Django validates the Host header.

    Kubelet probes call the pod by IP (Host: 10.x.x.x). That is not in ALLOWED_HOSTS,
    so without this, Django returns 400 and the pod never becomes Ready.
    """

    PROBE_PATHS = {"/healthz", "/ready"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in self.PROBE_PATHS:
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
