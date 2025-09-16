"""Restaurant order and table management."""
from __future__ import annotations

from typing import Dict, List, Optional

from app import database
from app.utils import current_timestamp, log_audit


def create_table(name: str) -> int:
    with database.get_connection() as conn:
        cursor = conn.execute("INSERT INTO tables (name, status) VALUES (?, 'livre')", (name,))
        table_id = cursor.lastrowid
    log_audit("mesa_criada", {"table_id": table_id})
    return table_id


def list_tables() -> List[Dict[str, str]]:
    with database.get_connection() as conn:
        rows = conn.execute("SELECT * FROM tables ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def open_comanda(table_id: Optional[int], notes: Optional[str] = None) -> int:
    with database.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO comandas (table_id, status, opened_at, total) VALUES (?, 'aberta', ?, 0)",
            (table_id, current_timestamp()),
        )
        comanda_id = cursor.lastrowid
        if table_id:
            conn.execute("UPDATE tables SET status = 'ocupada', opened_at = ? WHERE id = ?", (current_timestamp(), table_id))
    log_audit("comanda_aberta", {"comanda_id": comanda_id, "mesa": table_id})
    return comanda_id


def add_order(comanda_id: int, items: List[Dict[str, str]], source: str = "local", external_id: Optional[str] = None) -> int:
    with database.get_connection() as conn:
        comanda = conn.execute("SELECT * FROM comandas WHERE id = ?", (comanda_id,)).fetchone()
        cursor = conn.execute(
            "INSERT INTO orders (external_id, source, status, table_id, comanda_id, created_at) VALUES (?, ?, 'recebido', ?, ?, ?)",
            (
                external_id,
                source,
                comanda["table_id"] if comanda else None,
                comanda_id,
                current_timestamp(),
            ),
        )
        order_id = cursor.lastrowid
        for item in items:
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, description, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                (
                    order_id,
                    item.get("product_id"),
                    item.get("description"),
                    item.get("quantity"),
                    item.get("unit_price"),
                ),
            )
        conn.execute(
            "UPDATE comandas SET total = total + ? WHERE id = ?",
            (sum(float(item.get("unit_price", 0)) * int(item.get("quantity", 0)) for item in items), comanda_id),
        )
    log_audit("pedido_registrado", {"comanda_id": comanda_id, "order_id": order_id, "source": source})
    return order_id


def update_order_status(order_id: int, status: str) -> None:
    with database.get_connection() as conn:
        conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (status, current_timestamp(), order_id))
    log_audit("pedido_status", {"order_id": order_id, "status": status})


def close_comanda(comanda_id: int) -> None:
    with database.get_connection() as conn:
        comanda = conn.execute("SELECT * FROM comandas WHERE id = ?", (comanda_id,)).fetchone()
        if not comanda:
            raise ValueError("Comanda inexistente")
        conn.execute(
            "UPDATE comandas SET status = 'fechada', closed_at = ? WHERE id = ?",
            (current_timestamp(), comanda_id),
        )
        if comanda["table_id"]:
            conn.execute("UPDATE tables SET status = 'livre', closed_at = ? WHERE id = ?", (current_timestamp(), comanda["table_id"]))
    log_audit("comanda_fechada", {"comanda_id": comanda_id})


def import_ifood_order(payload: Dict[str, str]) -> Dict[str, str]:
    """Mock integration with iFood API generating NFC-e automatically."""
    comanda_id = open_comanda(None, notes="Pedido iFood")
    items = payload.get("items", [])
    order_id = add_order(
        comanda_id,
        items,
        source="ifood",
        external_id=payload.get("order_id"),
    )
    log_audit("ifood_importado", {"order_id": payload.get("order_id")})
    return {"comanda_id": comanda_id, "order_id": order_id}


__all__ = [
    "create_table",
    "list_tables",
    "open_comanda",
    "add_order",
    "update_order_status",
    "close_comanda",
    "import_ifood_order",
]
