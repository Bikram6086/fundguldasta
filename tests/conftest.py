"""Shared pytest fixtures."""
import pytest
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

@pytest.fixture(scope="session")
def db():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "fundguldasta_dev"),
        user=os.getenv("DB_USER", "fundguldasta_user"),
    )
    yield conn
    conn.close()

# All 13 verified scheme codes and what we know about them
VERIFIED_CODES = [
    "118825", "120152", "118834", "122639", "118955",
    "120505", "119071", "118989", "118778", "120828",
    "149134", "145552", "135800",
]

ARCHETYPES = ["steady", "balanced", "aggressive", "conviction"]

# Funds that MUST score high on manager stability (known long-tenure lead managers)
HIGH_MANAGER_TENURE = {
    "122639": ("Rajeev Thakkar", 2009),   # Parag Parikh — since 2009
    "118989": ("Chirag Setalvad", 2014),  # HDFC Mid Cap — since 2014
    "120505": ("Shreyash Devalkar", 2016), # Axis Midcap — since 2016
    "118778": ("Samir Rachh", 2016),       # Nippon Small Cap — since 2016
    "119071": ("Jay Kothari", 2017),       # DSP Midcap — since 2017
}

# Sentinel score that means "data not loaded" — must never appear post-fix
MANAGER_SENTINEL = 40
MANAGER_SENTINEL_ALT = 41
