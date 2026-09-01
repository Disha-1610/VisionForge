from datetime import timedelta
import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

settings = get_settings()


def test_password_hashing():
    plain = "SecurePassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_flow():
    user_data = {"sub": "123e4567-e89b-12d3-a456-426614174000", "role": "admin"}
    
    # Access token
    access_token = create_access_token(user_data)
    decoded = decode_token(access_token)
    assert decoded["sub"] == user_data["sub"]
    assert decoded["role"] == "admin"
    assert decoded["type"] == "access"
    assert "exp" in decoded

    # Refresh token
    refresh_token = create_refresh_token(user_data)
    decoded_refresh = decode_token(refresh_token)
    assert decoded_refresh["sub"] == user_data["sub"]
    assert decoded_refresh["type"] == "refresh"


def test_jwt_expired_token():
    user_data = {"sub": "123e4567-e89b-12d3-a456-426614174000"}
    # Token expired 10 minutes ago
    expired_token = create_access_token(user_data, expires_delta=timedelta(minutes=-10))
    with pytest.raises(HTTPException) as exc_info:
        decode_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_jwt_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("invalid.token.payload")
    assert exc_info.value.status_code == 401


# â”€â”€ RBAC â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import asyncio

from app.core.security import require_roles
from app.models.user import User, UserRole


def _make_user(role: UserRole) -> User:
    return User(
        email=f"{role.value}@test.com",
        full_name="Test User",
        role=role,
        is_active=True,
    )


def test_require_roles_allows_matching_role():
    """RBAC dependency lets a user with an allowed role through and returns the user."""
    checker = require_roles(UserRole.ADMIN, UserRole.OPERATOR)
    admin = _make_user(UserRole.ADMIN)

    result = asyncio.run(checker(current_user=admin))
    assert result is admin


def test_require_roles_rejects_other_role():
    """RBAC dependency blocks a user whose role is not allowed with 403."""
    checker = require_roles(UserRole.ADMIN)
    operator = _make_user(UserRole.OPERATOR)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(checker(current_user=operator))
    assert exc_info.value.status_code == 403


def test_require_roles_no_args_allows_all():
    """require_roles() with no arguments acts as authenticated-only."""
    checker = require_roles()
    operator = _make_user(UserRole.OPERATOR)

    result = asyncio.run(checker(current_user=operator))
    assert result is operator
