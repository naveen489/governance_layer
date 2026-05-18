"""
SQLAlchemy engine, session factory, and Base class for the Governance Layer.
Uses SQLite for MVP; swap DATABASE_URL env-var to use PostgreSQL.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./governance.db"
)

# connect_args only needed for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency – yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all tables defined via ORM models."""
    # import models so metadata is populated
    from governance.models import request, asset, event, exception, policy  # noqa: F401
    Base.metadata.create_all(bind=engine)
