"""
Password hashing utilities using bcrypt.

Never store or log plaintext passwords. Always hash before storing.
"""
import bcrypt

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password. Returns a bcrypt hash string."""
    pw_bytes = plain_password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not hashed_password or not plain_password:
        return False
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False
