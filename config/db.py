"""
Shared database configuration for all engine and data pipeline modules.

Reads DATABASE_URL first (Railway / Timescale Cloud production).
Falls back to individual DB_HOST/DB_NAME/DB_USER env vars (local dev).

Usage in any module:
    from config.db import get_db_config
    DB_CONFIG = get_db_config()
"""

import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load local .env if present — no-op in Railway (env vars are injected directly)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env")
load_dotenv(_env_path)


def get_db_config() -> dict:
    """Return a psycopg2-compatible DB config dict for the current environment."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        u = urlparse(database_url)
        return {
            "host":     u.hostname,
            "port":     u.port or 5432,
            "dbname":   u.path.lstrip("/"),
            "user":     u.username,
            "password": u.password,
            "sslmode":  "require",
        }
    return {
        "host":   os.getenv("DB_HOST", "localhost"),
        "port":   int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "fundguldasta_dev"),
        "user":   os.getenv("DB_USER", "fundguldasta_user"),
    }
