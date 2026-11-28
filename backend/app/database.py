from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

_url = make_url(settings.DATABASE_URL)
IS_SQLITE = _url.get_backend_name() == "sqlite"

connect_args = {}
if IS_SQLITE:
    connect_args = {"check_same_thread": False, "timeout": 15}
    # A fresh deploy has no data dir yet; sqlite won't create parent folders.
    if _url.database and _url.database != ":memory:":
        Path(_url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    future=True
)

if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        try:
            # WAL lets readers run while one writer commits; busy_timeout makes
            # a second writer wait instead of failing with "database is locked".
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=15000")
            cur.execute("PRAGMA synchronous=NORMAL")
        finally:
            cur.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    # Import models so every table is registered on Base before create_all.
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
