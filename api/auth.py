import os
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

_SECRET = os.getenv("JWT_SECRET_KEY", "")
_ALGO = "HS256"
_EXPIRE_DAYS = 30

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


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
