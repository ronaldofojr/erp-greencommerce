"""Customer management for retail operations."""
from __future__ import annotations

from typing import Dict, List, Optional

from app import database
from app.utils import log_audit, validate_cpf


def list_customers() -> List[Dict[str, str]]:
    with database.get_connection() as conn:
        rows = conn.execute("SELECT * FROM customers ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def create_customer(name: str, cpf: Optional[str], contact: Optional[str], accepts_lgpd: bool) -> int:
    if cpf and not validate_cpf(cpf):
        raise ValueError("CPF inválido para NFC-e")
    with database.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO customers (name, cpf, contact, accepts_lgpd) VALUES (?, ?, ?, ?)",
            (name, cpf, contact, 1 if accepts_lgpd else 0),
        )
        customer_id = cursor.lastrowid
    log_audit("cliente_cadastrado", {"id": customer_id})
    return customer_id


def customer_history(customer_id: int) -> Dict[str, List[Dict[str, str]]]:
    with database.get_connection() as conn:
        customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        sales = conn.execute("SELECT * FROM sales WHERE customer_id = ?", (customer_id,)).fetchall()
    return {
        "customer": dict(customer) if customer else {},
        "sales": [dict(row) for row in sales],
    }


__all__ = ["list_customers", "create_customer", "customer_history"]
