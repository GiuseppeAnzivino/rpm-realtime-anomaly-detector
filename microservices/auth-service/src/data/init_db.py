"""
DATABASE INITIALIZATION LAYER
Description: Initializes the Auth-Service database by creating the tables declared in the SQLAlchemy ORM models, using the connection configured through the DATABASE_URL environment variable.
Responsibility: Retrieves and validates the database connection URL, creates missing database tables, reports the resulting schema through application logging, and manages the database engine lifecycle.
Independence: Depends only on the data model definitions and SQLAlchemy infrastructure. Can be executed independently before application startup or manually through the Python module entry point.
"""

import logging
import os

from sqlalchemy import Engine, create_engine, inspect

from data.models import Base

logger = logging.getLogger(__name__)


#region Database Configuration

def get_database_url() -> str:
    """
        Retrieve and validate the database connection URL from the environment.

        The URL is read from DATABASE_URL to avoid hardcoding connection
        credentials in the application source code.

        Raises:
            RuntimeError: If DATABASE_URL is missing or contains an empty value.

        Returns:
            The configured database connection URL.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


#endregion


#region Database Initialization

def init_db(engine: Engine) -> list[str]:
    """
        Create all missing database tables and return the existing table names.

        SQLAlchemy's create_all operation is idempotent: existing tables and
        their records are preserved, while missing tables are created.
        The resulting table names are sorted to provide deterministic output.

        Args:
            engine: The SQLAlchemy engine connected to the target database.

        Returns:
            A sorted list of table names present after initialization.
    """
    Base.metadata.create_all(engine)
    tables = sorted(inspect(engine).get_table_names())
    logger.info("Database initialised, tables: %s", ", ".join(tables))
    return tables


#endregion


#region Application Entry Point

def main() -> None:
    """
        Initialize the database configured through the environment.

        Configures application logging, creates the SQLAlchemy engine with
        connection health checks enabled, executes database initialization,
        and disposes of the engine regardless of the operation's outcome.
    """
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(get_database_url(), pool_pre_ping=True)
    try:
        init_db(engine)
    finally:
        engine.dispose()


#endregion


#region Script Execution

if __name__ == "__main__":  # pragma: no cover
    main()

#endregion