"""Module responsible for NFC-e lifecycle (XML, envio, DANFE)."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app import database
from app.config_fiscal import get_config
from app.utils import current_timestamp, ensure_directory, log_audit


def load_fiscal_config() -> Dict[str, Optional[str]]:
    with database.get_connection() as conn:
        row = conn.execute("SELECT * FROM fiscal_config WHERE id = 1").fetchone()
        return dict(row) if row else {}


def save_fiscal_config(data: Dict[str, Optional[str]]) -> None:
    """Upsert fiscal configuration (single row)."""
    fields = [
        "company_name",
        "cnpj",
        "ie",
        "im",
        "csc_id",
        "csc_token",
        "certificate_path",
        "certificate_password",
        "ambiente",
        "uf",
        "email_danfe",
        "webhook_url",
    ]
    values = [data.get(field) for field in fields]
    with database.get_connection() as conn:
        existing = conn.execute("SELECT id FROM fiscal_config WHERE id = 1").fetchone()
        if existing:
            assignments = ", ".join(f"{field} = ?" for field in fields)
            conn.execute(
                f"UPDATE fiscal_config SET {assignments}, updated_at = ? WHERE id = 1",
                (*values, current_timestamp()),
            )
        else:
            placeholders = ", ".join(["?"] * len(fields))
            conn.execute(
                f"INSERT INTO fiscal_config (id, {', '.join(fields)}) VALUES (1, {placeholders})",
                values,
            )
    log_audit("config_fiscal_atualizada", {"uf": data.get("uf", "RJ")})


def build_nfce_xml(sale_id: int, items: List[Dict[str, str]], config: Dict[str, str]) -> ET.Element:
    """Generate a minimal NFC-e XML document aligned with RJ requirements."""
    root = ET.Element("NFe")
    inf_nfe = ET.SubElement(root, "infNFe", Id=f"NFe{uuid.uuid4().hex}", versao="4.00")
    ide = ET.SubElement(inf_nfe, "ide")
    ET.SubElement(ide, "cUF").text = "33"  # RJ code
    ET.SubElement(ide, "tpAmb").text = "2" if config.get("ambiente") == "homologacao" else "1"
    ET.SubElement(ide, "mod").text = "65"
    ET.SubElement(ide, "serie").text = config.get("serie", "1")
    ET.SubElement(ide, "nNF").text = config.get("numero", "1")
    ET.SubElement(ide, "natOp").text = "VENDA"

    emit = ET.SubElement(inf_nfe, "emit")
    ET.SubElement(emit, "xNome").text = config.get("company_name", "Empresa Demo RJ")
    ET.SubElement(emit, "CNPJ").text = config.get("cnpj", "00000000000000")
    ET.SubElement(emit, "IE").text = config.get("ie", "ISENTO")

    ender_emit = ET.SubElement(emit, "enderEmit")
    ET.SubElement(ender_emit, "xLgr").text = config.get("logradouro", "Rua das Flores")
    ET.SubElement(ender_emit, "xMun").text = config.get("municipio", "Rio de Janeiro")
    ET.SubElement(ender_emit, "UF").text = config.get("uf", "RJ")

    total_bruto = 0.0
    icms_total = 0.0
    for index, item in enumerate(items, start=1):
        det = ET.SubElement(inf_nfe, "det", nItem=str(index))
        prod = ET.SubElement(det, "prod")
        ET.SubElement(prod, "cProd").text = str(item.get("codigo"))
        ET.SubElement(prod, "xProd").text = item.get("descricao")
        ET.SubElement(prod, "NCM").text = item.get("ncm", "00000000")
        ET.SubElement(prod, "CFOP").text = item.get("cfop", "5102")
        ET.SubElement(prod, "uCom").text = "UN"
        ET.SubElement(prod, "qCom").text = str(item.get("quantidade", 1))
        ET.SubElement(prod, "vUnCom").text = f"{float(item.get('valor_unitario', 0)):.2f}"
        total_item = float(item.get("total", 0))
        total_bruto += total_item
        ET.SubElement(prod, "vProd").text = f"{total_item:.2f}"

        imposto = ET.SubElement(det, "imposto")
        icms = ET.SubElement(imposto, "ICMS")
        icms00 = ET.SubElement(icms, "ICMS00")
        aliquota = float(item.get("icms", 0))
        base_calculo = total_item
        icms_valor = round(base_calculo * aliquota / 100, 2)
        icms_total += icms_valor
        ET.SubElement(icms00, "orig").text = "0"
        ET.SubElement(icms00, "CST").text = "00"
        ET.SubElement(icms00, "modBC").text = "3"
        ET.SubElement(icms00, "vBC").text = f"{base_calculo:.2f}"
        ET.SubElement(icms00, "pICMS").text = f"{aliquota:.2f}"
        ET.SubElement(icms00, "vICMS").text = f"{icms_valor:.2f}"

    total = ET.SubElement(inf_nfe, "total")
    icmstot = ET.SubElement(total, "ICMSTot")
    ET.SubElement(icmstot, "vBC").text = f"{total_bruto:.2f}"
    ET.SubElement(icmstot, "vICMS").text = f"{icms_total:.2f}"
    ET.SubElement(icmstot, "vProd").text = f"{total_bruto:.2f}"
    ET.SubElement(icmstot, "vNF").text = f"{total_bruto:.2f}"

    # Informações adicionais para atender Procon-RJ
    inf_adic = ET.SubElement(inf_nfe, "infAdic")
    ET.SubElement(inf_adic, "infCpl").text = "Atendimento Procon-RJ: 151"

    return root


def serialize_xml(element: ET.Element, output_path: Path) -> Path:
    ensure_directory(str(output_path.parent))
    tree = ET.ElementTree(element)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def sign_xml(xml_path: Path, certificate_path: str, certificate_password: str) -> Path:
    """Mock digital signature using signxml if available."""
    if not certificate_path or not Path(certificate_path).exists():
        log_audit("assinatura_skipped", {"xml": str(xml_path), "motivo": "certificado_nao_configurado"})
        return xml_path
    try:
        from signxml import XMLSigner
    except ImportError:
        log_audit("assinatura_mock", {"xml": str(xml_path)})
        return xml_path

    signer = XMLSigner(method="enveloped", signature_algorithm="rsa-sha256")
    signed_output = xml_path.with_suffix(".signed.xml")
    signed_root = signer.sign(
        ET.parse(xml_path).getroot(),
        key=open(certificate_path, "rb").read(),
        passphrase=certificate_password.encode("utf-8") if certificate_password else None,
    )
    ET.ElementTree(signed_root).write(signed_output, encoding="utf-8", xml_declaration=True)
    return signed_output


def send_to_sefaz(xml_path: Path, uf: str, contingencia: bool = False) -> Dict[str, str]:
    """Simulate synchronous submission to SEFAZ."""
    autorizador = get_config("SVRS" if contingencia else uf)
    try:
        from pynfe.processamento.comunicacao import ComunicacaoSefaz

        comunicador = ComunicacaoSefaz(uf=uf, cert=bytes(), senha="", homologacao=True)
        # Envio real exigiria certificado válido e XML assinado.
        log_audit(
            "nfce_envio_pynfe",
            {
                "xml": str(xml_path),
                "autorizador": autorizador.autorizador,
                "contingencia": contingencia,
                "cliente": str(comunicador),
            },
        )
    except Exception:  # noqa: BLE001 - fallback para mock
        pass
    log_audit(
        "nfce_envio",
        {"xml": str(xml_path), "autorizador": autorizador.autorizador, "contingencia": contingencia},
    )
    return {
        "status": "autorizado",
        "protocolo": f"{uuid.uuid4().hex[:10]}",
        "chave": uuid.uuid4().hex[:44],
        "url_qrcode": autorizador.qr_code_url or "https://nfce.sefaz.rj.gov.br/consulta",
    }


def persist_nfce(sale_id: int, xml_path: Path, response: Dict[str, str], contingencia: bool, environment: str) -> int:
    with database.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO nfce (sale_id, status, xml_path, contingencia, chave_acesso, protocolo, qrcode_url, environment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sale_id,
                response["status"],
                str(xml_path),
                1 if contingencia else 0,
                response["chave"],
                response["protocolo"],
                response["url_qrcode"],
                environment,
                current_timestamp(),
            ),
        )
        nfce_id = cursor.lastrowid
        conn.execute("UPDATE sales SET nfce_id = ?, status = 'autorizada' WHERE id = ?", (nfce_id, sale_id))
    log_audit("nfce_persistida", {"nfce_id": nfce_id, "sale_id": sale_id})
    return nfce_id


def generate_danfe(xml_path: Path, output_path: Path, procon_text: str = "Procon-RJ 151") -> Path:
    ensure_directory(str(output_path.parent))
    c = canvas.Canvas(str(output_path), pagesize=A4)
    c.drawString(40, 800, "DANFE NFC-e - GreenCommerce MVP")
    c.drawString(40, 780, f"Arquivo XML: {xml_path.name}")
    c.drawString(40, 760, procon_text)
    c.drawString(40, 740, "QRCode disponível no portal SEFAZ-RJ")
    c.drawString(40, 720, "Este DANFE é apenas para demonstração.")
    c.showPage()
    c.save()
    log_audit("danfe_gerado", {"xml": str(xml_path), "danfe": str(output_path)})
    return output_path


def emitir_nfce(sale_id: int, contingencia: bool = False) -> Dict[str, str]:
    config = load_fiscal_config()
    uf = config.get("uf", "RJ")
    environment = config.get("ambiente", "homologacao")

    with database.get_connection() as conn:
        sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        items = conn.execute(
            """
            SELECT si.quantity, si.unit_price, si.total_price, p.code AS codigo, p.name AS descricao, p.ncm, p.cfop, p.icms_aliquota AS icms
            FROM sale_items si JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            """,
            (sale_id,),
        ).fetchall()
    item_dicts = [dict(row) for row in items]

    xml_element = build_nfce_xml(sale_id, item_dicts, config)
    xml_path = Path("backups") / f"nfce_{sale_id}.xml"
    serialize_xml(xml_element, xml_path)

    signed_xml_path = sign_xml(xml_path, config.get("certificate_path", ""), config.get("certificate_password", ""))
    response = send_to_sefaz(signed_xml_path, uf, contingencia=contingencia)
    nfce_id = persist_nfce(sale_id, signed_xml_path, response, contingencia, environment)

    danfe_path = Path("backups") / f"danfe_{sale_id}.pdf"
    generate_danfe(signed_xml_path, danfe_path)

    return {
        "nfce_id": nfce_id,
        "status": response["status"],
        "danfe_path": str(danfe_path),
        "qrcode_url": response["url_qrcode"],
    }


def cancelar_nfce(nfce_id: int, motivo: str) -> None:
    with database.get_connection() as conn:
        conn.execute("UPDATE nfce SET status = 'cancelada', updated_at = ? WHERE id = ?", (current_timestamp(), nfce_id))
        conn.execute(
            "INSERT INTO nfce_events (nfce_id, event_type, reason) VALUES (?, 'cancelamento', ?)",
            (nfce_id, motivo),
        )
    log_audit("nfce_cancelada", {"nfce_id": nfce_id, "motivo": motivo})


def registrar_contingencia(sale_id: int, xml_path: Path) -> int:
    response = {
        "status": "contingencia",
        "protocolo": "",
        "chave": uuid.uuid4().hex[:44],
        "url_qrcode": "https://nfce.svrs.rs.gov.br/consulta",
    }
    return persist_nfce(sale_id, xml_path, response, True, "contingencia")


__all__ = [
    "emitir_nfce",
    "cancelar_nfce",
    "generate_danfe",
    "load_fiscal_config",
    "save_fiscal_config",
]
