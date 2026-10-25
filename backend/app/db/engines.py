"""Database connection and engine management for DataQuery.

Creates two separate SQLAlchemy 2.0 engines:
1. readonly_engine: Bound to dq_readonly role for query execution and analytics health checks.
2. app_engine: Bound to dq_app role for internal application state (e.g. dq_query_history).

Both engines use pool_pre_ping and dedicated connection pools.
"""

from collections.abc import Generator

from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import DatabaseUnavailable

settings = get_settings()

# Read-only engine for analytics queries and public schema exploration
readonly_engine: Engine = create_engine(
    settings.readonly_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

# Application engine for internal state, audit logging, and metadata in 'app' schema
app_engine: Engine = create_engine(
    settings.app_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

# Scoped session factories
readonly_session_factory = sessionmaker(
    bind=readonly_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

app_session_factory = sessionmaker(
    bind=app_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_readonly_conn() -> Generator[Connection, None, None]:
    """Provide a read-only database connection dependency."""
    try:
        with readonly_engine.connect() as conn:
            yield conn
    except DatabaseUnavailable:
        raise
    except Exception as ex:
        raise DatabaseUnavailable(
            message="Unable to establish connection to PostgreSQL engine.",
            details={"component": "database", "error": "Connection failed"},
        ) from ex


def get_readonly_session() -> Generator[Session, None, None]:
    """Provide a read-only SQLAlchemy session dependency."""
    try:
        with readonly_session_factory() as session:
            yield session
    except DatabaseUnavailable:
        raise
    except Exception as ex:
        raise DatabaseUnavailable(
            message="Unable to establish session with PostgreSQL engine.",
            details={"component": "database", "error": "Session failed"},
        ) from ex


def get_app_conn() -> Generator[Connection, None, None]:
    """Provide an application database connection dependency."""
    try:
        with app_engine.connect() as conn:
            yield conn
    except DatabaseUnavailable:
        raise
    except Exception as ex:
        raise DatabaseUnavailable(
            message="Unable to establish connection to PostgreSQL app engine.",
            details={"component": "database", "error": "Connection failed"},
        ) from ex


def get_app_session() -> Generator[Session, None, None]:
    """Provide an application SQLAlchemy session dependency."""
    try:
        with app_session_factory() as session:
            yield session
    except DatabaseUnavailable:
        raise
    except Exception as ex:
        raise DatabaseUnavailable(
            message="Unable to establish session with PostgreSQL app engine.",
            details={"component": "database", "error": "Session failed"},
        ) from ex


def dispose_engines() -> None:
    """Safely dispose all database engine connection pools during app shutdown."""
    readonly_engine.dispose()
    app_engine.dispose()
