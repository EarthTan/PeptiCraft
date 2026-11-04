"""The progress page has to stay truthful while the batch runs, which means it is tested against
known inputs rather than against the live directory.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from scripts.progress_dashboard import (
    count_folded,
    count_published,
    parse_machine,
    probe_machine,
    read_manifest,
    render,
    render_machines,
    seconds_for,
    short_gpu,
    summarise,
)


def write_manifest(path: Path, rows):
    header = "structure_id,tier,fused_length\n"
    body = "".join(f"{sid},{tier},{length}\n" for sid, tier, length in rows)
    path.write_text(header + body)
    return path


def test_a_structure_that_appears_twice_keeps_its_first_tier(tmp_path):
    """Each structure is reachable through several paths, and only one row is canonical."""
    manifest = write_manifest(
        tmp_path / "manifest.csv",
        [("s1", 1, 100), ("s1", 3, 100), ("s2", 2, 200)],
    )
    tiers = read_manifest(manifest)
    assert tiers == {"s1": (1, 100), "s2": (2, 200)}


def test_folding_counts_only_coordinate_files(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "s1.pdb").write_text("ATOM")
    (staging / "s2.pdb").write_text("ATOM")
    (staging / "records.jsonl").write_text("{}")
    (staging / "notes.txt").write_text("")

    assert count_folded(staging) == {"s1", "s2"}


def test_a_missing_staging_directory_counts_as_nothing(tmp_path):
    assert count_folded(tmp_path / "absent") == set()


def test_the_publish_count_reads_the_record_length(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"structures/s1.pdb": {}, "structures/s2.pdb": {}}))
    assert count_published(state) == 2


def test_a_corrupt_record_reads_as_zero_rather_than_raising(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{not json")
    assert count_published(state) == 0


def test_a_tier_is_complete_when_every_structure_in_it_is_folded():
    tiers = {"s1": (1, 100), "s2": (1, 100), "s3": (2, 100)}
    stats = summarise(tiers, {"s1", "s2"})
    assert stats["per_tier"][1]["done"] == 2
    assert stats["per_tier"][1]["hours_left"] == 0
    assert stats["per_tier"][2]["done"] == 0


def test_the_phase_one_total_is_the_two_recommended_tiers():
    tiers = {"s1": (1, 100), "s2": (2, 100), "s3": (3, 100)}
    stats = summarise(tiers, {"s1"})
    assert stats["phase_one"]["total"] == 2
    assert stats["phase_one"]["done"] == 1


def test_hours_follow_the_length_fit_not_the_count():
    """Two structures of different length are not equal amounts of work."""
    short = {"a": (1, 100)}
    long = {"b": (1, 800)}
    assert summarise(short, set())["hours_left"] < summarise(long, set())["hours_left"]
    assert seconds_for(800) > seconds_for(100) * 10


def test_a_longer_chain_never_costs_less_than_a_shorter_one():
    assert all(seconds_for(a) < seconds_for(b) for a, b in [(67, 300), (300, 900), (900, 1126)])


def test_the_page_states_the_progress_it_was_given():
    tiers = {"s1": (1, 100), "s2": (2, 100), "s3": (3, 100)}
    stats = summarise(tiers, {"s1"})
    page = render(stats, published=1, generated=datetime(2026, 11, 3, 12, 0))

    assert "结构预测进度" in page
    assert "1 / 3" in page
    assert "2 / 3" not in page
    assert "云端结构桶已发布 1 条" in page
    assert "nan" not in page.lower()
    assert "None" not in page


def test_an_empty_batch_renders_without_dividing_by_zero():
    """The page is rebuilt on a schedule, so it has to survive a batch that has produced nothing."""
    page = render(summarise({}, set()), published=0, generated=datetime(2026, 11, 3, 12, 0))
    assert "0 / 0" in page
    assert "nan" not in page.lower()


def test_the_two_shares_are_reported_separately():
    """The count share and the clock share differ, and the page shows both."""
    tiers = {"short": (1, 70), "long": (3, 1100)}
    stats = summarise(tiers, {"short"})
    page = render(stats, published=1, generated=datetime(2026, 11, 3, 12, 0))

    assert "50.0%" in page
    assert "0.0%" in page


def a_machine(name: str = "宿舍 Ubuntu", host: str = "ubuntu-tailscale") -> dict:
    return {
        "name": name,
        "host": host,
        "window": "8:00–23:00",
        "fastas": ["/home/a/one.fasta", "/home/a/two.fasta"],
        "pdb": "/home/a/folds/pdb",
    }


def answer(monkeypatch, stdout: str, returncode: int = 0):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    monkeypatch.setattr("scripts.progress_dashboard.subprocess.run", fake_run)
    return calls


def test_a_machine_spec_splits_into_the_share_it_was_given():
    parsed = parse_machine("宿舍 Ubuntu|ubuntu-tailscale|8:00–23:00|/a/p1,/a/p2|/a/pdb")
    assert parsed["name"] == "宿舍 Ubuntu"
    assert parsed["host"] == "ubuntu-tailscale"
    assert parsed["window"] == "8:00–23:00"
    assert parsed["fastas"] == ["/a/p1", "/a/p2"]
    assert parsed["pdb"] == "/a/pdb"


def test_a_malformed_machine_spec_is_rejected_rather_than_half_read():
    with pytest.raises(ValueError):
        parse_machine("宿舍 Ubuntu|ubuntu-tailscale|8:00–23:00")


def test_the_probe_reads_back_the_four_facts_it_asked_for(monkeypatch):
    stdout = (
        "total=1040\ndone=260\nrecent=12\n"
        "gpu=NVIDIA GeForce RTX 5060 Laptop GPU, 100\n"
        "up=pepticraft-runner,pepticraft-fold,\n"
    )
    answer(monkeypatch, stdout)
    status = probe_machine(a_machine())

    assert status["reachable"] is True
    assert (status["total"], status["done"]) == (1040, 260)
    assert status["recent"] == 12
    assert status["running"] is True
    assert status["gpu"].endswith("100")


def test_a_machine_that_cannot_be_reached_is_reported_rather_than_assumed_idle(monkeypatch):
    """A sleeping machine and a broken batch look the same in the totals; only the machine
    can tell them apart, so a failed call has to say so."""
    answer(monkeypatch, "", returncode=255)
    status = probe_machine(a_machine())

    assert status["reachable"] is False
    assert status["done"] == 0
    page = render_machines([status])
    assert "失联" in page
    assert "运行中" not in page


def test_a_timed_out_probe_does_not_stop_the_page(monkeypatch):
    def boom(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr("scripts.progress_dashboard.subprocess.run", boom)
    status = probe_machine(a_machine())

    assert status["reachable"] is False
    assert "宿舍 Ubuntu" in render_machines([status])


def test_the_machine_cards_state_the_share_the_state_and_the_window():
    status = dict(a_machine(), reachable=True, total=1040, done=260, recent=12,
                  gpu="NVIDIA GeForce RTX 5060 Laptop GPU, 100", running=True)
    page = render_machines([status])

    assert "宿舍 Ubuntu" in page
    assert "260 / 1,040 条" in page
    assert "25.0%" in page
    assert "运行中" in page
    assert "8:00–23:00" in page
    assert "近一小时 12 条" in page


def test_a_stopped_machine_is_not_dressed_up_as_running():
    status = dict(a_machine(name="工作站"), reachable=True, total=3560, done=3000, recent=0,
                  gpu="NVIDIA RTX 5880 Ada Generation, 0", running=False)
    page = render_machines([status])

    assert "已停" in page
    assert "运行中" not in page


def test_the_hardware_line_drops_the_vendor_prefix():
    assert short_gpu("NVIDIA GeForce RTX 5060 Laptop GPU, 100") == "RTX 5060 Laptop GPU"
    assert short_gpu("NVIDIA RTX 5880 Ada Generation, 97") == "RTX 5880 Ada Generation"
    assert short_gpu("") == ""


def test_a_page_without_machines_has_no_machine_section():
    stats = summarise({"s1": (1, 100)}, set())
    page = render(stats, published=0, generated=datetime(2026, 11, 3, 12, 0))
    assert "两台机器" not in page


def test_the_page_counts_the_machines_it_was_given():
    status = [dict(a_machine(), reachable=True, total=10, done=1, recent=1, gpu="", running=True)]
    stats = summarise({"s1": (1, 100)}, {"s1"})
    page = render(stats, published=1, generated=datetime(2026, 11, 3, 12, 0), machines=status)
    assert "1 台机器并行" in page
    assert "两台机器" in page
