"""The Library listing endpoint: filtering, search, ordering and pagination.

`GET /api/constructs` is the endpoint behind the Library's peptide tab, where the peptide
library's twenty million rows are actually navigated. What these tests pin is that the
narrowing controls select the same rows on either database backend, and that the reported
`total` describes the filtered set rather than the table — a total the page cannot reconcile
with its rows is how a list ends up paging past its own end.

The search assertions are about literalness as much as about matching. A peptide sequence is
amino-acid letters, and `_` and `%` are ordinary characters in a source accession, so a filter
that let those act as wildcards would silently widen a search rather than narrow it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

PEPTIDE_7001 = "WYPLGPK"
PEPTIDE_7002 = "FHLSTQNR"
ACCESSION_7001 = "FIX_0001"
SOURCE = "fixture"
VERSION = "2026-07-17"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def sequences(response) -> list[str]:
    return [item["peptide_sequence"] for item in response.json()["items"]]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_matches_a_peptide_sequence_substring(client):
    body = client.get("/api/constructs", params={"search": PEPTIDE_7001}).json()
    assert body["total"] > 0
    assert set(sequences(client.get("/api/constructs", params={"search": PEPTIDE_7001}))) == {
        PEPTIDE_7001
    }


def test_search_is_case_insensitive(client):
    lower = client.get("/api/constructs", params={"search": PEPTIDE_7001.lower()}).json()
    exact = client.get("/api/constructs", params={"search": PEPTIDE_7001}).json()
    assert lower["total"] == exact["total"] > 0


def test_search_matches_the_peptide_source(client):
    body = client.get("/api/constructs", params={"search": SOURCE}).json()
    assert body["total"] > 0


def test_search_matches_the_source_version(client):
    body = client.get("/api/constructs", params={"search": VERSION}).json()
    assert body["total"] > 0


def test_search_matches_the_source_accession_including_its_underscore(client):
    """The underscore in `FIX_0001` is a literal character, not a single-character wildcard."""
    body = client.get("/api/constructs", params={"search": ACCESSION_7001}).json()
    assert body["total"] > 0


def test_a_row_carries_the_provenance_a_search_can_match_on(client):
    """The listed row has to carry the columns `search` matches, not only the sequence.

    The query covers four columns and three of them are provenance, which the row did not
    otherwise hold: a construct was searchable by a field it could not report. That matters
    beyond tidiness, because a client that applies the same four-column filter to the same rows
    — the static export does, since a deployment has no database to send the query to — can
    only match what the row carries. A row matched by accession would be kept by the service
    and dropped by the export, so the same term would answer with rows on one deployment and
    with nothing on the other, and nothing about either answer would look wrong.
    """
    item = client.get("/api/constructs", params={"search": ACCESSION_7001}).json()["items"][0]
    assert item["peptide_source"] == SOURCE
    assert item["peptide_source_accession"] == ACCESSION_7001
    # A string on both backends, which the filters on both sides rely on: the comparison is a
    # case-insensitive substring test, and a client lowercases the column to apply it.
    assert item["peptide_source_version"] == VERSION
    assert isinstance(item["peptide_source_version"], str)


def test_a_row_without_provenance_reports_none_rather_than_a_placeholder(client):
    """A null column stays null in the payload.

    The export's own filter reads these fields, and a value that arrived as the literal text
    `None` or `undefined` would match a search for that word. Nothing in the fixture is missing
    provenance, so this pins the contract rather than the fixture: whatever the database holds,
    the field is a string or null and never a rendering of one.
    """
    for item in client.get("/api/constructs", params={"limit": 200}).json()["items"]:
        for key in ("peptide_source", "peptide_source_accession", "peptide_source_version"):
            assert item[key] is None or isinstance(item[key], str), (key, item[key])


def test_underscore_in_a_term_does_not_act_as_a_wildcard(client):
    """`FIXX0001` would match `FIX_0001` if `_` were a wildcard. It must match nothing."""
    wildcard = client.get("/api/constructs", params={"search": "FIXX0001"}).json()
    literal = client.get("/api/constructs", params={"search": ACCESSION_7001}).json()
    assert wildcard["total"] == 0
    assert literal["total"] > 0


def test_percent_in_a_term_does_not_match_everything(client):
    """An unescaped `%` would turn the filter into a match-all and report every construct."""
    assert client.get("/api/constructs", params={"search": "%"}).json()["total"] == 0


def test_search_combines_with_the_other_filters(client):
    """A search narrows the filtered set rather than replacing it."""
    unfiltered = client.get("/api/constructs", params={"search": PEPTIDE_7001}).json()["total"]
    scoped = client.get(
        "/api/constructs",
        params={"search": PEPTIDE_7001, "direction": "antimelanin"},
    ).json()
    assert scoped["total"] == 0
    assert unfiltered > 0


def test_search_with_no_match_returns_an_empty_page_not_an_error(client):
    body = client.get("/api/constructs", params={"search": "ZZZZZZZZ"}).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_search_term_is_length_limited(client):
    """An unbounded term is an unbounded scan on a twenty-million-row table."""
    response = client.get("/api/constructs", params={"search": "A" * 201})
    assert response.status_code == 422


def test_blank_search_is_treated_as_no_search(client):
    blank = client.get("/api/constructs", params={"search": "   "}).json()
    bare = client.get("/api/constructs").json()
    assert blank["total"] == bare["total"]


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_order_by_peptide_length_sorts_shortest_first(client):
    rows = client.get(
        "/api/constructs", params={"order": "peptide_length", "limit": 50}
    ).json()["items"]
    lengths = [item["peptide_length"] for item in rows]
    assert lengths == sorted(lengths)


def test_order_by_peptide_length_needs_no_search_term(client):
    """The sort reads the peptides table, so it must add its own join when nothing searched."""
    response = client.get("/api/constructs", params={"order": "peptide_length"})
    assert response.status_code == 200


def test_order_by_peptide_id_groups_a_peptides_constructs_together(client):
    """Ordering by the peptide's own id, rather than by rank, is for locating one peptide's
    rows. Its observable effect is that a peptide's constructs become contiguous instead of
    being scattered through the ranking."""
    rows = client.get("/api/constructs", params={"order": "peptide_id", "limit": 50}).json()["items"]
    sequences_ordered = [item["peptide_sequence"] for item in rows]

    runs = 0
    for index, sequence in enumerate(sequences_ordered):
        if index == 0 or sequence != sequences_ordered[index - 1]:
            runs += 1

    assert runs == len(set(sequences_ordered))
    assert runs > 1


def test_default_order_is_the_pipeline_ranking(client):
    rows = client.get("/api/constructs", params={"limit": 50}).json()["items"]
    by_id = {item["id"]: item for item in rows}
    ordered = client.get("/api/constructs", params={"order": "rank", "limit": 50}).json()["items"]
    assert [item["id"] for item in rows] == [item["id"] for item in ordered]
    assert by_id  # the comparison is against real rows, not two empty lists


def test_unknown_order_is_rejected(client):
    assert client.get("/api/constructs", params={"order": "nonsense"}).status_code == 422


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_pagination_slices_without_repeating_or_dropping_rows(client):
    """`limit`/`offset` must partition the ordered set, which is what makes a page number
    addressable. The Library tab previously grew `limit` instead, so every page re-fetched
    the rows before it."""
    everything = client.get("/api/constructs", params={"limit": 50}).json()
    total = everything["total"]
    assert total > 2

    first = client.get("/api/constructs", params={"limit": 2, "offset": 0}).json()
    second = client.get("/api/constructs", params={"limit": 2, "offset": 2}).json()

    first_ids = [item["id"] for item in first["items"]]
    second_ids = [item["id"] for item in second["items"]]
    assert len(first_ids) == len(second_ids) == 2
    assert not set(first_ids) & set(second_ids)
    assert first_ids + second_ids == [item["id"] for item in everything["items"]][:4]


def test_total_describes_the_filtered_set_not_the_table(client):
    """The count and the rows have to come from the same statement shape. A `total` taken
    from a differently-joined query would report a number the page cannot page through."""
    scoped = client.get("/api/constructs", params={"search": PEPTIDE_7001}).json()
    assert scoped["total"] == len(
        [i for i in client.get("/api/constructs", params={"limit": 50}).json()["items"]
         if i["peptide_sequence"] == PEPTIDE_7001]
    )


def test_offset_past_the_end_returns_no_rows_and_keeps_the_total(client):
    body = client.get("/api/constructs", params={"limit": 2, "offset": 10_000}).json()
    assert body["items"] == []
    assert body["total"] > 0
