"""
Protects normal Django template views (e.g. your existing upload page)
using the same JWT cookie the API uses - so you don't need Django's
session-based @login_required for page views.

Usage:
    from tracker.services.auth.decorators import jwt_login_required

    @jwt_login_required
    def upload_view(request):
        ...  # request.user is set
"""

from functools import wraps
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import redirect
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .tokens import set_auth_cookies


def jwt_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)

        if raw_token:
            try:
                token = AccessToken(raw_token)
                request.user = User.objects.get(pk=token['user_id'])
                return view_func(request, *args, **kwargs)
            except (TokenError, User.DoesNotExist):
                pass

        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw_refresh:
            try:
                refresh = RefreshToken(raw_refresh)
                access = refresh.access_token
                request.user = User.objects.get(pk=access['user_id'])
                response = view_func(request, *args, **kwargs)
                return set_auth_cookies(response, access)
            except (TokenError, User.DoesNotExist):
                pass

        return redirect(f'/login/?next={quote(request.path)}')

    return wrapped
