from django.http import JsonResponse


def list_orders(request):
    return JsonResponse([{"id": 1, "item": "book"}, {"id": 2, "item": "pen"}], safe=False)
