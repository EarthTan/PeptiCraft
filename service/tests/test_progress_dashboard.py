"""The progress page has to stay truthful while the batch runs, which means it is tested against
known inputs rather than against the live directory.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.progress_dashboard import (
    count_folded,
    count_published,
    read_manifest,
    render,
    seconds_for,
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
