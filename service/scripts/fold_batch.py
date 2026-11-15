"""Fold every sequence in a FASTA through the OmegaFold service, resumably.

    python scripts/fold_batch.py --fasta <pack>/fasta/all_by_length.fasta --out <folds>

Why this exists
---------------
A structure is a function of the fused sequence alone, and a fused sequence is long enough
that folding them one at a time is the only option the machine permits. OmegaFold here is a
HTTP service rather than a command, so the batch is a client: it reads a FASTA, sends one
sequence at a time, and writes one coordinate file per sequence.

Resumability is the property that makes a run of this length possible at all. A prediction
costs anywhere from a second and a half to twenty minutes, and the batch is expected to
outlive any single session of the machine hosting it. So the presence of
`<out>/pdb/<structure_id>.pdb` is the record of what has been done, and the presence of that
file is the only thing consulted before a sequence is sent. Nothing else — not the log, not
a checkpoint file — is needed to resume, and nothing else can be out of step with the
coordinates on disk.

Failure handling
-----------------
Three failures are possible and they are not the same kind. A request can fail outright, in
which case the sequence produced no file and is simply absent from the output directory, and
the batch carries on. A request can also come back successfully with an empty coordinate
string, which is what the service returns when the pipeline raised or produced nothing; that
case is recorded as a failure rather than written as an empty file, because an empty file
would look complete to every later step. And the service can be not ready yet, which is not a
failure of any sequence but of the service itself: the model is still loading, so every
request is refused with the same message. That third case is the one the batch must not treat
as a failure, because it would mark an entire list as failed in a single moment — and the
list it is working through is then overwritten by the next phase's failures, so the loss is
invisible afterwards.

The distinction matters because these batches run for weeks on a machine that is started and
stopped by other means. A service that is not ready is a condition to wait for, not a verdict
on ten thousand sequences.

Failures are collected in two files. `failed.txt` holds the failures of the most recent
pass, and is what a caller retries from. `failed.log` accumulates every failure with a
timestamp, so that a sequence which failed once in a batch that ran for three weeks is still
visible afterwards. A long run should not be able to lose a failure quietly.

Retrying
--------
`--retry <file>` folds only the identifiers listed in that file, rather than the pending
ones. The point is that the batch treats a failure as ordinary — the run continues, the
sequence is absent, and a later pass will pick it up — which is right for a short batch and
wrong for a long one, where the gap between two passes can be weeks. A retry pass closes
that gap without a second process, and because it is a pass of its own it costs only the
sequences that actually failed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import time
import urllib.request
from typing import Iterator

DEFAULT_URL = "http://127.0.0.1:8204/predict"


def read_fasta(path: str) -> Iterator[tuple[str, str]]:
    """Yield `(identifier, sequence)` for every record, in file order.

    The identifier is the first whitespace-delimited token of the header, because that is the
    token OmegaFold takes the output filename from; anything after it is ignored.
    """
    opener = gzip.open if path.endswith(".gz") else open
    header, buf = None, []
    with opener(path, "rt") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header:
                    yield header, "".join(buf)
                header, buf = line[1:].split()[0], []
            else:
                buf.append(line)
    if header:
        yield header, "".join(buf)


def fold(seq: str, ident: str, url: str = DEFAULT_URL, timeout: int = 3600) -> tuple[float, dict]:
    """Ask the service for one structure. Returns the elapsed seconds and the response."""
    body = json.dumps({"sequence": seq, "peptide_id": ident}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    return time.time() - t0, payload


def _failure_reason(payload: dict) -> str:
    """What the service said went wrong, in one line.

    The service reports a failure inside the result rather than as an HTTP error: a pipeline
    that raised comes back as a normal response with an empty coordinate string and a
    `details` object carrying the message. An empty result with no message is still a
    failure, and saying so is more useful than the empty string.
    """
    result = payload.get("result") or {}
    details = result.get("details") or {}
    return str(details.get("error") or "no coordinates returned")


def _service_not_ready(payload: dict) -> bool:
    """Whether the service refused the request because it is not loaded yet.

    The service answers a request that arrives before the model has finished loading with a
    refusal that carries the reason, and the reason names the model rather than the sequence.
    Such a refusal says nothing about the sequence, so recording it as that sequence's
    failure would be a statement about the service's readiness mistaken for a statement
    about the peptide.
    """
    error = str(payload.get("error") or "").lower()
    details = payload.get("result") or {}
    nested = str((details.get("details") or {}).get("error") or "").lower()
    for text in (error, nested):
        if "not loaded" in text or "not checked yet" in text:
            return True
    return False


def wait_for_service(url: str, timeout: float = 300.0, interval: float = 5.0) -> bool:
    """Wait until the service reports that its model is loaded, or give up.

    The service binds its port before the weights are loaded, so a port that answers is not
    evidence that the model is ready to predict. Its health endpoint is: it says whether the
    model is loaded. Asking for a prediction instead would work too, but it would spend a
    real prediction to find out — on a machine whose every second of the GPU is accounted
    for, that is not a question worth asking.

    The health endpoint cannot be served while a prediction is running, because the model is
    called synchronously inside the request handler and the event loop is busy for the whole
    of it. A timeout therefore says nothing about readiness — the service is busy with a
    prediction, which means it is alive — so a timeout is taken as readiness. Only an answer
    that plainly reports the model as unloaded is a reason to keep waiting.
    """
    health = url.rsplit("/", 1)[0] + "/health"
    deadline = time.time() + timeout
    while True:
        try:
            with urllib.request.urlopen(health, timeout=10) as resp:
                payload = json.loads(resp.read())
        except Exception:
            # No answer. The service is busy with a prediction, which means it is alive.
            return True
        if payload.get("model_loaded") is True or payload.get("status") == "healthy":
            return True
        if payload.get("model_loaded") is False or payload.get("status") == "loading":
            if time.time() >= deadline:
                return False
            time.sleep(min(interval, max(0.0, deadline - time.time())))
            continue
        # An answer that says neither way is not evidence that the model is unloaded.
        return True


def run(
    fasta: str,
    out: str,
    url: str = DEFAULT_URL,
    limit: int = 0,
    budget: float = 0.0,
    retry: str | None = None,
) -> dict:
    """Fold sequences into `out`. Returns a summary.

    By default every sequence in `fasta` that has no coordinate file yet is folded. When
    `retry` names a file of identifiers, only those identifiers are folded, and identifiers
    that already have a file are folded again — which is how a failed prediction, or one whose
    file was written by a run that died before it was known to be good, is given a second
    chance without rebuilding the pending list by hand.
    """
    os.makedirs(out, exist_ok=True)
    pdb_dir = os.path.join(out, "pdb")
    os.makedirs(pdb_dir, exist_ok=True)
    log_path = os.path.join(out, "records.jsonl")

    done = {f[:-4] for f in os.listdir(pdb_dir) if f.endswith(".pdb")}
    everything = list(read_fasta(fasta))
    seq_of = dict(everything)

    if retry:
        wanted = [line.strip() for line in open(retry) if line.strip()]
        records = [(i, seq_of[i]) for i in wanted if i in seq_of]
    else:
        records = [(i, s) for i, s in everything if i not in done]

    if limit:
        records = records[:limit]

    print(
        f"todo={len(records)} done={len(done)} "
        f"residues={sum(len(s) for _, s in records):,}",
        flush=True,
    )

    # The service may still be loading its weights, in which case it refuses every request
    # with the same message. Running the list anyway would mark every sequence in it as
    # failed, and the next phase's failure list would then overwrite that record.
    if records and not wait_for_service(url):
        print("SERVICE NOT READY — stopping without touching the list", flush=True)
        return {
            "folded": 0,
            "failed": [],
            "done": len(done),
            "elapsed_h": 0.0,
            "service_not_ready": True,
        }

    t_start = time.time()
    folded = 0
    failed: list[str] = []
    stopped_early = False
    with open(log_path, "a") as log:
        for n, (sid, seq) in enumerate(records, 1):
            if budget and time.time() - t_start > budget:
                print("budget reached", flush=True)
                break
            try:
                dt, payload = fold(seq, sid, url)
            except Exception as exc:
                failed.append(sid)
                print(f"FAIL {sid}: {exc}", flush=True)
                continue
            if _service_not_ready(payload):
                # The service stopped answering mid-list. The sequences after this point
                # are untouched, so the pass ends here and the list is picked up again by
                # the next one.
                print(f"SERVICE NOT READY at {sid} — stopping the pass", flush=True)
                stopped_early = True
                break
            result = payload.get("result") or {}
            pdb = result.get("pdb_content") or ""
            if not pdb:
                failed.append(sid)
                print(f"EMPTY {sid}: {_failure_reason(payload)}", flush=True)
                continue
            with open(os.path.join(pdb_dir, f"{sid}.pdb"), "w") as fh:
                fh.write(pdb)
            log.write(
                json.dumps(
                    {
                        "id": sid,
                        "aa": len(seq),
                        "s": round(dt, 2),
                        "confidence": result.get("confidence"),
                        "bytes": len(pdb),
                    }
                )
                + "\n"
            )
            log.flush()
            folded += 1
            elapsed = time.time() - t_start
            eta = (len(records) - n) * (elapsed / n) / 3600
            print(
                f"[{n}/{len(records)}] {sid} aa={len(seq)} {dt:.1f}s "
                f"rate={folded / elapsed * 3600:.0f}/h eta={eta:.1f}h",
                flush=True,
            )

    elapsed = time.time() - t_start
    print(
        f"DONE folded={folded} failed={len(failed)} elapsed={elapsed / 3600:.2f}h",
        flush=True,
    )
    # `failed.txt` describes this pass and nothing else, so it is rewritten even when the
    # pass had no failures — otherwise a stale list would invite a retry of sequences that
    # have since succeeded. A pass that stopped early is the exception: it did not reach
    # the end of its list, so the failures it collected are only part of what is still
    # outstanding, and overwriting the list would lose the part it did not reach.
    if not stopped_early:
        with open(os.path.join(out, "failed.txt"), "w") as fh:
            if failed:
                fh.write("\n".join(failed) + "\n")
    if failed:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(out, "failed.log"), "a") as fh:
            for sid in failed:
                fh.write(f"{stamp}\t{sid}\n")

    return {
        "folded": folded,
        "failed": failed,
        "done": len(done),
        "elapsed_h": round(elapsed / 3600, 3),
        "service_not_ready": stopped_early,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fasta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=0.0, help="stop after N seconds")
    ap.add_argument("--retry", default=None, help="file of identifiers to fold again")
    args = ap.parse_args(argv)

    summary = run(
        args.fasta,
        args.out,
        url=args.url,
        limit=args.limit,
        budget=args.budget,
        retry=args.retry,
    )
    # A pass that stopped because the service was not ready has folded nothing, and the
    # caller must be able to tell that from a pass that simply had nothing to do.
    if summary.get("service_not_ready"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
