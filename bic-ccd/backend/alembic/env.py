"""Alembic environment configuration.

Supports two migration targets, selected by the ALEMBIC_TARGET env var:

  ALEMBIC_TARGET=legacy    (default) — manages CCB_* and app tables via Base.
  ALEMBIC_TARGET=bic_ccd             — manages BIC_CCD_* tables via BicCcdBase,
                                       tracked in ALEMBIC_VERSION_BIC_CCD.

Usage:
  # legacy tables (existing behaviour):
  alembic upgrade head

  # BIC_CCD tables:
  ALEMBIC_TARGET=bic_ccd alembic upgrade head
  ALEMBIC_TARGET=bic_ccd alembic revision --autogenerate -m "d2_bic_ccd_..."
"""
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import get_settings

_target = os.environ.get("ALEMBIC_TARGET", "legacy")

if _target == "bic_ccd":
    from app.database import BicCcdBase
    import app.models.bic_ccd  # noqa — registers all BIC_CCD_* models
    target_metadata = BicCcdBase.metadata
    _version_table = "ALEMBIC_VERSION_BIC_CCD"
else:
    from app.database import Base
    import app.models  # noqa — registers all CCB_* and app models
    target_metadata = Base.metadata
    _version_table = "alembic_version"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        version_table=_version_table,
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
            version_table=_version_table,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
