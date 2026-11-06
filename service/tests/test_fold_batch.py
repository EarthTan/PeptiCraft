"""The folding batch must survive failures and resume from what is on disk.

A run of this batch lasts months, so the properties that keep it alive are worth more than
the properties that make one pass fast. Four of them are checked here: a sequence whose
prediction came back empty is a failure rather than an empty file, a failure leaves no file
behind so a later pass tries it again, a retry pass folds the failures rather than everything
else, and a service that is not ready yet stops the pass instead of marking the whole list as
failed.
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
    an exception to raise. Anything not named succeeds. `server.not_ready` makes the service
    refuse every request the way it does while the model is still loading.
    """

    def log_message(self, *args):  # noqa: D102 - silence the default stderr logging
        pass

    def do_GET(self):  # noqa: N802 - the name is fixed by BaseHTTPRequestHandler
        if self.path != "/health":
            self.send_error(404, "no such endpoint")
            return
        if getattr(self.server, "health_silent", False):
            # The service is busy with a prediction and cannot answer at all.
            self.close_connection = True
            return
        loading = getattr(self.server, "health_says_loading", False)
        loaded = (not loading) and not getattr(self.server, "not_ready", False)
        body = {"status": "healthy" if loaded else "loading",
                "tool_name": "OmegaFold", "version": "1", "model_loaded": loaded}
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):  # noqa: N802 - the name is fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.server.calls += 1
        # `not_ready_after` lets a test have the service stop answering partway through.
        stop_after = getattr(self.server, "not_ready_after", None)
        if getattr(self.server, "not_ready", False) or (
            stop_after is not None and self.server.calls > stop_after
        ):
            # The shape the real service returns before the weights are loaded.
            body = {"success": False, "peptide_id": payload.get("peptide_id"),
                    "sequence": payload.get("sequence"), "result": None,
                    "error": "Model not loaded"}
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
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
    server.not_ready = False
    server.not_ready_after = None
    server.health_silent = False
    server.health_says_loading = False
    server.calls = 0
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


def test_a_service_that_is_not_ready_does_not_fail_the_whole_list(tmp_path, service):
    """A service still loading its weights must stop the pass, not condemn the list.

    The batch used to treat the refusal as a failure of the sequence, which marked every
    sequence in the list as failed in one moment — and the next phase's failure list then
    overwrote that record, so the loss could not be seen afterwards.
    """
    url, server = service
    server.not_ready = True
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC"), ("s3", "EEE")])
    out = tmp_path / "folds"

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 0
    assert summary["failed"] == []
    assert summary["service_not_ready"] is True
    # Nothing is written, and no file claims the sequences were tried.
    assert not (out / "pdb").exists() or not list((out / "pdb").glob("*.pdb"))
    assert not (out / "failed.txt").exists()


def test_the_batch_waits_for_a_service_that_is_still_loading(tmp_path, service):
    """The service may finish loading while the batch waits for it."""
    url, server = service
    server.not_ready = True
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA")])
    out = tmp_path / "folds"

    def become_ready():
        import time as _time
        _time.sleep(0.3)
        server.not_ready = False

    threading.Thread(target=become_ready, daemon=True).start()

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["service_not_ready"] is False
    assert (out / "pdb" / "s1.pdb").exists()


def test_a_service_that_stops_answering_midway_leaves_the_rest_untouched(tmp_path, service):
    """A pass that is cut short must not overwrite the failures of an earlier pass."""
    url, server = service
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA"), ("s2", "CCC")])
    out = tmp_path / "folds"
    out.mkdir()
    # An earlier pass recorded a failure; it is the record of what is still outstanding.
    (out / "failed.txt").write_text("s0\n")
    # The service answers the first request and then refuses.
    server.not_ready_after = 1

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["service_not_ready"] is True
    # The sequence after the cut was never folded, and the earlier record survives,
    # because this pass never reached the end of its list.
    assert not (out / "pdb" / "s2.pdb").exists()
    assert (out / "failed.txt").read_text() == "s0\n"


def test_a_health_endpoint_that_does_not_answer_does_not_stop_the_batch(tmp_path, service):
    """A service busy with a prediction cannot answer its health endpoint, and is alive.

    The health endpoint is served by the same event loop that runs the prediction, so while
    a prediction is in flight it cannot be answered at all. Reading that silence as "the
    model is not loaded" would stop a batch that was about to work perfectly well.
    """
    url, server = service
    server.health_silent = True
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA")])
    out = tmp_path / "folds"

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["service_not_ready"] is False
    assert (out / "pdb" / "s1.pdb").exists()


def test_a_service_that_reports_the_model_as_loading_is_waited_for(tmp_path, service):
    """An answer that says the model is not loaded yet is a reason to keep waiting."""
    url, server = service
    server.health_says_loading = True
    fasta = _fasta(tmp_path / "a.fasta", [("s1", "AAA")])
    out = tmp_path / "folds"

    def become_ready():
        import time as _time
        _time.sleep(0.3)
        server.health_says_loading = False

    threading.Thread(target=become_ready, daemon=True).start()

    summary = run(str(fasta), str(out), url=url)

    assert summary["folded"] == 1
    assert summary["service_not_ready"] is False
