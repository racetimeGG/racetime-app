from django.middleware.csrf import (
    CsrfViewMiddleware,
    REASON_NO_CSRF_COOKIE,
    REASON_BAD_TOKEN,
    _compare_salted_tokens,
    _sanitize_token,
)


class CsrfViewMiddlewareTwitch(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        referer = request.META.get('HTTP_REFERER')

        csrf_token = request.META.get('CSRF_COOKIE')
        if csrf_token is None:
            return self._reject(request, REASON_NO_CSRF_COOKIE)

        request_csrf_token = request.GET.get('state', '')
        request_csrf_token = _sanitize_token(request_csrf_token)
        if not _compare_salted_tokens(request_csrf_token, csrf_token):
            return self._reject(request, REASON_BAD_TOKEN)

        return self._accept(request)
