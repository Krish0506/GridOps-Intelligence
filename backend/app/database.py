"""Database engine and request-scoped session management."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://gridops:gridops_dev_only@localhost:5432/gridops",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session and close it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
