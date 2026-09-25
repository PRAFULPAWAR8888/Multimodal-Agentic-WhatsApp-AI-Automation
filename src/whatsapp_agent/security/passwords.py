"""
Password hashing utilities using passlib with bcrypt.

Never store or log plaintext passwords. Always hash before storing.
"""
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password. Returns a bcrypt hash string."""
    return _pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)
