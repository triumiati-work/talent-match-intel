#streamlit/utils/db.py
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from urllib.parse import urlparse

# Load environment
env_path = Path(__file__).resolve().parent / "key.env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found in environment")

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
# Optional: disable client-side pooling if using Supabase Session Pooler
# from sqlalchemy.pool import NullPool
# engine = create_engine(DATABASE_URL, poolclass=NullPool)

# --- Optional: test connection
try:
    with engine.connect() as connection:
        print("✅ DB connection successful.")
except Exception as e:
    print(f"❌ Failed to connect to DB: {e}")

# --- Utility functions
def get_engine():
    return engine

def load_sql(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_parameterized_sql(sql: str, params: dict) -> pd.DataFrame:
    stmt = text(sql)
    with get_engine().connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)
    return df
