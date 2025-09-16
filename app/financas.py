"""Finance module for accounts payable/receivable and cash flow."""
from __future__ import annotations

from typing import Dict, List

from app import database
from app.utils import log_audit


def add_account_receivable(description: str, due_date: str, amount: float, sale_id: int | None = None) -> int:
    with database.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO accounts_receivable (description, due_date, amount, sale_id) VALUES (?, ?, ?, ?)",
            (description, due_date, amount, sale_id),
        )
        account_id = cursor.lastrowid
    log_audit("conta_receber_criada", {"id": account_id, "valor": amount})
    return account_id


def add_account_payable(description: str, due_date: str, amount: float, supplier: str) -> int:
    with database.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO accounts_payable (description, due_date, amount, supplier) VALUES (?, ?, ?, ?)",
            (description, due_date, amount, supplier),
        )
        account_id = cursor.lastrowid
    log_audit("conta_pagar_criada", {"id": account_id, "valor": amount})
    return account_id


def update_account_status(table: str, account_id: int, status: str) -> None:
    if table not in {"accounts_receivable", "accounts_payable"}:
        raise ValueError("Tabela inválida")
    with database.get_connection() as conn:
        conn.execute(
            f"UPDATE {table} SET status = ?, created_at = created_at WHERE id = ?",
            (status, account_id),
        )
    log_audit("conta_atualizada", {"tabela": table, "id": account_id, "status": status})


def cash_flow_summary() -> Dict[str, float]:
    with database.get_connection() as conn:
        recebimentos = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE status = 'pago'",
        ).fetchone()["total"]
        contas_receber = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM accounts_receivable WHERE status != 'pago'",
        ).fetchone()["total"]
        contas_pagar = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM accounts_payable WHERE status != 'pago'",
        ).fetchone()["total"]
    return {
        "entradas_confirmadas": recebimentos,
        "receber_em_aberto": contas_receber,
        "pagar_em_aberto": contas_pagar,
        "saldo_estimado": recebimentos + contas_receber - contas_pagar,
    }


def fluxo_caixa_detalhado() -> List[Dict[str, float]]:
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT created_at AS data, amount AS valor, method AS origem, status
            FROM payments
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
        return [dict(row) for row in cursor.fetchall()]


__all__ = [
    "add_account_receivable",
    "add_account_payable",
    "update_account_status",
    "cash_flow_summary",
    "fluxo_caixa_detalhado",
]
