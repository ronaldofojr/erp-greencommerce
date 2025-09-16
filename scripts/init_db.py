"""Populate the SQLite database with sample data for demos."""
from __future__ import annotations

from pathlib import Path

from app import clientes, comandas, database, estoque, nfce, vendas
from app.financas import add_account_payable, add_account_receivable
from app.pagamentos import register_payment
from app.security import create_user

SAMPLE_PRODUCTS = [
    {"name": "Café Expresso", "code": "CAFE001", "price": 6.0, "quantity": 100, "category": "Bebidas", "ncm": "09012100", "cfop": "5102", "icms_aliquota": 18},
    {"name": "Pão de Queijo", "code": "PAO001", "price": 4.5, "quantity": 80, "category": "Padaria", "ncm": "19059090", "cfop": "5102", "icms_aliquota": 12},
    {"name": "Hambúrguer Artesanal", "code": "BURGER01", "price": 28.0, "quantity": 40, "category": "Lanches", "ncm": "16025000", "cfop": "5102", "icms_aliquota": 18},
    {"name": "Cerveja Artesanal", "code": "CERV001", "price": 18.0, "quantity": 60, "category": "Bebidas", "ncm": "22030000", "cfop": "5102", "icms_aliquota": 25},
    {"name": "Água Mineral", "code": "AGUA001", "price": 4.0, "quantity": 120, "category": "Bebidas", "ncm": "22011000", "cfop": "5102", "icms_aliquota": 18},
    {"name": "Refrigerante Lata", "code": "REFRI01", "price": 6.5, "quantity": 90, "category": "Bebidas", "ncm": "22021000", "cfop": "5102", "icms_aliquota": 18},
    {"name": "Combo Almoço", "code": "COMBO01", "price": 35.0, "quantity": 50, "category": "Pratos", "ncm": "21069090", "cfop": "5102", "icms_aliquota": 12},
    {"name": "Salada Caesar", "code": "SALAD01", "price": 22.0, "quantity": 30, "category": "Pratos", "ncm": "21069090", "cfop": "5102", "icms_aliquota": 12},
    {"name": "Brownie", "code": "BROWN01", "price": 12.0, "quantity": 45, "category": "Sobremesas", "ncm": "19053010", "cfop": "5102", "icms_aliquota": 18},
    {"name": "Suco Natural", "code": "SUCO001", "price": 9.5, "quantity": 70, "category": "Bebidas", "ncm": "20099000", "cfop": "5102", "icms_aliquota": 18},
]

SAMPLE_CUSTOMERS = [
    {"name": "Maria Oliveira", "cpf": "12345678901", "contact": "21 99999-1000", "accepts_lgpd": True},
    {"name": "João Silva", "cpf": "10987654321", "contact": "21 98888-2000", "accepts_lgpd": True},
    {"name": "Cliente Balcão", "cpf": None, "contact": None, "accepts_lgpd": False},
]


def seed() -> None:
    database.initialize_database()

    if not Path("backups").exists():
        Path("backups").mkdir(parents=True)

    if not estoque.list_products():
        for product in SAMPLE_PRODUCTS:
            estoque.create_product(product)

    if not clientes.list_customers():
        for customer in SAMPLE_CUSTOMERS:
            clientes.create_customer(**customer)

    create_user("admin", "admin123", role="admin", email="admin@erp.local")
    create_user("caixa", "caixa123", role="caixa")

    nfce.save_fiscal_config(
        {
            "company_name": "GreenCommerce Demo RJ",
            "cnpj": "12345678000199",
            "ie": "12345678",
            "csc_id": "000001",
            "csc_token": "TOKENDEMO123",
            "certificate_path": "",
            "certificate_password": "",
            "ambiente": "homologacao",
            "uf": "RJ",
            "email_danfe": "contato@greencommerce.com",
            "webhook_url": "https://exemplo.com/webhook",
        }
    )

    venda1 = vendas.register_sale(
        [{"product_id": 1, "quantity": 2, "unit_price": 6.0}],
        payment_method="dinheiro",
        customer_id=1,
    )
    register_payment(venda1, "dinheiro", 12.0)

    venda2 = vendas.register_sale(
        [
            {"product_id": 3, "quantity": 1, "unit_price": 28.0},
            {"product_id": 9, "quantity": 2, "unit_price": 12.0},
        ],
        payment_method="cartao",
        customer_id=2,
    )
    register_payment(venda2, "cartao", 52.0)

    nfce.emitir_nfce(venda1)
    nfce.emitir_nfce(venda2)

    comanda_id = comandas.open_comanda(table_id=None)
    comandas.add_order(
        comanda_id,
        [
            {"product_id": 1, "description": "Café Expresso", "quantity": 1, "unit_price": 6.0},
            {"product_id": 3, "description": "Hambúrguer Artesanal", "quantity": 1, "unit_price": 28.0},
        ],
        source="local",
    )

    add_account_receivable("Mensalidade SaaS", "2025-02-10", 299.0)
    add_account_payable("Fornecedor de Bebidas", "2025-02-05", 850.0, "Distribuidora RJ")

    print("Banco populado com dados de demonstração.")


if __name__ == "__main__":
    seed()
