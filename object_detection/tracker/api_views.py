"""
Thin DRF views for the JWT auth API. All actual logic lives in
tracker/services/auth/ - these views just translate HTTP <-> service calls.

Endpoints (see urls.py):
    POST /api/auth/register/
    POST /api/auth/login/
    POST /api/auth/logout/
    POST /api/auth/refresh/
    GET  /api/auth/me/
"""

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .services.auth.auth_service import AuthError, authenticate_user, register_user
from .services.auth.tokens import clear_auth_cookies, set_auth_cookies

# These endpoints are stateless (JWT-in-cookie, not Django session auth), so
# Django's session-based CSRF check doesn't apply to them the way it does to
# normal form posts - hence csrf_exempt here. Note this is *not* the same as
# disabling CSRF site-wide; your other session/form-based views are untouched.


@method_decorator(csrf_exempt, name='dispatch')
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = register_user(
                username=data['username'],
                email=data.get('email', ''),
                password=data['password'],
                password_confirm=data['password_confirm'],
            )
        except AuthError as exc:
            return Response({'field': exc.field, 'detail': exc.message}, status=400)

        refresh = RefreshToken.for_user(user)
        response = Response({'user': UserSerializer(user).data}, status=201)
        return set_auth_cookies(response, refresh.access_token, refresh)


@method_decorator(csrf_exempt, name='dispatch')
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = authenticate_user(data['username'], data['password'])
        except AuthError as exc:
            return Response({'detail': exc.message}, status=401)

        refresh = RefreshToken.for_user(user)
        response = Response({'user': UserSerializer(user).data}, status=200)
        return set_auth_cookies(response, refresh.access_token, refresh)


@method_decorator(csrf_exempt, name='dispatch')
class RefreshAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw_refresh:
            return Response({'detail': 'No refresh token.'}, status=401)

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError:
            return Response({'detail': 'Refresh token invalid or expired.'}, status=401)

        response = Response({'detail': 'Token refreshed.'}, status=200)
        return set_auth_cookies(response, refresh.access_token, refresh)


@method_decorator(csrf_exempt, name='dispatch')
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # already invalid/expired - fine, we're logging out anyway

        response = Response({'detail': 'Logged out.'}, status=200)
        return clear_auth_cookies(response)


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
