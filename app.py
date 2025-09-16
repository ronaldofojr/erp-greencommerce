"""GreenCommerce ERP MVP - Flask application."""
from __future__ import annotations

import os
import re
from datetime import date
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import clientes, comandas, database, estoque, financas, nfce, pagamentos, relatorios, vendas
from app.config_fiscal import supported_states
from app.security import authenticate, create_user, has_role
from app.utils import log_audit

app = Flask(__name__)
app.secret_key = os.environ.get("ERP_SECRET_KEY", "greencommerce-secret")


@app.before_request
def ensure_db() -> None:
    database.initialize_database()


def require_role(roles: set[str] | None = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Faça login para continuar", "warning")
                return redirect(url_for("login"))
            if roles and not has_role(user, roles):
                flash("Você não possui permissão para acessar esta área", "danger")
                return redirect(url_for("dashboard"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = authenticate(request.form["username"], request.form["password"])
        if user:
            session["user"] = {"id": user["id"], "username": user["username"], "role": user["role"]}
            flash("Login realizado com sucesso", "success")
            return redirect(url_for("dashboard"))
        flash("Credenciais inválidas", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Sessão encerrada", "info")
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    resumo = vendas.daily_sales_summary()
    produtos = vendas.top_products()
    por_hora = vendas.sales_by_hour()
    low_stock = list(estoque.low_stock_alerts())
    fluxo = financas.cash_flow_summary()
    return render_template(
        "dashboard.html",
        resumo=resumo,
        produtos=produtos,
        por_hora=por_hora,
        low_stock=low_stock,
        fluxo=fluxo,
    )


@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if request.method == "POST":
        data = request.form.to_dict()
        nfce.save_fiscal_config(data)
        flash("Configurações fiscais salvas! Configure o certificado digital e CSC.", "success")
        return redirect(url_for("dashboard"))
    config = nfce.load_fiscal_config()
    return render_template("onboarding.html", config=config, estados=supported_states())


@app.route("/produtos", methods=["GET", "POST"])
def manage_products():
    if request.method == "POST":
        payload = request.form.to_dict() if request.form else request.json
        try:
            estoque.create_product(payload)
            flash("Produto cadastrado com sucesso", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("manage_products"))
    products = estoque.list_products()
    return render_template("products.html", products=products)


@app.route("/clientes", methods=["GET", "POST"])
def manage_clients():
    if request.method == "POST":
        form = request.form
        try:
            clientes.create_customer(
                form["name"],
                form.get("cpf"),
                form.get("contact"),
                bool(form.get("accepts_lgpd")),
            )
            flash("Cliente cadastrado com sucesso", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("manage_clients"))
    return render_template("customers.html", customers=clientes.list_customers())


@app.route("/vendas", methods=["GET", "POST"])
def manage_sales():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            items = data.get("items", [])
            payment_method = data.get("payment_method", "dinheiro")
            customer_id = data.get("customer_id")
            table_id = data.get("table_id")
            channel = data.get("channel", "pdv")
        else:
            data = request.form.to_dict(flat=False)
            pattern = re.compile(r"items\[(\d+)\]\[(.*?)\]")
            grouped: Dict[str, Dict[str, Any]] = {}
            for key, values in data.items():
                match = pattern.match(key)
                if match:
                    index, field = match.groups()
                    grouped.setdefault(index, {})[field] = values[0]
            items = [
                {
                    "product_id": int(fields.get("product_id", 0)),
                    "quantity": int(fields.get("quantity", 0)),
                    "unit_price": float(fields.get("unit_price", 0)),
                }
                for _, fields in sorted(grouped.items())
            ]
            payment_method = request.form.get("payment_method", "dinheiro")
            customer_id = request.form.get("customer_id")
            table_id = request.form.get("table_id")
            channel = request.form.get("channel", "pdv")
        sale_id = vendas.register_sale(
            items,
            payment_method,
            customer_id=int(customer_id) if customer_id else None,
            table_id=int(table_id) if table_id else None,
            channel=channel,
        )
        if request.is_json:
            return jsonify({"sale_id": sale_id}), 201
        flash(f"Venda registrada #{sale_id}", "success")
        return redirect(url_for("manage_sales"))
    return render_template("sales.html", sales=vendas.list_sales())


@app.route("/emitir-nfce", methods=["POST"])
def emitir_nfce_route():
    payload = request.get_json(force=True)
    result = nfce.emitir_nfce(payload["sale_id"], contingencia=payload.get("contingencia", False))
    log_audit("rota_emitir_nfce", {"sale_id": payload["sale_id"], "resultado": result["status"]})
    return jsonify(result)


@app.route("/cancelar-nfce", methods=["POST"])
def cancelar_nfce_route():
    payload = request.get_json(force=True)
    nfce.cancelar_nfce(payload["nfce_id"], payload.get("motivo", "Cancelamento solicitado"))
    log_audit("rota_cancelar_nfce", {"nfce_id": payload["nfce_id"]})
    return jsonify({"status": "cancelada"})


@app.route("/gerar-pix", methods=["POST"])
def gerar_pix():
    payload = request.get_json(force=True)
    txid = payload.get("txid") or f"TX{payload.get('sale_id', '')}"
    qr_path = pagamentos.generate_pix_qr_code(txid, float(payload.get("amount", 0)), payload.get("description", ""))
    pagamentos.register_payment(payload.get("sale_id", 0), "pix", float(payload.get("amount", 0)), status="pendente", txid=txid)
    log_audit("rota_pix", {"txid": txid, "sale_id": payload.get("sale_id")})
    return jsonify({"txid": txid, "qr_code": qr_path})


@app.route("/importar-pedido-ifood", methods=["POST"])
def importar_pedido_ifood():
    payload = request.get_json(force=True)
    resultado = comandas.import_ifood_order(payload)
    log_audit("rota_ifood", {"external_id": payload.get("order_id")})
    return jsonify(resultado)


@app.route("/abrir-comanda", methods=["POST"])
def abrir_comanda():
    payload = request.get_json(force=True)
    comanda_id = comandas.open_comanda(payload.get("table_id"))
    return jsonify({"comanda_id": comanda_id})


@app.route("/relatorios/vendas")
@require_role({"admin", "gerente"})
def relatorios_vendas():
    analytics = relatorios.analytics_dashboard()
    return render_template("reports.html", analytics=analytics)


@app.route("/relatorios/sped")
@require_role({"admin", "gerente"})
def relatorios_sped():
    output = relatorios.export_nfce_sped(date.today(), date.today(), Path("backups") / "sped_nfce.txt")
    return jsonify({"arquivo": str(output)})


@app.route("/financas/fluxo-caixa")
@require_role({"admin", "gerente"})
def fluxo_caixa():
    resumo = financas.cash_flow_summary()
    detalhado = financas.fluxo_caixa_detalhado()
    return render_template("finance.html", resumo=resumo, detalhado=detalhado)


@app.route("/api/produtos")
def api_produtos():
    return jsonify(estoque.list_products())


@app.route("/api/comandas")
def api_comandas():
    return jsonify(comandas.list_tables())


@app.route("/backup/nfce")
def backup_nfce():
    ensure_dir = Path("backups")
    ensure_dir.mkdir(parents=True, exist_ok=True)
    files = [str(f) for f in ensure_dir.glob("nfce_*.xml")]
    return jsonify({"xmls": files})


@app.route("/setup/usuario-admin")
def setup_usuario_admin():
    with database.get_connection() as conn:
        exists = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not exists:
        create_user("admin", "admin123", role="admin", email="admin@erp.local")
        flash("Usuário admin criado com senha admin123", "warning")
    else:
        flash("Usuário admin já configurado", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
