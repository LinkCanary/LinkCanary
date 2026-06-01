"""Alembic environment.

Pulls the sync database URL from the application settings and uses the
SQLAlchemy model metadata as the autogenerate target.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from linkcanary_ui.config import settings
from linkcanary_ui.models import Base

# Import model modules so every table registers on Base.metadata.
import linkcanary_ui.models.crawl  # noqa: F401
import linkcanary_ui.models.webhook  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.sync_db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
