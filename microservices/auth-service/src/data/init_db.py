"""Database initialisation for the auth-service.

Creates the tables declared in ``data.models`` on the database configured
through the ``DATABASE_URL`` environment variable. The operation is
idempotent: running it again on an already initialised database leaves
existing tables and rows untouched.

It runs before the web server starts (see the Dockerfile ``CMD``) and can also
be launched manually with::

    python -m data.init_db

The database URL contains credentials, so it is never logged.
"""

import logging
import os

from sqlalchemy import Engine, create_engine, inspect

from data.models import Base

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Return the database URL from the environment.

    Raises:
        RuntimeError: if ``DATABASE_URL`` is missing or empty.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def init_db(engine: Engine) -> list[str]:
    """Create all missing tables and return the names of the existing ones."""
    Base.metadata.create_all(engine)
    tables = sorted(inspect(engine).get_table_names())
    logger.info("Database initialised, tables: %s", ", ".join(tables))
    return tables


def main() -> None:
    """Entry point: initialise the database configured in the environment."""
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(get_database_url(), pool_pre_ping=True)
    try:
        init_db(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    main()