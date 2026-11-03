"""The folding batch must survive failures and resume from what is on disk.

A run of this batch lasts months, so the properties that keep it alive are worth more than
the properties that make one pass fast. Three of them are checked here: a sequence whose
prediction came back empty is a failure rather than an empty file, a failure leaves no file
behind so a later pass tries it again, and a retry pass folds the failures rather than
everything else.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.fold_batch import fold, read_fasta, run


class _Handler(BaseHTTPRequestHandler):
    """A stand-in for the OmegaFold service.

    `server.behaviour` maps a sequence to one of: a coordinate string, an empty result, or
    an exception to raise. Anything not named succeeds.
    """

    def log_message(self, *args):  # noqa: D102 - silence the default stderr logging
        pass

    def do_POST(self):  # noqa: N802 - the name is fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        behaviour = self.server.behaviour.get(payload["sequence"], "ok")
        if behaviour == "boom":
            self.send_error(500, "prediction exploded")
            return
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/predict", server
    server.shutdown()


def _fasta(path: Path, records: list[tuple[str, str]]) -> Path:
    with path.open("w") as handle:
        for ident, seq in records:
            handle.write(f">{ident}\n{seq}\n")
    return path


def test_read_fasta_handles_plain_and_gzip(tmp_path):
    import gzip

    plain = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    records = list(read_fasta(str(plain)))
    assert records == [("s1", "AAA"), ("s2", "CCC")]

    gz = tmp_path / "b.fasta.gz"
    with gzip.open(gz, "wt") as handle:
        handle.write(">s1\nAAA\n>s2\nCCC\n")
    assert list(read_fasta(str(gz))) == records


def test_header_takes_the_first_token_only(tmp_path):
    path = _fasta(tmp_path / "a.fasta", [("s1", "AAA")])
    path.write_text(">s1 extra description here\nAAA\n")
    assert list(read_fasta(str(path))) == [("s1", "AAA")]


def test_a_successful_prediction_writes_a_file_and_a_record(tmp_path, service):
    url, _ = service
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 2
    assert summary["failed"] == []
    assert (out / "pdb" / "s1.pdb").exists()
    assert (out / "pdb" / "s2.pdb").exists()
    records = [json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()]
    assert [r["id"] for r in records] == ["s1", "s2"]
    assert records[0]["aa"] == 3


def test_an_empty_result_is_a_failure_and_writes_no_file(tmp_path, service):
    url, server = service
    server.behaviour["CCC"] = "empty"
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["failed"] == ["s2"]
    # The whole point: a failure must leave no file, or the next pass would skip it as done.
    assert not (out / "pdb" / "s2.pdb").exists()
    assert (out / "failed.txt").read_text().split() == ["s2"]
    # The failure is also accumulated, so a batch that ran for weeks does not lose it.
    assert "s2" in (out / "failed.log").read_text()


def test_a_request_that_raises_is_a_failure(tmp_path, service):
    url, server = service
    server.behaviour["AAA"] = "boom"
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["failed"] == ["s1"]
    assert not (out / "pdb" / "s1.pdb").exists()


def test_a_second_pass_picks_up_what_the_first_left_out(tmp_path, service):
    url, server = service
    server.behaviour["CCC"] = "empty"
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"

    run(str(fasta), str(out), url=url)
    assert len(list((out / "pdb").glob("*.pdb"))) == 1

    # The service recovers; the second pass folds only what is missing.
    server.behaviour.clear()
    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["failed"] == []
    assert sorted(p.name for p in (out / "pdb").glob("*.pdb")) == ["s1.pdb", "s2.pdb"]


def test_a_retry_pass_folds_the_failures_and_nothing_else(tmp_path, service):
    url, server = service
    server.behaviour["CCC"] = "empty"
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC"), ("s3", "EEE")])
    out = tmp_path / "folds"

    run(str(fasta), str(out), url=url)
    server.behaviour.clear()

    retry_file = out / "retry.txt"
    retry_file.write_text("s2\n")

    summary = run(str(fasta), str(out), url=url, retry=str(retry_file))

    # Only the named sequence is folded, and it is folded even though s1 and s3 are done.
    assert summary["folded"] == 1
    assert len(list((out / "pdb").glob("*.pdb"))) == 3
    assert [json.loads(line)["id"]
            for line in (out / "records.jsonl").read_text().splitlines()] == ["s1", "s3", "s2"]


def test_a_retry_ignores_identifiers_that_are_not_in_the_fasta(tmp_path, service):
    url, _ = service
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA")])
    out = tmp_path / "folds"
    out.mkdir()
    retry_file = out / "retry.txt"
    retry_file.write_text("s1\nnot-a-real-id\n")

    summary = run(str(fasta), str(out), url=url, retry=str(retry_file))

    assert summary["folded"] == 1
    assert summary["failed"] == []


def test_fold_returns_the_elapsed_time_and_the_payload(tmp_path, service):
    url, _ = service
    elapsed, payload = fold("AAA", "s1", url=url)
    assert elapsed >= 0
    assert payload["result"]["pdb_content"] == "ATOM  s1"


def test_two_phases_cover_the_whole_set_in_the_right_order(tmp_path, service):
    """The phase runner must put the default linkers first and the remainder second."""
    from scripts.run_fold_phases import PHASES

    assert [name for name, _ in PHASES] == ["tier1+2", "full"]
    assert PHASES[0][1] == "tier2_two_linkers.fasta.gz"
    assert PHASES[1][1] == "all_by_length.fasta"
