"""Publishing must obey the store's request quota and keep the index consistent with it.

The store answers a burst of requests with 429 and a five-minute quota, so an uploader that
does not pace itself uploads the first thousand files and then fails every one after that,
forever. Two properties are therefore worth pinning down: the uploader waits rather than
issuing a request that will be refused, and the index is published only once the files it
names are in the store.
"""
from __future__ import annotations

import io
import json
import threading
import time
import urllib.error
from pathlib import Path

import pytest

from scripts.publish_structures import (
    RateLimiter,
    RestUploader,
    content_type_for,
    refresh_token,
    token_expiry,
    upload_with_rest,
    wrangler_commands,
)


def test_the_limiter_admits_no_more_than_the_budget_in_the_window():
    """The request that would exceed the window's budget must wait, not be issued."""
    limiter = RateLimiter(limit=3, window=60.0, target=1.0)
    for _ in range(3):
        limiter.acquire()

    finished = threading.Event()

    def fourth():
        limiter.acquire()
        finished.set()

    thread = threading.Thread(target=fourth, daemon=True)
    thread.start()
    # The fourth request cannot be issued until the window rolls over, so a short wait is
    # not enough for it to finish.
    assert not finished.wait(timeout=0.5)


def test_the_limiter_is_shared_across_threads():
    limiter = RateLimiter(limit=50, window=60.0, target=1.0)
    granted = []
    lock = threading.Lock()

    def worker():
        limiter.acquire()
        with lock:
            granted.append(1)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(granted) == 50


def test_a_window_that_has_passed_frees_its_budget():
    limiter = RateLimiter(limit=2, window=0.3, target=1.0)
    limiter.acquire()
    limiter.acquire()
    time.sleep(0.4)
    # The first two are now outside the window, so two more are admitted without waiting.
    started = time.monotonic()
    limiter.acquire()
    limiter.acquire()
    assert time.monotonic() - started < 0.3


class _Uploader:
    """Stands in for the REST uploader, recording what it was asked to store."""

    def __init__(self, fail_keys=(), refuse_keys=()):
        self.fail_keys = set(fail_keys)
        self.refuse_keys = set(refuse_keys)
        self.stored: list[str] = []
        self.order: list[str] = []
        self.workers = 4

    def put(self, key, payload, content_type):
        self.order.append(key)
        if key in self.fail_keys:
            return key, False, "500 boom"
        if key in self.refuse_keys:
            return key, False, "429 refused"
        self.stored.append(key)
        return key, True, "etag"


def _files(tmp_path: Path, count: int) -> list[tuple[str, Path]]:
    out = []
    for i in range(count):
        path = tmp_path / f"s{i}.pdb"
        path.write_text(f"ATOM  s{i}\n")
        out.append((f"structures/s{i}.pdb", path))
    return out


def test_the_index_is_uploaded_after_the_files_it_names(tmp_path):
    uploader = _Uploader()
    structures = tmp_path / "structures.json"
    structures.write_text('{"count": 1}')
    lookup = tmp_path / "structure_lookup.json"
    lookup.write_text('{"a|b|c": "s0"}')
    files = _files(tmp_path, 3) + [
        ("structures.json", structures),
        ("structure_lookup.json", lookup),
    ]

    upload_with_rest(uploader, files, None, index_keys=frozenset({
        "structures.json", "structure_lookup.json"}))

    assert set(uploader.stored) == {
        "structures/s0.pdb", "structures/s1.pdb", "structures/s2.pdb",
        "structures.json", "structure_lookup.json",
    }
    # The index must be the last thing stored, so that it never names an absent file.
    assert uploader.order[-2:] == ["structures.json", "structure_lookup.json"]


def test_a_failed_coordinate_file_withholds_the_index(tmp_path):
    uploader = _Uploader(fail_keys={"structures/s1.pdb"})
    structures = tmp_path / "structures.json"
    structures.write_text('{"count": 3}')
    lookup = tmp_path / "structure_lookup.json"
    lookup.write_text("{}")
    files = _files(tmp_path, 3) + [
        ("structures.json", structures),
        ("structure_lookup.json", lookup),
    ]

    upload_with_rest(uploader, files, None, index_keys=frozenset({
        "structures.json", "structure_lookup.json"}))

    assert "structures/s1.pdb" not in uploader.stored
    assert "structures.json" not in uploader.stored
    assert "structure_lookup.json" not in uploader.stored


def test_a_failed_file_is_not_recorded_as_uploaded(tmp_path):
    uploader = _Uploader(fail_keys={"structures/s1.pdb"})
    state_path = tmp_path / "state.json"
    upload_with_rest(uploader, _files(tmp_path, 3), state_path)

    state = json.loads(state_path.read_text())
    assert "structures/s0.pdb" in state
    assert "structures/s1.pdb" not in state
    assert "structures/s2.pdb" in state


def test_a_file_already_stored_is_not_uploaded_again(tmp_path):
    uploader = _Uploader()
    state_path = tmp_path / "state.json"
    files = _files(tmp_path, 3)

    upload_with_rest(uploader, files, state_path)
    assert len(uploader.stored) == 3

    again = _Uploader()
    upload_with_rest(again, files, state_path)
    assert again.stored == []


def test_content_types():
    assert content_type_for(Path("a.pdb")) == "chemical/x-pdb"
    assert content_type_for(Path("a.json")) == "application/json"
    assert content_type_for(Path("a.bin")) == "application/octet-stream"


def test_the_rest_uploader_retries_a_refused_request(monkeypatch):
    """A 429 is a rate limit, not a verdict: the same file succeeds later."""
    attempts = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"result": {"etag": "abc"}}).encode()

    def fake_urlopen(request, timeout=None):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"rate limited"))
        return _Response()

    monkeypatch.setattr("scripts.publish_structures.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.publish_structures.time.sleep", lambda _s: None)

    uploader = RestUploader("bucket", "account", "token", workers=1)
    key, ok, _ = uploader.put("structures/s0.pdb", b"ATOM", "chemical/x-pdb")

    assert ok
    assert key == "structures/s0.pdb"
    assert len(attempts) == 2


def test_a_non_rate_limit_error_is_not_retried(monkeypatch):
    attempts = []

    def fake_urlopen(request, timeout=None):
        attempts.append(request.full_url)
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b"forbidden"))

    monkeypatch.setattr("scripts.publish_structures.urllib.request.urlopen", fake_urlopen)

    uploader = RestUploader("bucket", "account", "token", workers=1)
    key, ok, detail = uploader.put("structures/s0.pdb", b"ATOM", "chemical/x-pdb")

    assert not ok
    assert "403" in detail
    assert len(attempts) == 1


def test_a_dropped_connection_is_retried(monkeypatch):
    """A connection the proxy drops mid-request says nothing about the file."""
    attempts = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"result": {"etag": "abc"}}).encode()

    def fake_urlopen(request, timeout=None):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise urllib.error.URLError(
                OSError(5, "EOF occurred in violation of protocol"))
        return _Response()

    monkeypatch.setattr("scripts.publish_structures.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.publish_structures.time.sleep", lambda _s: None)

    uploader = RestUploader("bucket", "account", "token", workers=1)
    key, ok, _ = uploader.put("structures/s0.pdb", b"ATOM", "chemical/x-pdb")

    assert ok
    assert key == "structures/s0.pdb"
    assert len(attempts) == 2


def test_a_connection_that_keeps_dropping_is_reported(monkeypatch):
    """The retries are bounded; a file that never gets through is a failure."""
    attempts = []

    def fake_urlopen(request, timeout=None):
        attempts.append(request.full_url)
        raise urllib.error.URLError(OSError(5, "EOF occurred in violation of protocol"))

    monkeypatch.setattr("scripts.publish_structures.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.publish_structures.time.sleep", lambda _s: None)

    uploader = RestUploader("bucket", "account", "token", workers=1)
    key, ok, detail = uploader.put("structures/s0.pdb", b"ATOM", "chemical/x-pdb")

    assert not ok
    assert "EOF" in detail
    assert len(attempts) == 6


def test_an_expired_token_is_renewed_and_the_upload_retried(monkeypatch):
    """A batch that outlives the OAuth grant must renew it rather than stop."""
    attempts = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"result": {"etag": "abc"}}).encode()

    def fake_urlopen(request, timeout=None):
        attempts.append(request.headers.get("Authorization"))
        if len(attempts) == 1:
            raise urllib.error.HTTPError(
                request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"expired"))
        return _Response()

    monkeypatch.setattr("scripts.publish_structures.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.publish_structures.refresh_token", lambda: "new")
    monkeypatch.setattr("scripts.publish_structures.time.sleep", lambda _s: None)

    uploader = RestUploader("bucket", "account", "old", workers=1)
    key, ok, _ = uploader.put("structures/s0.pdb", b"ATOM", "chemical/x-pdb")

    assert ok
    # The second attempt carries the renewed token, not the one that was refused.
    assert attempts == ["Bearer old", "Bearer new"]


def test_an_expired_token_that_cannot_be_renewed_is_reported(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"expired"))

    monkeypatch.setattr("scripts.publish_structures.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.publish_structures.refresh_token", lambda: None)

    uploader = RestUploader("bucket", "account", "Bearer old", workers=1)
    key, ok, detail = uploader.put("structures/s0.pdb", b"ATOM", "chemical/x-pdb")

    assert not ok
    assert "401" in detail


def test_the_expiry_is_read_from_the_wrangler_config(tmp_path, monkeypatch):
    config = tmp_path / "default.toml"
    config.write_text(
        'oauth_token = "abc"\n'
        'expiration_time = "2026-11-03T11:49:03.034Z"\n'
    )
    monkeypatch.setattr("scripts.publish_structures.WRANGLER_CONFIG", config)

    expiry = token_expiry()
    assert expiry is not None
    assert expiry.year == 2026
    assert expiry.hour == 11


def test_a_config_without_an_expiry_reads_as_unknown(tmp_path, monkeypatch):
    config = tmp_path / "default.toml"
    config.write_text('oauth_token = "abc"\n')
    monkeypatch.setattr("scripts.publish_structures.WRANGLER_CONFIG", config)
    assert token_expiry() is None


def test_the_cached_wrangler_is_preferred_over_the_npx_wrapper(tmp_path, monkeypatch):
    """The direct binary needs no registry access, so it is tried first."""
    cache = tmp_path / ".npm/_npx/abc/node_modules/.bin"
    cache.mkdir(parents=True)
    wrangler = cache / "wrangler"
    wrangler.write_text("#!/bin/sh\n")
    wrangler.chmod(0o755)

    monkeypatch.setattr("scripts.publish_structures.Path.home", lambda: tmp_path)

    commands = wrangler_commands()
    assert commands[0] == [str(wrangler)]
    assert len(commands[0]) == 1
    for command in commands[1:]:
        assert command[-1] == "wrangler"


def test_no_cached_wrangler_leaves_the_npx_wrapper(tmp_path, monkeypatch):
    """With an empty cache no direct binary is offered, only the wrapper."""
    (tmp_path / ".npm/_npx").mkdir(parents=True)
    monkeypatch.setattr("scripts.publish_structures.Path.home", lambda: tmp_path)

    for command in wrangler_commands():
        assert len(command) > 1
        assert command[-1] == "wrangler"


def test_a_silent_renewal_returns_the_new_token(tmp_path, monkeypatch):
    """Wrangler refreshes its own token; the uploader only has to notice."""
    config = tmp_path / "default.toml"
    config.write_text('oauth_token = "old"\n')
    monkeypatch.setattr("scripts.publish_structures.WRANGLER_CONFIG", config)

    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append(command)
        config.write_text('oauth_token = "new"\n')
        return Result()

    monkeypatch.setattr("scripts.publish_structures.subprocess.run", fake_run)
    monkeypatch.setattr(
        "scripts.publish_structures.wrangler_commands",
        lambda: [["/opt/homebrew/bin/npx", "wrangler"]],
    )

    assert refresh_token() == "new"
    assert calls[0][-1] == "whoami"


def test_a_renewal_that_changes_nothing_is_not_a_renewal(tmp_path, monkeypatch):
    """A command that leaves the token alone means the renewal did not happen."""
    config = tmp_path / "default.toml"
    config.write_text('oauth_token = "same"\n')
    monkeypatch.setattr("scripts.publish_structures.WRANGLER_CONFIG", config)

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        "scripts.publish_structures.subprocess.run",
        lambda command, **kwargs: Result(),
    )
    monkeypatch.setattr(
        "scripts.publish_structures.wrangler_commands",
        lambda: [["/opt/homebrew/bin/npx", "wrangler"]],
    )

    assert refresh_token() is None


def test_a_missing_wrangler_is_reported_rather_than_raised(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.publish_structures.wrangler_commands", lambda: [])
    assert refresh_token() is None
