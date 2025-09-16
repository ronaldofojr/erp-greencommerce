"""Fiscal configuration and utilities for handling multi-UF rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AutorizadorConfig:
    """Configuration data for a SEFAZ autorizador."""

    autorizador: str
    servico_autorizacao: str
    servico_retorno: str
    svrs: bool = False
    qr_code_url: Optional[str] = None
    notas: Optional[str] = None


FISCAL_CONFIG: Dict[str, AutorizadorConfig] = {
    "RJ": AutorizadorConfig(
        autorizador="SEFAZ-RJ",
        servico_autorizacao="https://nfce.sefaz.rj.gov.br/nfce/services/NFeAutorizacao4",
        servico_retorno="https://nfce.sefaz.rj.gov.br/nfce/services/NFeRetAutorizacao4",
        svrs=False,
        qr_code_url="https://nfce.sefaz.rj.gov.br/consulta",
        notas=(
            "Incluir telefone 151 do Procon-RJ no DANFE, validar regras de 2025 "
            "para campos obrigatórios de endereço e informar opção de pagamento PIX."
        ),
    ),
    "SVRS": AutorizadorConfig(
        autorizador="SVRS",
        servico_autorizacao="https://nfce.svrs.rs.gov.br/ws/NFeAutorizacao/NFeAutorizacao4",
        servico_retorno="https://nfce.svrs.rs.gov.br/ws/NFeRetAutorizacao/NFeRetAutorizacao4",
        svrs=True,
        notas="Utilizado como contingência para RJ em caso de indisponibilidade."
    ),
    "SP": AutorizadorConfig(
        autorizador="SEFAZ-SP",
        servico_autorizacao="https://nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4",
        servico_retorno="https://nfce.fazenda.sp.gov.br/ws/NFeRetAutorizacao4",
        svrs=False,
        qr_code_url="https://portal.fazenda.sp.gov.br/Paginas/ConsultaNFCe.aspx",
        notas="Placeholder para regras específicas de SP."
    ),
    "SC": AutorizadorConfig(
        autorizador="SEFAZ-SC",
        servico_autorizacao="https://nfce.sef.sc.gov.br/ws/NFeAutorizacao4",
        servico_retorno="https://nfce.sef.sc.gov.br/ws/NFeRetAutorizacao4",
        svrs=False,
        qr_code_url="https://sat.sef.sc.gov.br/nfce/consulta",
        notas="Placeholder para validações de SC."
    ),
}


def get_config(uf: str) -> AutorizadorConfig:
    """Return configuration for the provided state or fallback to RJ."""
    uf = uf.upper()
    return FISCAL_CONFIG.get(uf, FISCAL_CONFIG["RJ"])


def supported_states() -> Dict[str, AutorizadorConfig]:
    """Expose configurations for documentation purposes."""
    return FISCAL_CONFIG

