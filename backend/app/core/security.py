from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# ── Password Hashing Context ──────────────────────────────────────────────────
# Passlib CryptContext configuration.
# Primary scheme is Argon2 for modern memory-hard password hashing, with bcrypt as fallback.
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto"
)

# ── OAuth2 Token Scheme ───────────────────────────────────────────────────────
# FastAPI ka standard OAuth2 password bearer scheme token extraction ke liye.
# tokenUrl endpoint setting FastAPI docs (Swagger UI) mein authorize button ke liye use hota hai.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"/api/{settings.API_VERSION}/auth/login",
    auto_error=False
)


# ── Password Utilities ───────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Hashes a plain text password using Argon2/bcrypt.
    
    Args:
        password: Plain text password string.
        
    Returns:
        Hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against a stored hashed password.
    
    Args:
        plain_password: User entered plain text password.
        hashed_password: Stored database hash.
        
    Returns:
        True if password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Token Utilities ───────────────────────────────────────────────────────

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a signed JWT access token for user authentication.
    
    Args:
        data: Dictionary of claims to embed in the token (e.g., {"sub": user_id, "role": "admin"}).
        expires_delta: Optional custom expiry duration.
        
    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()

    # Timezone-aware UTC current time
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    # Standard JWT claims:
    # "exp": expiration timestamp
    # "iat": issued at timestamp
    # "type": token category ("access")
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a signed JWT refresh token for renewing access tokens.
    
    Args:
        data: Dictionary of claims to embed in the token.
        expires_delta: Optional custom expiry duration.
        
    Returns:
        Encoded JWT refresh token string.
    """
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token string.
    
    Args:
        token: JWT string to verify and decode.
        
    Returns:
        Decoded claims dictionary.
        
    Raises:
        UnauthorizedError: If token is invalid, expired, or corrupted.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        # Invalid signature, token expired, ya tampered payload hone par custom UnauthorizedError raise karo
        raise UnauthorizedError(
            message="Could not validate credentials or token expired",
            code="INVALID_TOKEN",
            details=str(e)
        )


def get_current_user_id(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency that extracts and validates user_id (subject claim) from bearer token.
    
    Args:
        token: Bearer token extracted from Authorization header.
        
    Returns:
        User ID string (sub claim).
        
    Raises:
        UnauthorizedError: If Authorization header missing or token is invalid/expired.
    """
    if not token:
        raise UnauthorizedError(
            message="Authentication token is missing",
            code="MISSING_TOKEN"
        )

    payload = decode_token(token)

    # Token category verify karo (access token hona chahiye, refresh token nahi)
    token_type = payload.get("type")
    if token_type != "access":
        raise UnauthorizedError(
            message="Invalid token type for API access",
            code="INVALID_TOKEN_TYPE"
        )

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(
            message="Token subject claim is missing",
            code="MALFORMED_TOKEN"
        )

    return user_id
