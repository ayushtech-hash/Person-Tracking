"""
Registration / login business logic, independent of DRF or HTTP.
api_views.py calls into this; this module never touches request/response
objects directly, so it stays easy to unit test.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class AuthError(Exception):
    """Raised for any expected auth failure (bad password, dup username, etc).
    `field` lets the API view attach the error to a specific form field."""

    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)


def register_user(username, email, password, password_confirm):
    username = (username or '').strip()
    email = (email or '').strip()

    if not username or not password:
        raise AuthError('Username and password are required.')

    if password != password_confirm:
        raise AuthError('Passwords do not match.', field='password_confirm')

    if User.objects.filter(username__iexact=username).exists():
        raise AuthError('That username is already taken.', field='username')

    if email and User.objects.filter(email__iexact=email).exists():
        raise AuthError('That email is already registered.', field='email')

    try:
        validate_password(password)
    except ValidationError as exc:
        raise AuthError(' '.join(exc.messages), field='password')

    return User.objects.create_user(username=username, email=email, password=password)


def authenticate_user(username, password):
    user = authenticate(username=username, password=password)
    if user is None:
        raise AuthError('Invalid username or password.')
    if not user.is_active:
        raise AuthError('This account has been disabled.')
    return user
