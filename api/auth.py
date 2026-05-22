import os
import bcrypt
import jwt
from datetime import datetime, timedelta

_SECRET = os.getenv("JWT_SECRET_KEY", "fundguldasta-dev-secret-change-in-prod")
_ALGO = "HS256"
_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """Hash a password using bcrypt. Returns a UTF-8 string for storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def decode_token(token: str) -> dict:
    """Decode and return payload. Raises jwt.PyJWTError on invalid/expired."""
    return jwt.decode(token, _SECRET, algorithms=[_ALGO])
