"""Account and opaque bearer-session helpers for JASSIM AI.

Passwords are stored as PBKDF2-HMAC-SHA256 hashes; session secrets are random
and only their SHA-256 digests are persisted. This module never logs secrets.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

PBKDF2_ITERATIONS = 310_000
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$")


def normalize_email(value):
    email = str(value or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("invalid_email")
    return email


def hash_password(password):
    password = str(password or "")
    if len(password) < 10 or len(password) > 256:
        raise ValueError("password_length_invalid")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "pbkdf2_sha256$%d$%s$%s" % (
        PBKDF2_ITERATIONS,
        salt.hex(),
        digest.hex(),
    )


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt_hex, digest_hex = str(encoded).split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(iterations)
        if rounds < 100_000 or rounds > 2_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", str(password or "").encode("utf-8"), salt, rounds
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def _token_hash(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def create_user(db, email, password):
    email = normalize_email(email)
    password_hash = hash_password(password)
    user_id = secrets.token_hex(16)
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = db.execute(
        """INSERT INTO users(id,email_normalized,password_hash,role,created_at)
           VALUES(?,?,?,?,?) ON CONFLICT(email_normalized) DO NOTHING""",
        (user_id, email, password_hash, "user", created_at),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise ValueError("email_already_registered")
    db.commit()
    return {"id": user_id, "email": email, "role": "user"}


def issue_session(db, user_id):
    token = "jss_" + secrets.token_urlsafe(36)
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=SESSION_DAYS)).isoformat()
    db.execute(
        "INSERT INTO sessions(token_hash,user_id,created_at,expires_at,revoked_at) VALUES(?,?,?,?,NULL)",
        (_token_hash(token), user_id, now.isoformat(), expires),
    )
    db.commit()
    return token


def authenticate_session(db, token):
    token = str(token or "")
    if not token.startswith("jss_") or len(token) > 200:
        return None
    row = db.execute(
        """SELECT users.id,users.email_normalized,users.role,sessions.expires_at,sessions.revoked_at
           FROM sessions JOIN users ON users.id=sessions.user_id
           WHERE sessions.token_hash=?""",
        (_token_hash(token),),
    ).fetchone()
    if not row or row[4] is not None:
        return None
    try:
        expiry = datetime.fromisoformat(str(row[3]).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            return None
    except (TypeError, ValueError):
        return None
    return {"user_id": row[0], "email": row[1], "role": row[2], "legacy": False}


def revoke_session(db, token):
    token = str(token or "")
    if not token.startswith("jss_") or len(token) > 200:
        return False
    cursor = db.execute(
        "UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
        (datetime.now(timezone.utc).isoformat(), _token_hash(token)),
    )
    db.commit()
    return cursor.rowcount > 0


def find_user_by_email(db, email):
    email = normalize_email(email)
    return db.execute(
        "SELECT id,email_normalized,password_hash,role FROM users WHERE email_normalized=?",
        (email,),
    ).fetchone()
