# streamlit_app/utils/db.py
from sqlalchemy import create_engine, text
import os
import pandas as pd

def get_engine():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    # echo=False by default
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return engine

def load_sql(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_parameterized_sql(sql: str, params: dict) -> pd.DataFrame:
    """Execute parameterized SQL and return a pandas DataFrame."""
    engine = get_engine()
    # Use SQLAlchemy text() for parameter binding
    stmt = text(sql)
    # Pandas read_sql accepts text() and params
    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)
    return df
