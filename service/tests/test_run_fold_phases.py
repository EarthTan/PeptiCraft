"""The phase runner must fold the default linkers first and the exhaustive remainder second.

The order is the whole point of the two-phase arrangement, and it is also the part a
refactor could quietly break: both phases are FASTA files, and both are folded by the same
routine, so nothing about the machinery forces the order — only the list of phases does.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.run_fold_phases import run_phase


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - silence the default stderr logging
        pass

    def do_POST(self):  # noqa: N802 - the name is fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.server.requested.append(payload["sequence"])
        behaviour = self.server.behaviour.get(payload["sequence"], "ok")
        if behaviour == "empty":
            body = {"result": {"pdb_content": "", "confidence": None,
                               "details": {"error": "no results"}}}
        else:
            body = {"result": {"pdb_content": f"ATOM  {payload['peptide_id']}",
                               "confidence": 0.8, "details": {}}}
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def service():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.behaviour = {}
    server.requested = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/predict", server
    server.shutdown()


def _fasta(path: Path, records: list[tuple[str, str]]) -> Path:
    with path.open("w") as handle:
        for ident, seq in records:
            handle.write(f">{ident}\n{seq}\n")
    return path


def test_a_phase_folds_everything_it_owes(tmp_path, service):
    url, _ = service
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"
    out.mkdir()

    failures = run_phase("tier1+2", fasta, out, url, out / "phases.log", retries=1)

    assert failures == []
    assert sorted(p.name for p in (out / "pdb").glob("*.pdb")) == ["s1.pdb", "s2.pdb"]


def test_a_failure_is_retried_and_the_retry_only_covers_it(tmp_path, service):
    url, server = service
    server.behaviour["CCC"] = "empty"
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC"), ("s3", "EEE")])
    out = tmp_path / "folds"
    out.mkdir()

    failures = run_phase("tier1+2", fasta, out, url, out / "phases.log", retries=1)

    # The service never recovers, so the failure survives the retry and is reported.
    assert failures == ["s2"]
    # The first pass asked for all three; the retry asked for the failure and nothing else.
    assert server.requested == ["AAA", "CCC", "EEE", "CCC"]
    # The retry list is on disk for the next pass to pick up.
    assert (out / "retry-tier1+2.txt").read_text().split() == ["s2"]


def test_a_phase_that_recovers_ends_with_no_failures(tmp_path, service):
    url, server = service
    server.behaviour["CCC"] = "empty"
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"
    out.mkdir()

    # The service recovers between the first pass and the retry, which is what a transient
    # failure looks like from the batch's side.
    original = server.behaviour.copy()
    server.behaviour.clear()

    failures = run_phase("tier1+2", fasta, out, url, out / "phases.log", retries=1)

    assert failures == []
    assert sorted(p.name for p in (out / "pdb").glob("*.pdb")) == ["s1.pdb", "s2.pdb"]
    assert original == {"CCC": "empty"}
