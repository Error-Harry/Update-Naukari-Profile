"""Async SQLAlchemy engine + session factory."""

from __future__ import annotations

from typing import AsyncGenerator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _prepare_async_url(raw_url: str) -> tuple[str, dict]:
    """
    Convert a libpq-style Postgres URL into (asyncpg_url, connect_args).

    Neon/Supabase/Heroku often ship URLs with `sslmode=require` and
    `channel_binding=require` in the query string. asyncpg doesn't understand
    those parameters, so we strip the query and enable SSL via connect_args.
    """
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://") :]

    parsed = urlparse(raw_url)
    scheme = parsed.scheme
    if scheme == "postgresql":
        scheme = "postgresql+asyncpg"
    elif scheme != "postgresql+asyncpg":
        return raw_url, {}

    stripped = parsed._replace(scheme=scheme, query="")
    url = urlunparse(stripped)

    query = parsed.query.lower()
    connect_args: dict = {"server_settings": {"application_name": "naukri-updater"}}
    if "sslmode=require" in query or "sslmode=prefer" in query or "sslmode=verify" in query:
        connect_args["ssl"] = True
    return url, connect_args


_settings = get_settings()
_async_url, _connect_args = _prepare_async_url(_settings.database_url)
engine = create_async_engine(
    _async_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
