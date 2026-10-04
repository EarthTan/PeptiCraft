"""Runtime settings.

The database runs on a separate host and is reached by IP, so there is no localhost
fallback anywhere in this module. The shared pipeline helper (`iGEM-platform-main/src/
pipeline/db.py`) defaults to `127.0.0.1`, which is correct on the Ubuntu workstation but
wrong on a macOS development machine: a local Postgres does listen on 127.0.0.1 there, and
it has no `igem` role, so the failure surfaces as `role "igem" does not exist` rather than
as a connection error. A missing DSN here is therefore a hard error — unless the backend is
pinned to the local SQLite fixture, in which case no PostgreSQL connection is needed at all.

The remote instance is not always reachable: it lives behind a tunnel on a workstation that
is not always up. `IGEM_DB_BACKEND=auto` (the default) probes it once and, if the probe
fails, serves the bundled SQLite fixture instead so the API and the interface can still be
developed against. `postgres` and `sqlite` pin the backend and are what a deployment and a
test run use respectively. The fixture never carries real pipeline data; it is four seeded
constructs that exist to exercise the code paths.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `service/` — the directory holding `app/`, `sql/` and `local/`.
_SERVICE_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- database ---------------------------------------------------------
    # Either supply the full libpq connection string ...
    igem_pg_dsn: str | None = Field(default=None)
    # ... or supply the parts and let the validator assemble it.
    igem_pg_host: str | None = Field(default=None)
    igem_pg_port: int = Field(default=5432)
    igem_pg_db: str = Field(default="igem_peptides")
    igem_pg_user: str = Field(default="igem")
    igem_pg_password: str | None = Field(default=None)
    # Set to true only when the remote instance is deliberately reached through a local
    # tunnel. Leaving it false keeps the wrong-instance guard below active.
    igem_pg_allow_localhost: bool = Field(default=False)

    # A single query may not run longer than this. The enrichment table holds 377 M rows
    # in 130 GB; an unbounded planner mistake would otherwise pin a worker indefinitely.
    statement_timeout_ms: int = Field(default=60_000, ge=1_000, le=600_000)

    pg_pool_min_size: int = Field(default=1, ge=0)
    pg_pool_max_size: int = Field(default=8, ge=1)
    pg_pool_timeout_s: int = Field(default=15, ge=1)

    # --- backend selection and local fallback -----------------------------
    # `auto` probes PostgreSQL and falls back to the bundled SQLite fixture when the probe
    # fails. `postgres` never falls back (what a deployment wants: a dead database must be
    # visible, not masked). `sqlite` never touches PostgreSQL (what a test run wants).
    igem_db_backend: Literal["auto", "postgres", "sqlite"] = Field(default="auto")

    # Where the fixture database is written. Defaults to service/local/pepticraft_local.sqlite3.
    igem_sqlite_path: str | None = Field(default=None)
    # The SQL the fixture is built from, read only when the database file is absent.
    igem_sqlite_fixture: str | None = Field(default=None)

    # --- http -------------------------------------------------------------
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    # The Vite dev server runs on 127.0.0.1:5173.
    cors_origins: str = Field(default="http://127.0.0.1:5173,http://localhost:5173")

    # --- analysis ---------------------------------------------------------
    # `template` renders deterministic prose from real scores. `llm` is reserved and not
    # implemented yet; see app/services/analysis.py for the generator protocol.
    analysis_provider: str = Field(default="template")
    llm_base_url: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None)
    llm_model: str | None = Field(default=None)

    # --- derived ----------------------------------------------------------
    @model_validator(mode="after")
    def _assemble_dsn(self) -> "Settings":
        # With the backend pinned to the fixture there is nothing to connect to, so the
        # DSN requirement below is skipped rather than forcing a host onto a test run.
        if self.igem_db_backend == "sqlite" and not self.igem_pg_dsn and not self.igem_pg_host:
            object.__setattr__(self, "dsn", "")
            return self

        if self.igem_pg_dsn:
            dsn = self.igem_pg_dsn
        else:
            if not self.igem_pg_host:
                raise ValueError(
                    "IGEM_PG_HOST is required when IGEM_PG_DSN is not set. The database "
                    "runs on a separate machine and is reached by IP; there is no "
                    "localhost fallback by design."
                )
            if not self.igem_pg_password:
                raise ValueError(
                    "IGEM_PG_PASSWORD is required when IGEM_PG_DSN is not set."
                )
            dsn = (
                f"host={self.igem_pg_host} port={self.igem_pg_port} "
                f"dbname={self.igem_pg_db} user={self.igem_pg_user} "
                f"password={self.igem_pg_password} "
                f"connect_timeout=10 application_name=pepticraft_service"
            )
        # Guard against the fallback mistake described in the module docstring.
        flat = dsn.replace(" ", "")
        if not self.igem_pg_allow_localhost and (
            "host=localhost" in flat or "host=127.0.0.1" in flat
        ):
            raise ValueError(
                "The DSN points at localhost. The iGEM database lives on a separate "
                "machine (Tailscale 100.69.116.8 by default) and a local Postgres without "
                "the `igem` role is usually what answers on 127.0.0.1. Set "
                "IGEM_PG_ALLOW_LOCALHOST=true if this is a deliberate SSH tunnel."
            )
        object.__setattr__(self, "dsn", dsn)
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlite_file(self) -> Path:
        if self.igem_sqlite_path:
            return Path(self.igem_sqlite_path).expanduser()
        return _SERVICE_ROOT / "local" / "pepticraft_local.sqlite3"

    @property
    def sqlite_fixture_file(self) -> Path:
        if self.igem_sqlite_fixture:
            return Path(self.igem_sqlite_fixture).expanduser()
        return _SERVICE_ROOT / "local" / "fixture_local.sql"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
