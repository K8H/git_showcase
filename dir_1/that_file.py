from django.http import JsonResponse
from utils.fuel_consumption import fuel_consumption_prediction

def fuel_consumption(request):
    print(request.body)
    result = fuel_consumption_prediction(
        request.POST.get('slat'),
        request.POST.get('slon'),
        request.POST.get('elat'),
        request.POST.get('elon'),
        request.POST.get('weight'),
        request.POST.get('dept_time')
    )

    return JsonResponse(result, safe=False)
