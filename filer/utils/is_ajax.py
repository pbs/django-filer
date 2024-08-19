def is_ajax(request):
    """Checks if a request is ajax."""
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'
