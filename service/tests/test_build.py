"""The Builder endpoint, exercised offline against the local SQLite fixture.

`GET /api/build` is the one endpoint that composes rather than reports, so what these tests
pin is not only that it returns rows but that the composition decisions are the ones
documented: candidates come from the top channel only, the ranking is computed over the whole
candidate set before `limit` slices it, and a row's scaffold binding and linker both reflect
what the build actually assembled that row from.

The fixture gives the cases the assertions need. `antioxidant` holds one placeholder-binding
row and one verified-binding row, so a build with no scaffold named must produce one row with
a fused sequence and one without. `antibacterial` holds one top row and one bottom row, so the
channel filter is observable, and its pool has a single observation, so its composite is
absent and the null-composite ordering is exercised without being contrived. Its top row also
records a different linker from the other three, so the fallback a build makes when no linker
is named is an observation rather than a claim.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

COLLAGEN = "GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPP"
SILK = "GAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAG"
LINKER = "GGGGS"
# A curated entry whose length differs from both sample rows, so that a chosen linker is
# distinguishable from a stored one by arithmetic rather than only by letters.
CHOSEN_LINKER = "GGGGSGGGGSGGGGS"
STORED_LINKER_NAME = "(GGGGS)"
OTHER_STORED_LINKER_NAME = "(EAAAK)"
PEPTIDE_7001 = "WYPLGPK"
PEPTIDE_7002 = "FHLSTQNR"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_a_build_needs_at_least_one_direction(client):
    response = client.get("/api/build")
    assert response.status_code == 400
    assert "at least one direction" in response.json()["detail"]


def test_unknown_directions_and_routes_are_rejected(client):
    assert client.get("/api/build", params={"direction": "nope"}).status_code == 400
    assert (
        client.get("/api/build", params={"direction": ["antioxidant", "nope"]}).status_code
        == 400
    )
    assert (
        client.get(
            "/api/build", params={"direction": "antioxidant", "route_id": "nope"}
        ).status_code
        == 400
    )


def test_an_unknown_scaffold_is_a_not_found(client):
    response = client.get(
        "/api/build", params={"direction": "antioxidant", "scaffold_id": "nope"}
    )
    assert response.status_code == 404
    # A build with no scaffold named is legitimate; only a named-but-missing one is an error.
    assert client.get("/api/build", params={"direction": "antioxidant"}).status_code == 200


def test_an_unknown_linker_is_a_not_found(client):
    response = client.get(
        "/api/build", params={"direction": "antioxidant", "linker_id": "nope"}
    )
    assert response.status_code == 404
    # A build with no linker named is legitimate; only a named-but-missing one is an error.
    assert client.get("/api/build", params={"direction": "antioxidant"}).status_code == 200


# ---------------------------------------------------------------------------
# The linker decision
# ---------------------------------------------------------------------------

def test_a_build_without_a_linker_keeps_each_rows_own(client):
    body = client.get(
        "/api/build", params={"direction": ["antioxidant", "antibacterial"]}
    ).json()

    assert body["linker"] is None
    # The note has to say that the rows can differ, because here they do.
    assert "stored row records" in body["linker_note"]

    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["con_9001"]["linker_name"] == STORED_LINKER_NAME
    assert by_id["con_9002"]["linker_name"] == STORED_LINKER_NAME
    # The one row that records a different linker. Without it the fallback would be
    # indistinguishable from a constant.
    assert by_id["con_9003"]["linker_name"] == OTHER_STORED_LINKER_NAME


def test_a_named_linker_assembles_every_row_with_it_and_says_where_it_came_from(client):
    body = client.get(
        "/api/build",
        params={
            "direction": "antioxidant",
            "scaffold_id": "fixture-silk-s1",
            "linker_id": "LK_GS3",
        },
    ).json()

    assert body["linker"]["id"] == "LK_GS3"
    assert body["linker"]["sequence"] == CHOSEN_LINKER
    assert body["linker"]["length"] == len(CHOSEN_LINKER)
    # Which of the two linker tables answered is part of the answer, not a detail.
    assert body["linker"]["source_table"] == "linker_library"
    assert "named for this build" in body["linker_note"]
    # The note describes a candidate set, so it must not be the single-construct wording.
    assert "this construct" not in body["linker_note"]

    assert len(body["items"]) == 2
    for item in body["items"]:
        assert item["linker_name"] == "(GGGGS)3"
        assert item["full_sequence"] == SILK + CHOSEN_LINKER + item["peptide_sequence"]
        assert item["fused_length"] == len(SILK) + len(CHOSEN_LINKER) + item["peptide_length"]
        linker_segment = next(s for s in item["segments"] if s["type"] == "linker")
        assert linker_segment["sequence"] == CHOSEN_LINKER
        assert linker_segment["available"] is True


def test_a_named_linker_leaves_the_candidates_and_the_ranking_alone(client):
    """Naming a linker changes the sequence and nothing else — which the note claims."""
    base = {"direction": ["antioxidant", "antibacterial"], "scaffold_id": "fixture-silk-s1"}
    without = client.get("/api/build", params=base).json()
    with_linker = client.get("/api/build", params={**base, "linker_id": "LK_GS3"}).json()

    assert [i["id"] for i in without["items"]] == [i["id"] for i in with_linker["items"]]
    assert [i["composite"] for i in without["items"]] == [
        i["composite"] for i in with_linker["items"]
    ]
    assert [i["safety_verdict"] for i in without["items"]] == [
        i["safety_verdict"] for i in with_linker["items"]
    ]
    assert without["counts"] == with_linker["counts"]
    assert without["totals"] == with_linker["totals"]
    assert without["total"] == with_linker["total"]

    # ...and what it does change is every fused sequence, including the row whose stored
    # linker is the other sample entry.
    assert [i["fused_length"] for i in without["items"]] != [
        i["fused_length"] for i in with_linker["items"]
    ]
    assert all(i["fused_length"] == len(SILK) + len(CHOSEN_LINKER) + i["peptide_length"]
               for i in with_linker["items"])


def test_a_sample_table_linker_can_be_named_and_the_response_says_so(client):
    body = client.get(
        "/api/build", params={"direction": "antioxidant", "linker_id": "2"}
    ).json()

    assert body["linker"]["source_table"] == "linkers"
    assert body["linker"]["sequence"] == "EAAAK"
    assert body["linker"]["rigidity"] == "Rigid"


def test_the_two_assembly_choices_are_decided_and_reported_separately(client):
    """A build can take its scaffold from the record and its linker from the request."""
    body = client.get(
        "/api/build", params={"direction": "antioxidant", "linker_id": "LK_GS3"}
    ).json()

    assert body["scaffold"] is None
    assert "stored binding" in body["binding_note"]
    assert body["linker"]["id"] == "LK_GS3"
    assert "named for this build" in body["linker_note"]

    # No scaffold was named, so the placeholder row still emits no sequence — while its
    # linker was replaced all the same. Merging the two accounts into one note would have
    # to describe a row that is half from the record and half from the request.
    placeholder = next(i for i in body["items"] if i["id"] == "con_9001")
    assert placeholder["full_sequence"] is None
    assert placeholder["assembled_sequence_available"] is False
    assert placeholder["linker_name"] == "(GGGGS)3"
    linker_segment = next(s for s in placeholder["segments"] if s["type"] == "linker")
    assert linker_segment["available"] is True
    assert linker_segment["sequence"] == CHOSEN_LINKER


# ---------------------------------------------------------------------------
# The scaffold decision
# ---------------------------------------------------------------------------

def test_a_build_without_a_scaffold_inherits_each_stored_binding(client):
    body = client.get("/api/build", params={"direction": "antioxidant"}).json()

    assert body["scaffold"] is None
    assert body["total"] == 2
    assert len(body["items"]) == 2
    # The note has to say that the rows can disagree, because here they do.
    assert "stored binding" in body["binding_note"]

    by_id = {item["id"]: item for item in body["items"]}

    placeholder = by_id["con_9001"]
    assert placeholder["backbone_binding"] == "placeholder"
    assert placeholder["full_sequence"] is None
    assert placeholder["fused_length"] is None
    assert placeholder["assembled_sequence_available"] is False

    verified = by_id["con_9002"]
    assert verified["backbone_binding"] == "verified"
    assert verified["full_sequence"] == COLLAGEN + LINKER + PEPTIDE_7002
    assert verified["fused_length"] == len(COLLAGEN) + len(LINKER) + len(PEPTIDE_7002)
    assert verified["assembled_sequence_available"] is True


def test_a_named_scaffold_assembles_every_row_and_says_where_it_came_from(client):
    body = client.get(
        "/api/build",
        params={"direction": "antioxidant", "scaffold_id": "fixture-silk-s1"},
    ).json()

    assert body["scaffold"]["id"] == "fixture-silk-s1"
    assert body["scaffold"]["short_name"] == "Fixture S1"
    # The pairing is the caller's, and the response has to say so rather than let a full
    # sequence read as a pipeline result.
    assert "request time" in body["binding_note"]

    assert len(body["items"]) == 2
    for item in body["items"]:
        assert item["backbone_binding"] == "inferred"
        assert item["backbone_name"] == "Fixture S1"
        assert item["backbone_id"] == "fixture-silk-s1"
        assert item["full_sequence"] == SILK + LINKER + item["peptide_sequence"]
        assert item["fused_length"] == len(SILK) + len(LINKER) + item["peptide_length"]
        assert item["assembled_sequence_available"] is True
        assert [segment["type"] for segment in item["segments"]] == [
            "backbone", "linker", "peptide",
        ]
        assert all(segment["available"] for segment in item["segments"])

    # Naming a scaffold lifts the placeholder row into a real sequence — which is the whole
    # point of the page, and is why the binding has to be reported as inferred.
    placeholder = next(i for i in body["items"] if i["id"] == "con_9001")
    assert placeholder["full_sequence"] == SILK + LINKER + PEPTIDE_7001


def test_the_scope_note_separates_the_sequence_from_the_scores(client):
    body = client.get("/api/build", params={"direction": "antioxidant"}).json()
    assert "functional peptide alone" in body["scope_note"]
    assert "not a measurement of the construct" in body["scope_note"]


# ---------------------------------------------------------------------------
# The candidate decision
# ---------------------------------------------------------------------------

def test_a_build_ranks_candidates_and_excludes_the_control_arm(client):
    unfiltered = client.get("/api/constructs", params={"direction": "antibacterial"}).json()
    assert unfiltered["total"] == 2, "the fixture holds one candidate and one control"

    body = client.get("/api/build", params={"direction": "antibacterial"}).json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == ["con_9003"]
    assert "con_9004" not in {item["id"] for item in body["items"]}


# ---------------------------------------------------------------------------
# The ranking decision
# ---------------------------------------------------------------------------

def test_a_build_covers_several_directions_in_the_order_asked_for(client):
    body = client.get(
        "/api/build", params={"direction": ["antioxidant", "antibacterial"]}
    ).json()

    assert body["directions"] == ["antioxidant", "antibacterial"]
    assert body["totals"] == {"antioxidant": 2, "antibacterial": 1}
    assert body["total"] == 3
    assert {item["direction"] for item in body["items"]} == {"antioxidant", "antibacterial"}

    # The reverse order is the same set, and the direction list follows the request.
    reversed_body = client.get(
        "/api/build", params={"direction": ["antibacterial", "antioxidant"]}
    ).json()
    assert reversed_body["directions"] == ["antibacterial", "antioxidant"]
    assert reversed_body["total"] == 3


def test_comma_separated_and_repeated_directions_are_the_same_request(client):
    repeated = client.get(
        "/api/build", params={"direction": ["antioxidant", "antibacterial"]}
    ).json()
    comma = client.get("/api/build", params={"direction": "antioxidant,antibacterial"}).json()
    assert comma["directions"] == repeated["directions"]
    assert comma["total"] == repeated["total"]


def test_a_repeated_direction_is_not_ranked_twice(client):
    body = client.get(
        "/api/build", params={"direction": ["antioxidant", "antioxidant"]}
    ).json()
    assert body["directions"] == ["antioxidant"]
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_the_tally_covers_the_whole_match_not_the_returned_page(client):
    page = client.get(
        "/api/build", params={"direction": ["antioxidant", "antibacterial"], "limit": 1}
    ).json()

    assert len(page["items"]) == 1
    assert page["counts"]["ranked"] == 3, "the tally is over the match, not the slice"
    assert page["total"] == 3
    # con_9001 and con_9003 both carry peptide 7001, which clears every gate; con_9002 is
    # past haemolysis and the immunogenicity gate under the default route.
    assert page["counts"]["clear"] == 2
    assert page["counts"]["vetoed"] == 1
    assert page["counts"]["without_composite"] == 1


def test_the_page_slices_a_complete_ranking(client):
    params = {"direction": ["antioxidant", "antibacterial"], "limit": 10}
    everything = client.get("/api/build", params=params).json()
    assert len(everything["items"]) == 3

    first = client.get("/api/build", params={**params, "limit": 2}).json()
    second = client.get("/api/build", params={**params, "limit": 2, "offset": 2}).json()
    assert [i["id"] for i in first["items"]] == [i["id"] for i in everything["items"][:2]]
    assert [i["id"] for i in second["items"]] == [i["id"] for i in everything["items"][2:]]
    assert second["offset"] == 2


def test_rows_without_a_composite_sort_last_rather_than_as_zero(client):
    body = client.get(
        "/api/build", params={"direction": ["antioxidant", "antibacterial"]}
    ).json()

    composites = [item["composite"] for item in body["items"]]
    assert composites == sorted(
        (c for c in composites if c is not None), reverse=True
    ) + [None] * composites.count(None)

    # antibacterial's pool holds one observation, so it has no spread to weight over and no
    # composite can be computed. Ranking it as 0 would put an unrankable row in the middle of
    # a ranked list.
    assert body["items"][-1]["id"] == "con_9003"
    assert body["items"][-1]["composite"] is None


def test_the_route_shapes_the_ranking_and_is_reported(client):
    routes = client.get("/api/meta/routes").json()
    default = client.get("/api/build", params={"direction": "antioxidant"}).json()
    assert default["route"]["id"] == routes[0]["id"]
    # The route travels with its scaffold list, so a caller does not need a second request to
    # know which scaffolds this profile admits.
    assert default["route"]["scaffold_ids"] == routes[0]["scaffold_ids"]

    tightened = client.get(
        "/api/build",
        params={"direction": "antioxidant", "route_id": "wound-dressing"},
    ).json()
    assert tightened["route"]["id"] == "wound-dressing"
    assert tightened["route"]["screening"]["immunogenicity_threshold"] == 0.35
