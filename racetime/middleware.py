from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from django.middleware import csrf


class CsrfViewMiddlewareTwitch(csrf.CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        try:
            csrf_secret = self._get_secret(request)
        except csrf.InvalidTokenFormat as exc:
            return self._reject(request, f'CSRF cookie {exc.reason}.')

        request_csrf_token = request.GET.get('state', '')

        try:
            csrf._check_token_format(request_csrf_token)
        except csrf.InvalidTokenFormat as exc:
            return self._reject(request, f'CSRF token {exc.reason}.')

        if not csrf._does_token_match(request_csrf_token, csrf_secret):
            self._reject(request, 'CSRF token incorrect.')

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

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope['oauth_token'] = (
            self.get_token_from_header(scope)
            or self.get_token_from_query(scope)
            or None
        )
        return await self.inner(scope, receive, send)
