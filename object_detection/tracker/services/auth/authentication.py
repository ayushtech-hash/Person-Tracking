"""
Cookie-based JWT authentication.

Standard SimpleJWT expects the access token in an `Authorization: Bearer <token>`
header, which means client-side JS has to hold the raw token (usually in
localStorage) and attach it manually. Since we're serving a browser UI and
want the token in an httpOnly cookie instead, this class:

  1. Still checks the Authorization header first (so the API also works
     for non-browser clients / tools like Postman / mobile apps later), then
  2. Falls back to the `access_token` httpOnly cookie set by LoginAPIView /
     RegisterAPIView (see tokens.py).
"""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = self.get_raw_token(header) if header is not None else None

        if raw_token is None:
            raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
