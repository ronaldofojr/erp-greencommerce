"""Sales and POS logic."""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple

from app import database
from app import estoque
from app.utils import current_timestamp, log_audit

SaleItemInput = Dict[str, float]

PROMOTION_THRESHOLD = 100.0
PROMOTION_PERCENTAGE = 0.10


class PromotionResult(Tuple[float, float]):
    pass


def apply_promotions(subtotal: float) -> PromotionResult:
    """Return discount and total based on automatic promotion rules."""
    if subtotal >= PROMOTION_THRESHOLD:
        discount = round(subtotal * PROMOTION_PERCENTAGE, 2)
    else:
        discount = 0.0
    total = round(subtotal - discount, 2)
    return PromotionResult((discount, total))


def register_sale(
    items: Iterable[SaleItemInput],
    payment_method: str,
    customer_id: Optional[int] = None,
    table_id: Optional[int] = None,
    channel: str = "pdv",
) -> int:
    """Register a sale, apply promotions and update inventory."""
    subtotal = 0.0
    normalized_items: List[SaleItemInput] = []
    for item in items:
        quantity = int(item.get("quantity", 0))
        price = float(item.get("unit_price", 0))
        subtotal += quantity * price
        normalized_items.append({
            "product_id": int(item["product_id"]),
            "quantity": quantity,
            "unit_price": price,
            "total_price": quantity * price,
        })

    discount, total = apply_promotions(subtotal)
    average_ticket = total  # For MVP we consider single sale equals ticket value

    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sales (status, total, discount, payment_method, channel, average_ticket, customer_id, table_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "autorizada" if payment_method != "pendente" else "pendente",
                total,
                discount,
                payment_method,
                channel,
                average_ticket,
                customer_id,
                table_id,
            ),
        )
        sale_id = cursor.lastrowid

        for item in normalized_items:
            conn.execute(
                """
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    sale_id,
                    item["product_id"],
                    item["quantity"],
                    item["unit_price"],
                    item["total_price"],
                ),
            )
            estoque.update_stock(item["product_id"], -item["quantity"], f"Venda #{sale_id}")

        conn.execute(
            "INSERT INTO payments (sale_id, method, amount, status) VALUES (?, ?, ?, ?)",
            (
                sale_id,
                payment_method,
                total,
                "pago" if payment_method in {"dinheiro", "cartao", "pix"} else "pendente",
            ),
        )

    log_audit(
        "venda_registrada",
        {"sale_id": sale_id, "payment_method": payment_method, "total": total},
    )
    return sale_id


def list_sales(limit: int = 50) -> List[Dict[str, Optional[str]]]:
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT s.*, c.name AS customer_name FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            ORDER BY s.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def sale_details(sale_id: int) -> Dict[str, List[Dict[str, Optional[str]]]]:
    with database.get_connection() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        items = conn.execute(
            "SELECT si.*, p.name FROM sale_items si JOIN products p ON p.id = si.product_id WHERE sale_id = ?",
            (sale_id,),
        ).fetchall()
        payments = conn.execute(
            "SELECT * FROM payments WHERE sale_id = ?",
            (sale_id,),
        ).fetchall()
    return {
        "sale": dict(sale) if sale else {},
        "items": [dict(row) for row in items],
        "payments": [dict(row) for row in payments],
    }


def daily_sales_summary(target_date: Optional[date] = None) -> Dict[str, float]:
    """Return aggregated sales data for dashboards."""
    target_date = target_date or date.today()
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date, datetime.max.time())
    with database.get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS quantidade,
                COALESCE(SUM(total), 0) AS faturamento,
                COALESCE(AVG(average_ticket), 0) AS ticket_medio
            FROM sales
            WHERE created_at BETWEEN ? AND ?
        """,
            (start.isoformat(), end.isoformat()),
        ).fetchone()
    return dict(row) if row else {"quantidade": 0, "faturamento": 0.0, "ticket_medio": 0.0}


def top_products(limit: int = 5) -> List[Dict[str, Optional[str]]]:
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT p.name, SUM(si.quantity) AS quantidade_vendida, SUM(si.total_price) AS faturamento
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            GROUP BY p.id
            ORDER BY quantidade_vendida DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def sales_by_hour(target_date: Optional[date] = None) -> List[Dict[str, float]]:
    target_date = target_date or date.today()
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT strftime('%H', created_at) AS hora, SUM(total) AS total
            FROM sales
            WHERE date(created_at) = date(?)
            GROUP BY hora
            ORDER BY hora
            """,
            (target_date.isoformat(),),
        )
        return [dict(row) for row in cursor.fetchall()]


__all__ = [
    "register_sale",
    "list_sales",
    "sale_details",
    "daily_sales_summary",
    "top_products",
    "sales_by_hour",
]
