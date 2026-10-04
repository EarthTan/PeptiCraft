"""Database access.

Two backends sit behind one interface. The normal one is a connection pool over the remote
Postgres instance; the fallback is a local SQLite fixture that is used when that instance
cannot be reached and `IGEM_DB_BACKEND` allows it. Repositories call `query`, `query_one`,
`count` and `ping` and never learn which backend answered.

Postgres session tuning, unchanged: `peptide_enrichment` holds 377 M rows in 130 GB and the
planner will occasionally prefer a sequential scan, which turns a millisecond lookup into a
minute-long sweep. `SET enable_seqscan = off` and `SET enable_bitmapscan = off` push it onto
the `(peptide_id, tool)` primary key instead. Those two settings are applied **only on
request** rather than to every connection: they are helpful on the enrichment table and
actively unhelpful on `constructs`, which holds 496 rows in 744 kB and is cheapest to read
with a plain sequential scan. Callers that touch the enrichment table ask for
`force_index=True`; everything else leaves the planner alone.

Connections are read-only on both backends. The service never writes; migrations and imports
ship as separate scripts rather than as application code paths.

Backend selection, from `IGEM_DB_BACKEND`:

    postgres   never fall back. A dead database must be visible, which is what a deployment
               wants.
    sqlite     never touch Postgres, which is what a test run wants.
    auto       probe Postgres once at first use. If the probe fails, serve the fixture and
               record why; the reason travels to `/api/health`. A connection that dies later
               mid-session is also caught and the switch happens then.

`auto` is the default because the remote instance is a workstation behind a tunnel that is
not always up, and an unreachable database should degrade the data source rather than take
the whole interface down. The fallback is never silent: it is logged at warning level, it is
reported by `/api/health`, and `get_backend()` names it.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import psycopg
import psycopg_pool
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import sqlite_backend
from .config import get_settings

log = logging.getLogger("pepticraft.db")

_pool: ConnectionPool | None = None
_backend: str | None = None
_fallback_reason: str | None = None
_backend_lock = threading.RLock()

# `ConnectionPool.connection()` raises these rather than a psycopg error when the pool cannot
# hand out a connection, and they mean the same thing to a caller: the database is not usable
# right now. Looked up defensively so a psycopg_pool version that lacks one still imports.
_POOL_ERRORS: tuple[type[BaseException], ...] = tuple(
    exc for exc in (
        getattr(psycopg_pool, "PoolTimeout", None),
        getattr(psycopg_pool, "PoolClosed", None),
    ) if isinstance(exc, type)
)

POSTGRES = "postgres"
SQLITE = "sqlite"


class DatabaseUnavailable(RuntimeError):
    """The database could not be reached at all (network, auth, wrong instance)."""


class QueryFailed(RuntimeError):
    """The database was reachable but the statement did not complete."""


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _probe_postgres() -> None:
    """Reach the remote instance once, cheaply, and raise if it is not there.

    A direct connect with a short timeout rather than a pool checkout: the point is to learn
    quickly whether the host answers, and a pool checkout would wait out the full pool
    timeout while the startup path blocks on it.
    """
    settings = get_settings()
    if not settings.dsn:
        raise DatabaseUnavailable("no PostgreSQL DSN is configured")
    try:
        with psycopg.connect(settings.dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error as exc:
        raise DatabaseUnavailable(str(exc)) from exc


def _select_backend() -> None:
    global _backend, _fallback_reason
    if _backend is not None:
        return
    with _backend_lock:
        if _backend is not None:
            return
        settings = get_settings()
        wanted = settings.igem_db_backend

        if wanted == SQLITE:
            sqlite_backend.ensure_fixture()
            _fallback_reason = "IGEM_DB_BACKEND=sqlite"
            _backend = SQLITE
            log.info("serving the local SQLite fixture (%s)", settings.sqlite_file)
            return

        if wanted == POSTGRES:
            _backend = POSTGRES
            return

        try:
            _probe_postgres()
        except DatabaseUnavailable as exc:
            sqlite_backend.ensure_fixture()
            _fallback_reason = f"PostgreSQL unreachable at first use: {exc}"
            _backend = SQLITE
            log.warning(
                "PostgreSQL unreachable (%s); serving the local SQLite fixture at %s instead",
                exc, settings.sqlite_file,
            )
            return
        _backend = POSTGRES


def _use_sqlite(reason: str) -> None:
    global _backend, _fallback_reason
    with _backend_lock:
        if _backend == SQLITE:
            return
        sqlite_backend.ensure_fixture()
        _fallback_reason = reason
        _backend = SQLITE
        log.warning("switched to the local SQLite fixture: %s", reason)


def get_backend() -> str:
    """Which backend is answering, `postgres` or `sqlite`."""
    _select_backend()
    return _backend or POSTGRES


def get_fallback_reason() -> str | None:
    """Why the fixture is in use, or None when Postgres is answering."""
    _select_backend()
    return _fallback_reason if _backend == SQLITE else None


# ---------------------------------------------------------------------------
# Connection pool (Postgres)
# ---------------------------------------------------------------------------

def _configure(conn: psycopg.Connection) -> None:
    """Applied to every pooled connection, once, on creation."""
    settings = get_settings()
    conn.read_only = True
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = {settings.statement_timeout_ms}")
    conn.commit()


def init_pool() -> ConnectionPool | None:
    global _pool
    _select_backend()
    if _backend == SQLITE:
        return None
    if _pool is not None:
        return _pool
    settings = get_settings()
    _pool = ConnectionPool(
        conninfo=settings.dsn,
        min_size=settings.pg_pool_min_size,
        max_size=settings.pg_pool_max_size,
        timeout=settings.pg_pool_timeout_s,
        configure=_configure,
        kwargs={"row_factory": dict_row},
        open=False,
        name="pepticraft",
    )
    _pool.open(wait=False)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool | None:
    return _pool if _pool is not None else init_pool()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _postgres_fetch(
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None,
    *,
    force_index: bool,
    one: bool,
) -> Any:
    try:
        with get_pool().connection() as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                if force_index:
                    cur.execute("SET enable_seqscan = off")
                    cur.execute("SET enable_bitmapscan = off")
                try:
                    cur.execute(sql, params)
                    return cur.fetchone() if one else cur.fetchall()
                finally:
                    if force_index:
                        cur.execute("RESET enable_seqscan")
                        cur.execute("RESET enable_bitmapscan")
    except psycopg.OperationalError as exc:  # connect / auth / network
        raise DatabaseUnavailable(str(exc)) from exc
    except _POOL_ERRORS as exc:  # pool exhausted or closed
        raise DatabaseUnavailable(f"connection pool unavailable: {exc}") from exc
    except psycopg.Error as exc:  # statement level
        raise QueryFailed(str(exc)) from exc


def _sqlite_fetch(
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None,
    *,
    force_index: bool,
    one: bool,
) -> Any:
    try:
        rows = sqlite_backend.query(sql, params, force_index=force_index)
    except sqlite3.OperationalError as exc:
        # A missing or unreadable fixture is the SQLite equivalent of an unreachable host,
        # so it maps to the same status code.
        raise DatabaseUnavailable(f"local fallback database unusable: {exc}") from exc
    except sqlite3.DatabaseError as exc:
        raise QueryFailed(str(exc)) from exc
    return (rows[0] if rows else None) if one else rows


def _run(
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None,
    *,
    force_index: bool = False,
    one: bool = False,
) -> Any:
    _select_backend()
    if _backend == SQLITE:
        return _sqlite_fetch(sql, params, force_index=force_index, one=one)

    try:
        return _postgres_fetch(sql, params, force_index=force_index, one=one)
    except DatabaseUnavailable as exc:
        # In `auto` mode a connection that dies mid-session degrades to the fixture rather
        # than failing the request. A pinned backend keeps the failure visible.
        if get_settings().igem_db_backend != "auto":
            raise
        _use_sqlite(f"PostgreSQL became unreachable mid-session: {exc}")
        return _sqlite_fetch(sql, params, force_index=force_index, one=one)


@contextmanager
def cursor(force_index: bool = False) -> Iterator[psycopg.Cursor]:
    """Yield a dict-row cursor bound to a pooled Postgres connection.

    Postgres only: the SQLite fallback opens a short-lived connection per statement instead,
    because it has no pool and a per-statement connection over a two-row file is cheaper than
    holding one open. Callers that need to work on both backends use `query` / `query_one`.
    """
    _select_backend()
    if _backend == SQLITE:
        raise RuntimeError(
            "cursor() is a PostgreSQL-only entry point; use query() or query_one(), which "
            "dispatch to whichever backend is active"
        )
    try:
        with get_pool().connection() as conn:  # type: ignore[union-attr]
            with conn.cursor() as cur:
                if force_index:
                    cur.execute("SET enable_seqscan = off")
                    cur.execute("SET enable_bitmapscan = off")
                try:
                    yield cur
                finally:
                    if force_index:
                        cur.execute("RESET enable_seqscan")
                        cur.execute("RESET enable_bitmapscan")
    except psycopg.OperationalError as exc:  # connect / auth / network
        raise DatabaseUnavailable(str(exc)) from exc
    except _POOL_ERRORS as exc:
        raise DatabaseUnavailable(f"connection pool unavailable: {exc}") from exc
    except psycopg.Error as exc:  # statement level
        raise QueryFailed(str(exc)) from exc


def query(sql: str, params: Sequence[Any] | dict[str, Any] | None = None,
          *, force_index: bool = False) -> list[dict[str, Any]]:
    return _run(sql, params, force_index=force_index, one=False)


def query_one(sql: str, params: Sequence[Any] | dict[str, Any] | None = None,
              *, force_index: bool = False) -> dict[str, Any] | None:
    return _run(sql, params, force_index=force_index, one=True)


def ping() -> dict[str, Any]:
    """Cheap liveness probe used by /api/health."""
    if get_backend() == SQLITE:
        return sqlite_backend.ping()
    row = query_one("SELECT version() AS version, current_database() AS db, now() AS ts")
    return row or {}


def count(sql: str, params: Sequence[Any] | dict[str, Any] | None = None,
          *, force_index: bool = False) -> int:
    row = query_one(sql, params, force_index=force_index)
    if not row:
        return 0
    return int(next(iter(row.values())))
