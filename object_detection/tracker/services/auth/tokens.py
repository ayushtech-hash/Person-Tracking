"""
Helpers for writing/clearing the httpOnly JWT cookies on a response.
Kept separate from the views so the cookie policy (names, flags, paths)
lives in exactly one place.
"""

from django.conf import settings


def set_auth_cookies(response, access_token, refresh_token=None):
    response.set_cookie(
        key=settings.AUTH_COOKIE_ACCESS,
        value=str(access_token),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path='/',
    )
    if refresh_token is not None:
        response.set_cookie(
            key=settings.AUTH_COOKIE_REFRESH,
            value=str(refresh_token),
            httponly=True,
            secure=settings.AUTH_COOKIE_SECURE,
            samesite=settings.AUTH_COOKIE_SAMESITE,
            # Scoped to the refresh endpoint only - the browser won't even
            # send this cookie on ordinary page/API requests.
            path='/api/auth/refresh/',
        )
    return response


def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path='/')
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path='/api/auth/refresh/')
    return response
