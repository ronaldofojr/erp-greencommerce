"""Inventory management module."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from app import database
from app.utils import current_timestamp, log_audit


Product = Dict[str, Optional[str]]


def list_products() -> List[Product]:
    """Return all products registered in the database."""
    with database.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM products ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]


def get_product(product_id: int) -> Optional[Product]:
    with database.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_product(data: Dict[str, Optional[str]]) -> int:
    """Insert a new product and return its ID."""
    required_fields = ["name", "code", "price", "quantity"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Campo obrigatório ausente: {field}")

    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO products (name, code, price, quantity, category, ncm, cest, cfop, icms_aliquota, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["code"],
                float(data.get("price", 0)),
                int(data.get("quantity", 0)),
                data.get("category"),
                data.get("ncm"),
                data.get("cest"),
                data.get("cfop"),
                data.get("icms_aliquota"),
                current_timestamp(),
            ),
        )
        product_id = cursor.lastrowid
        log_audit("produto_cadastrado", {"product_id": product_id, "code": data["code"]})
        return product_id


def update_product(product_id: int, updates: Dict[str, Optional[str]]) -> None:
    """Update product fields dynamically."""
    allowed_fields = {
        "name",
        "code",
        "price",
        "quantity",
        "category",
        "ncm",
        "cest",
        "cfop",
        "icms_aliquota",
    }
    fields: List[str] = []
    values: List[Optional[str]] = []
    for key, value in updates.items():
        if key in allowed_fields:
            fields.append(f"{key} = ?")
            values.append(value)
    if not fields:
        return
    values.append(current_timestamp())
    values.append(product_id)

    with database.get_connection() as conn:
        conn.execute(
            f"UPDATE products SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
            tuple(values),
        )
    log_audit("produto_atualizado", {"product_id": product_id})


def update_stock(product_id: int, quantity_change: int, reason: str) -> None:
    """Adjust stock for a product."""
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE products SET quantity = quantity + ?, updated_at = ? WHERE id = ?",
            (quantity_change, current_timestamp(), product_id),
        )
        conn.execute(
            "INSERT INTO inventory_movements (product_id, change, reason) VALUES (?, ?, ?)",
            (product_id, quantity_change, reason),
        )
    log_audit(
        "estoque_ajustado",
        {"product_id": product_id, "change": quantity_change, "reason": reason},
    )


def low_stock_alerts(threshold: int = 10) -> Iterable[Product]:
    """Return products below the provided quantity threshold."""
    with database.get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM products WHERE quantity < ? ORDER BY quantity",
            (threshold,),
        )
        return [dict(row) for row in cursor.fetchall()]


__all__ = [
    "list_products",
    "get_product",
    "create_product",
    "update_product",
    "update_stock",
    "low_stock_alerts",
]
