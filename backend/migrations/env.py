import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure backend root is on sys.path so app modules are resolvable
# whether alembic is invoked from repo root or backend/
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

load_dotenv()


from app.db.base import Base
from app.models.document import Document
from app.models.extraction import Extraction

config = context.config

database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),
    )

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
