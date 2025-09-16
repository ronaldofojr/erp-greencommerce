"""Authentication and authorization helpers."""
from __future__ import annotations

from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash

from app import database
from app.utils import log_audit


def create_user(username: str, password: str, role: str = "caixa", email: str | None = None) -> int:
    with database.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, email),
        )
        user_id = cursor.lastrowid
    log_audit("usuario_criado", {"id": user_id, "role": role})
    return user_id


def authenticate(username: str, password: str) -> Optional[dict]:
    with database.get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        log_audit("login_sucesso", {"username": username})
        return dict(row)
    log_audit("login_falha", {"username": username})
    return None


def has_role(user: dict, allowed_roles: set[str]) -> bool:
    return user.get("role") in allowed_roles


__all__ = ["create_user", "authenticate", "has_role"]
