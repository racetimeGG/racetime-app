from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
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


class OAuth2TokenMiddleware(BaseMiddleware):
    """
    OAuth2 middleware for ASGI.
    """
    @staticmethod
    def get_token_from_header(scope):
        """
        Try and retrieve a bearer token from the Authorization header.
        """
        for name, value in scope['headers']:
            try:
                auth_type, token = value.decode().split(' ', 1)
            except ValueError:
                pass
            else:
                if name == b'authorization' and auth_type == 'Bearer':
                    return token
        return None

    @staticmethod
    def get_token_from_query(scope):
        """
        Try and retrieve a bearer token from the query string.

        This is less secure, but the JavaScript WebSockets API doesn't allow
        you to set HTTP headers. JavaScript is stupid.
        """
        qs = parse_qs(scope.get('query_string', b'').decode())
        if qs.get('token'):
            return qs.get('token')[0]
        return None

    def populate_scope(self, scope):
        scope['oauth_token'] = (
            self.get_token_from_header(scope)
            or self.get_token_from_query(scope)
            or None
        )

    async def resolve_scope(self, scope):
        pass
