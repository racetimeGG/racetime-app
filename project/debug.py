def show_toolbar(request):
    return bool(request.GET.get('debug'))
