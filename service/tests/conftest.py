"""Test environment.

The backend is pinned to the SQLite fixture before anything imports `app`, because
`app.config.get_settings` is cached and `app.main` resolves settings at import time. The
fixture database is written to a throwaway directory rather than to `service/local/`, so a
test run never disturbs a fixture a developer is using.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="pepticraft-fixture-"))

os.environ["IGEM_DB_BACKEND"] = "sqlite"
os.environ["IGEM_SQLITE_PATH"] = str(_TMP / "pepticraft_local.sqlite3")
# Leave IGEM_SQLITE_FIXTURE unset so the repository's own SQL is used; it is resolved
# relative to the service root, not to the working directory.
os.environ.pop("IGEM_SQLITE_FIXTURE", None)
