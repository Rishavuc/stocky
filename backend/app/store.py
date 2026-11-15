"""Persistent application state. User-row locks serialize each account's mutations."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, JSON, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///./investors_eye_v2.db").replace(
    "sqlite+aiosqlite:", "sqlite:"
)
engine = create_engine(
    URL,
    connect_args={"check_same_thread": False, "timeout": 30}
    if URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
if URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_setup(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.isolation_level = None

    @event.listens_for(engine, "begin")
    def sqlite_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")


DB = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "eye_users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password: Mapped[str] = mapped_column(String)


class Session(Base):
    __tablename__ = "eye_sessions"
    digest: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String, index=True)
    expires: Mapped[str] = mapped_column(String)


class Record(Base):
    __tablename__ = "eye_records"
    __table_args__ = (UniqueConstraint("owner", "kind", "key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)


def now():
    return datetime.now(timezone.utc).isoformat()


class Migration(Base):
    __tablename__ = "eye_schema_migrations"
    version: Mapped[int] = mapped_column(primary_key=True)
    applied_at: Mapped[str] = mapped_column(String)


def init():
    Base.metadata.create_all(engine)
    from app.datasets import ensure_versions

    ensure_versions()
    with DB.begin() as db:
        if not db.get(Migration, 2):
            from sqlalchemy import select
            from app.market import meta

            for r in db.scalars(select(Record).where(Record.kind == "replay")):
                if not r.data.get("dataset_version"):
                    r.data = {
                        **r.data,
                        "dataset_version": meta(r.data["symbol"])["sha256"],
                    }
            db.add(Migration(version=2, applied_at=now()))


class Observation(Base):
    __tablename__ = "eye_observations"
    __table_args__ = (UniqueConstraint("owner", "symbol"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON)
