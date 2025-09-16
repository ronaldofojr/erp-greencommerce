"""Utility helpers for validation, formatting and notifications."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CNPJ_REGEX = re.compile(r"^\d{14}$")
IE_REGEX = re.compile(r"^[0-9A-Z]{2,14}$")
CPF_REGEX = re.compile(r"^\d{11}$")


def validate_cnpj(cnpj: str) -> bool:
    """Perform a basic length/format validation for CNPJ."""
    if not cnpj:
        return False
    digits = re.sub(r"\D", "", cnpj)
    if not CNPJ_REGEX.match(digits):
        return False
    return True


def validate_ie(ie: str) -> bool:
    """Validate state registration format (simplified)."""
    if not ie:
        return False
    return bool(IE_REGEX.match(ie.strip().upper()))


def validate_cpf(cpf: str) -> bool:
    """Perform simple CPF validation used for optional NFC-e identification."""
    if not cpf:
        return False
    digits = re.sub(r"\D", "", cpf)
    return bool(CPF_REGEX.match(digits))


def current_timestamp() -> str:
    return datetime.utcnow().isoformat()


def ensure_directory(path: str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log_audit(event: str, details: Optional[Dict[str, Any]] = None) -> None:
    logger.info("AUDIT | %s | %s", event, json.dumps(details or {}, ensure_ascii=False))

