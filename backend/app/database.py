"""Database engine and request-scoped session management."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from data_engineering.etl.config import resolve_database_url

DATABASE_URL = os.getenv("DATABASE_URL") or resolve_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session and close it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
