"""
Database connection (PostgreSQL)
No ORM yet – connection test only
"""

from sqlalchemy import create_engine
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


def test_db_connection():
    with engine.connect() as conn:
        conn.execute("SELECT 1")
