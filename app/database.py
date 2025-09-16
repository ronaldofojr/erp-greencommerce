"""Database utilities for the GreenCommerce ERP MVP."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterable

DATABASE_PATH = os.environ.get("ERP_DB_PATH", os.path.join("db", "erp.db"))


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a SQLite connection with row factory enabled."""
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database() -> None:
    """Create all tables required for the MVP if they do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        for statement in TABLE_DEFINITIONS:
            cursor.execute(statement)


TABLE_DEFINITIONS: Iterable[str] = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'caixa',
        email TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fiscal_config (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        company_name TEXT,
        cnpj TEXT,
        ie TEXT,
        im TEXT,
        csc_id TEXT,
        csc_token TEXT,
        certificate_path TEXT,
        certificate_password TEXT,
        ambiente TEXT DEFAULT 'homologacao',
        uf TEXT DEFAULT 'RJ',
        email_danfe TEXT,
        webhook_url TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        price REAL NOT NULL CHECK (price >= 0),
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        category TEXT,
        ncm TEXT,
        cest TEXT,
        cfop TEXT,
        icms_aliquota REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        change INTEGER NOT NULL,
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cpf TEXT,
        contact TEXT,
        accepts_lgpd INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pendente',
        total REAL NOT NULL,
        discount REAL DEFAULT 0,
        payment_method TEXT,
        channel TEXT DEFAULT 'pdv',
        average_ticket REAL,
        customer_id INTEGER,
        nfce_id INTEGER,
        table_id INTEGER,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (nfce_id) REFERENCES nfce(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        method TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pendente',
        pix_txid TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sale_id) REFERENCES sales(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts_receivable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        due_date TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'aberto',
        sale_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sale_id) REFERENCES sales(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts_payable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        due_date TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'aberto',
        supplier TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'livre',
        opened_at TEXT,
        closed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_id TEXT,
        source TEXT DEFAULT 'local',
        status TEXT DEFAULT 'recebido',
        table_id INTEGER,
        comanda_id INTEGER,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT,
        FOREIGN KEY (table_id) REFERENCES tables(id),
        FOREIGN KEY (comanda_id) REFERENCES comandas(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        description TEXT,
        quantity INTEGER NOT NULL,
        unit_price REAL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS comandas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER,
        status TEXT DEFAULT 'aberta',
        opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT,
        total REAL DEFAULT 0,
        FOREIGN KEY (table_id) REFERENCES tables(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nfce (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        status TEXT DEFAULT 'nao_enviada',
        xml_path TEXT,
        contingencia INTEGER DEFAULT 0,
        chave_acesso TEXT,
        protocolo TEXT,
        qrcode_url TEXT,
        environment TEXT DEFAULT 'homologacao',
        serie INTEGER,
        numero INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT,
        FOREIGN KEY (sale_id) REFERENCES sales(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nfce_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nfce_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        reason TEXT,
        registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (nfce_id) REFERENCES nfce(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        uploaded INTEGER DEFAULT 0,
        notes TEXT
    )
    """
]

