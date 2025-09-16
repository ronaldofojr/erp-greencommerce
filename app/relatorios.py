"""Reporting helpers for analytics and SPED exports."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List

from app import database
from app.utils import ensure_directory, log_audit


def export_nfce_sped(start_date: date, end_date: date, output_path: Path) -> Path:
    ensure_directory(str(output_path.parent))
    with database.get_connection() as conn, open(output_path, "w", encoding="utf-8") as file:
        file.write("|0000|000|1|ERPGREEN|" + start_date.strftime("%Y%m%d") + "|" + end_date.strftime("%Y%m%d") + "|\n")
        cursor = conn.execute(
            "SELECT * FROM nfce WHERE date(created_at) BETWEEN date(?) AND date(?)",
            (start_date.isoformat(), end_date.isoformat()),
        )
        for row in cursor.fetchall():
            file.write(f"|C100|{row['chave_acesso']}|{row['status']}|{row['environment']}|\n")
    log_audit("sped_exportado", {"arquivo": str(output_path)})
    return output_path


def export_sales_csv(output_path: Path) -> Path:
    ensure_directory(str(output_path.parent))
    with database.get_connection() as conn, open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["ID", "Data", "Total", "Desconto", "Forma Pagamento", "Status"])
        for row in conn.execute("SELECT id, created_at, total, discount, payment_method, status FROM sales"):
            writer.writerow([row["id"], row["created_at"], row["total"], row["discount"], row["payment_method"], row["status"]])
    log_audit("relatorio_csv", {"arquivo": str(output_path)})
    return output_path


def export_sales_excel(output_path: Path) -> Path:
    ensure_directory(str(output_path.parent))
    try:
        from openpyxl import Workbook
    except ImportError:
        # fallback to CSV style content
        return export_sales_csv(output_path.with_suffix(".csv"))

    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Data", "Total", "Desconto", "Forma Pagamento", "Status"])
    with database.get_connection() as conn:
        for row in conn.execute("SELECT id, created_at, total, discount, payment_method, status FROM sales"):
            ws.append([row["id"], row["created_at"], row["total"], row["discount"], row["payment_method"], row["status"]])
    wb.save(output_path)
    log_audit("relatorio_excel", {"arquivo": str(output_path)})
    return output_path


def analytics_dashboard() -> Dict[str, Iterable[Dict[str, float]]]:
    from app import vendas

    resumo = vendas.daily_sales_summary()
    produtos = vendas.top_products()
    por_hora = vendas.sales_by_hour()

    return {
        "resumo": resumo,
        "produtos": produtos,
        "por_hora": por_hora,
    }


__all__ = ["export_nfce_sped", "export_sales_csv", "export_sales_excel", "analytics_dashboard"]
