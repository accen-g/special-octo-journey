"""Database engine, session factory and dependency."""
from sqlalchemy import create_engine, event, MetaData
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine_kwargs = {}
if settings.USE_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.DB_POOL_MAX
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["max_overflow"] = 5
    # Recycle connections after 30 min so Oracle doesn't kill idle sessions
    # before SQLAlchemy notices, preventing the silent +200ms pre-ping on checkout.
    engine_kwargs["pool_recycle"] = 1800

engine = create_engine(settings.database_url, echo=settings.DEBUG, **engine_kwargs)

# Enable WAL for SQLite
if settings.USE_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


_naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_naming_convention)


def get_db():
    """FastAPI dependency yielding a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
