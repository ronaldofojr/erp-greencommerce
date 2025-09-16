"""PDV (Point of Sale) module integrating inventory, sales and NFC-e."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import database, estoque
from app.utils import current_timestamp, log_audit

SessionDict = Dict[str, Any]
ItemDict = Dict[str, Any]


def get_session(session_id: int) -> Optional[SessionDict]:
    """Return a PDV session by ID."""
    with database.get_connection() as conn:
        row = conn.execute("SELECT * FROM pdv_sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None


def create_session(user_id: Optional[int] = None) -> SessionDict:
    """Create a new PDV session for the informed user."""
    with database.get_connection() as conn:
        cursor = conn.execute("INSERT INTO pdv_sessions (user_id) VALUES (?)", (user_id,))
        session_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM pdv_sessions WHERE id = ?", (session_id,)).fetchone()
    log_audit("pdv_sessao_criada", {"session_id": session_id, "user_id": user_id})
    return dict(row)


def get_or_create_session(user_id: Optional[int] = None, session_id: Optional[int] = None) -> SessionDict:
    """Return an existing open session or create a new one."""
    if session_id:
        session_data = get_session(session_id)
        if session_data:
            return session_data
    if user_id:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pdv_sessions WHERE user_id = ? AND status = 'aberta' ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        if row:
            return dict(row)
    return create_session(user_id)


def list_session_items(session_id: int) -> List[ItemDict]:
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, session_id, product_id, product_code, product_name, quantity, unit_price, discount, total
            FROM pdv_session_items
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        )
        items = [dict(row) for row in cursor.fetchall()]
    for item in items:
        item["quantity"] = int(item["quantity"])
        item["unit_price"] = float(item["unit_price"])
        item["discount"] = float(item.get("discount") or 0)
        item["total"] = float(item["total"])
    return items


def _update_totals_for_item(quantity: int, unit_price: float, discount: float) -> float:
    total = round(quantity * unit_price - discount, 2)
    if total < 0:
        raise ValueError("Desconto não pode exceder o valor do item")
    return total


def add_item_by_code(
    session_id: int,
    product_code: str,
    quantity: int = 1,
    discount: Optional[float] = None,
) -> ItemDict:
    """Add an item to the PDV session using the product code."""
    if quantity <= 0:
        raise ValueError("Quantidade deve ser positiva")
    product = estoque.get_product_by_code(product_code)
    if not product:
        raise ValueError("Produto não encontrado")
    unit_price = float(product.get("price", 0))
    discount_value = float(discount) if discount is not None else 0.0
    with database.get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM pdv_session_items WHERE session_id = ? AND product_id = ?",
            (session_id, product["id"]),
        ).fetchone()
        if existing:
            new_quantity = int(existing["quantity"]) + quantity
            discount_value = float(existing["discount"] or 0) if discount is None else float(discount)
            total = _update_totals_for_item(new_quantity, unit_price, discount_value)
            conn.execute(
                """
                UPDATE pdv_session_items
                SET quantity = ?, discount = ?, total = ?, unit_price = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_quantity, discount_value, total, unit_price, current_timestamp(), existing["id"]),
            )
            item_id = existing["id"]
        else:
            total = _update_totals_for_item(quantity, unit_price, discount_value)
            cursor = conn.execute(
                """
                INSERT INTO pdv_session_items
                    (session_id, product_id, product_code, product_name, quantity, unit_price, discount, total, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    product["id"],
                    product.get("code"),
                    product.get("name"),
                    quantity,
                    unit_price,
                    discount_value,
                    total,
                    current_timestamp(),
                ),
            )
            item_id = cursor.lastrowid
    log_audit(
        "pdv_item_adicionado",
        {"session_id": session_id, "product_id": product["id"], "quantity": quantity, "item_id": item_id},
    )
    items = list_session_items(session_id)
    return next(item for item in items if item["id"] == item_id)


def update_item(session_id: int, item_id: int, quantity: int, discount: Optional[float] = None) -> ItemDict:
    if quantity <= 0:
        raise ValueError("Quantidade deve ser positiva")
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pdv_session_items WHERE id = ? AND session_id = ?",
            (item_id, session_id),
        ).fetchone()
        if not row:
            raise ValueError("Item não encontrado")
        unit_price = float(row["unit_price"])
        discount_value = float(discount) if discount is not None else float(row["discount"] or 0)
        total = _update_totals_for_item(quantity, unit_price, discount_value)
        conn.execute(
            """
            UPDATE pdv_session_items
            SET quantity = ?, discount = ?, total = ?, updated_at = ?
            WHERE id = ?
            """,
            (quantity, discount_value, total, current_timestamp(), item_id),
        )
    log_audit("pdv_item_atualizado", {"session_id": session_id, "item_id": item_id})
    items = list_session_items(session_id)
    return next(item for item in items if item["id"] == item_id)


def remove_item(session_id: int, item_id: int) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "DELETE FROM pdv_session_items WHERE id = ? AND session_id = ?",
            (item_id, session_id),
        )
    log_audit("pdv_item_removido", {"session_id": session_id, "item_id": item_id})


def calculate_totals(session_id: int) -> Dict[str, float]:
    items = list_session_items(session_id)
    subtotal = round(sum(item["quantity"] * item["unit_price"] for item in items), 2)
    discount = round(sum(item.get("discount", 0.0) for item in items), 2)
    total = round(sum(item["total"] for item in items), 2)
    quantity_total = sum(item["quantity"] for item in items)
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE pdv_sessions SET total = ?, discount = ?, updated_at = ? WHERE id = ?",
            (total, discount, current_timestamp(), session_id),
        )
    return {
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "items": len(items),
        "quantity": quantity_total,
    }


def prepare_sale_items(session_id: int) -> List[Dict[str, float]]:
    items = list_session_items(session_id)
    sale_items: List[Dict[str, float]] = []
    for item in items:
        quantity = item["quantity"]
        if quantity <= 0:
            continue
        unit_price = round(item["total"] / quantity, 2)
        sale_items.append(
            {
                "product_id": item["product_id"],
                "quantity": quantity,
                "unit_price": unit_price,
            }
        )
    return sale_items


def finalize_session(session_id: int, sale_id: int, payment_method: str) -> Dict[str, float]:
    totals = calculate_totals(session_id)
    with database.get_connection() as conn:
        conn.execute(
            """
            UPDATE pdv_sessions
            SET status = 'finalizada', sale_id = ?, payment_method = ?, closed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (sale_id, payment_method, current_timestamp(), current_timestamp(), session_id),
        )
    log_audit("pdv_sessao_finalizada", {"session_id": session_id, "sale_id": sale_id})
    return totals


def session_payload(session_id: int) -> Dict[str, Any]:
    session_data = get_session(session_id)
    items = list_session_items(session_id)
    totals = calculate_totals(session_id)
    return {
        "session_id": session_id,
        "session": session_data,
        "items": items,
        "totals": totals,
    }


__all__ = [
    "get_session",
    "create_session",
    "get_or_create_session",
    "list_session_items",
    "add_item_by_code",
    "update_item",
    "remove_item",
    "calculate_totals",
    "prepare_sale_items",
    "finalize_session",
    "session_payload",
]
