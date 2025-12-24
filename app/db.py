"""
Database setup
Engine + Base metadata only
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL
from app.models import Base
from sqlalchemy.orm import Session



engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)


def test_db_connection():
    with engine.connect() as conn:
        conn.execute("SELECT 1")


def create_all_tables():
    """
    Creates tables from SQLAlchemy models.
    For local/dev only.
    """
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
