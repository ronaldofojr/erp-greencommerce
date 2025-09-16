"""Payment utilities including PIX QR Code generation."""
from __future__ import annotations

import base64
import io
import os
from typing import Dict, Optional

import qrcode

from app import database
from app.utils import current_timestamp, log_audit


def build_pix_payload(cnpj: str, txid: str, amount: float, description: str) -> str:
    """Return an EMV payload for PIX payments (simplified)."""
    amount_field = f"{amount:.2f}".replace(".", "")
    payload = (
        f"000201"
        f"010212"
        f"26360014BR.GOV.BCB.PIX0114+552199999999"
        f"52040000"
        f"5303986"
        f"5406{amount_field:0>10}"
        f"5802BR"
        f"5909GreenPOS"
        f"6009RioDeJane"
        f"62070503***"
        f"6304"
    )
    return payload


def generate_pix_qr_code(txid: str, amount: float, description: str, output_dir: str = "static/img") -> str:
    payload = build_pix_payload("00000000000191", txid, amount, description)
    img = qrcode.make(payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    filename = f"pix_{txid}.png"
    path = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "wb") as f:
        f.write(buffer.getvalue())
    log_audit("pix_qrcode_gerado", {"txid": txid, "amount": amount})
    return path


def generate_pix_base64(txid: str, amount: float, description: str) -> str:
    payload = build_pix_payload("00000000000191", txid, amount, description)
    img = qrcode.make(payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def register_payment(sale_id: int, method: str, amount: float, status: str = "pago", txid: Optional[str] = None) -> None:
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO payments (sale_id, method, amount, status, pix_txid) VALUES (?, ?, ?, ?, ?)",
            (sale_id, method, amount, status, txid),
        )
    log_audit("pagamento_registrado", {"sale_id": sale_id, "method": method, "amount": amount})


def mock_pix_callback(txid: str) -> Dict[str, str]:
    """Simulate Banco Central callback confirming PIX payment."""
    log_audit("pix_callback_recebido", {"txid": txid})
    return {"txid": txid, "status": "confirmado", "recebido_em": current_timestamp()}


__all__ = ["generate_pix_qr_code", "generate_pix_base64", "register_payment", "mock_pix_callback"]
