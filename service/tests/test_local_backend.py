"""Offline run of every endpoint against the local SQLite fixture.

The remote Postgres instance is not always reachable, and the whole point of the fallback is
that the service stays exercisable when it is not. These tests pin the backend to the fixture
(see conftest.py) and drive the real application through its real routers, services and
repositories — only the database engine differs.

What they are for:

  * the Postgres-to-SQLite translation covers every statement the repositories issue, so a
    repository edit that adds an untranslatable construct fails here rather than in
    production;
  * every endpoint serialises against the fixture, which catches a response model that
    assumes a column the fixture does not have;
  * the two seeded constructs take the two binding branches, so the verified/placeholder
    split is asserted rather than assumed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

BACKBONE_SEQUENCE = "GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPP"
PEPTIDE_9001 = "WYPLGPK"
PEPTIDE_9002 = "FHLSTQNR"
SILK_SEQUENCE = "GAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAG"
CHOSEN_LINKER_SEQUENCE = "GGGGSGGGGSGGGGS"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health and reference data
# ---------------------------------------------------------------------------

def test_health_names_the_active_backend(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["database"]["backend"] == "sqlite"
    # The fallback is never silent: the reason and a note travel with the payload.
    assert "fallback_reason" in body["database"]
    assert "fixture" in body["database"]["note"].lower()
    assert body["database"]["server"].startswith("SQLite")


def test_reference_data_is_complete(client):
    body = client.get("/api/meta/reference").json()
    assert len(body["directions"]) == 4
    assert len(body["routes"]) == 5
    assert len(body["tools"]) == 9
    assert len(body["evidence_levels"]) == 5
    assert len(body["material_forms"]) == 7
    assert {c["id"] for c in body["categories"]} == {"recombinant-collagen", "silkworm-silk"}

    antioxidant = next(d for d in body["directions"] if d["id"] == "antioxidant")
    assert antioxidant["construct_count"] == 2
    assert antioxidant["status"] == "ready"

    # The route's scaffold list is derived from the scaffold rows, not hardcoded.
    wound = next(r for r in body["routes"] if r["id"] == "wound-dressing")
    assert wound["scaffold_ids"] == ["fixture-collagen-c1"]
    assert wound["screening"]["immunogenicity_threshold"] == 0.35


def test_individual_reference_endpoints(client):
    assert len(client.get("/api/meta/directions").json()) == 4
    assert len(client.get("/api/meta/routes").json()) == 5
    assert len(client.get("/api/meta/tools").json()) == 9
    pipeline = client.get("/api/meta/pipeline").json()
    assert len(pipeline["included"]) == 4
    assert len(pipeline["excluded"]) == 4
    # The view is translated from Postgres into SQLite rather than stubbed.
    assert len(client.get("/api/meta/coverage").json()) == 15


# ---------------------------------------------------------------------------
# Constructs
# ---------------------------------------------------------------------------

def test_construct_list_reports_both_bindings(client):
    body = client.get("/api/constructs", params={"direction": "antioxidant"}).json()
    assert body["total"] == 2
    by_id = {item["id"]: item for item in body["items"]}

    assert by_id["con_9001"]["backbone_binding"] == "placeholder"
    assert by_id["con_9001"]["backbone_name"] is None

    assert by_id["con_9002"]["backbone_binding"] == "verified"
    assert by_id["con_9002"]["backbone_name"] == "Fixture-C1"

    # The composite needs two observations to take a spread over; both rows must carry one.
    assert all(item["composite"] is not None for item in body["items"])


def test_placeholder_construct_emits_no_fused_sequence(client):
    body = client.get("/api/constructs/con_9001").json()
    assert body["backbone_binding"] == "placeholder"
    assert body["full_sequence"] is None
    assert body["assembled_sequence_available"] is False

    backbone, linker, peptide = body["segments"]
    assert backbone["type"] == "backbone"
    assert backbone["available"] is False
    assert linker["available"] is True
    assert peptide["sequence"] == PEPTIDE_9001

    assert body["safety"]["verdict"] == "clear"
    assert body["safety"]["vetoed_by"] == []
    assert body["scores"]["toxicity"] == pytest.approx(0.18)
    assert body["scores"]["composite"] is not None


def test_verified_construct_assembles_the_full_sequence(client):
    body = client.get("/api/constructs/con_9002").json()
    assert body["backbone_binding"] == "verified"
    assert body["assembled_sequence_available"] is True
    assert body["full_sequence"] == BACKBONE_SEQUENCE + "GGGGS" + PEPTIDE_9002
    assert body["backbone_name"] == "Fixture-C1"

    backbone = body["segments"][0]
    assert backbone["available"] is True
    assert backbone["sequence"] == BACKBONE_SEQUENCE

    # A stored binding has no curated scaffold-library metadata behind it, so the curated
    # block stays empty while the name is still reported.
    assert body["scaffold"] is None

    assert body["safety"]["verdict"] == "vetoed"
    assert set(body["safety"]["vetoed_by"]) == {"hemolysis", "immunogenicity"}


def test_request_scaffold_overrides_the_stored_binding(client):
    body = client.get(
        "/api/constructs/con_9002", params={"scaffold_id": "fixture-silk-s1"}
    ).json()
    assert body["backbone_binding"] == "inferred"
    assert body["scaffold"]["id"] == "fixture-silk-s1"
    assert body["full_sequence"] == SILK_SEQUENCE + "GGGGS" + PEPTIDE_9002

    # A placeholder construct can still be assembled when the caller names a scaffold.
    other = client.get(
        "/api/constructs/con_9001", params={"scaffold_id": "fixture-collagen-c1"}
    ).json()
    assert other["backbone_binding"] == "inferred"
    assert other["full_sequence"] == BACKBONE_SEQUENCE + "GGGGS" + PEPTIDE_9001


def test_construct_detail_honours_a_named_linker(client):
    """The Builder's result cards link here with the linker they assembled with.

    A detail page that ignored the parameter would show a different fused sequence from the
    one the build produced, for the same candidate, without saying so.
    """
    base = client.get(
        "/api/constructs/con_9001", params={"scaffold_id": "fixture-silk-s1"}
    ).json()
    assert base["linker"]["name"] == "(GGGGS)"
    assert base["linker"]["source_table"] == "linkers"
    assert base["linker_note"].startswith("No linker was named")
    assert base["full_sequence"] == SILK_SEQUENCE + "GGGGS" + PEPTIDE_9001

    named = client.get(
        "/api/constructs/con_9001",
        params={"scaffold_id": "fixture-silk-s1", "linker_id": "LK_GS3"},
    ).json()
    assert named["linker"]["id"] == "LK_GS3"
    assert named["linker"]["source_table"] == "linker_library"
    assert "named at request time" in named["linker_note"]
    assert named["full_sequence"] == SILK_SEQUENCE + CHOSEN_LINKER_SEQUENCE + PEPTIDE_9001
    # The scaffold account is untouched by the linker choice, and the other way round.
    assert named["backbone_binding"] == base["backbone_binding"] == "inferred"

    assert client.get("/api/constructs/con_9001", params={"linker_id": "nope"}).status_code == 404


def test_routing_and_validation(client):
    assert client.get("/api/constructs/con_9002", params={"scaffold_id": "nope"}).status_code == 404
    assert client.get("/api/constructs/con_9999").status_code == 404
    assert client.get("/api/constructs/not-an-id").status_code == 400
    assert client.get("/api/constructs", params={"direction": "nope"}).status_code == 400
    assert client.get("/api/constructs", params={"route_id": "nope"}).status_code == 400
    assert client.get("/api/constructs", params={"limit": 0}).status_code == 422


def test_scaffold_candidates_are_returned_as_options(client):
    items = client.get("/api/constructs/con_9001/scaffolds").json()
    assert items, "wound_care should narrow to at least one scaffold"
    assert {s["id"] for s in items} == {"fixture-collagen-c1"}


def test_peptide_detail_exposes_the_raw_tool_rows(client):
    body = client.get("/api/constructs/con_9001/peptide").json()
    assert body["construct_id"] == "con_9001"
    assert len(body["tools"]) == 15
    assert body["peptide"]["sequence"] == PEPTIDE_9001
    # The JSONB column round-trips through SQLite as a decoded object, not a string.
    assert body["stored_construct_scores"]["aggrescan_a3v"] == pytest.approx(-0.19)


def test_analysis_and_chat(client):
    body = client.get("/api/constructs/con_9002/analysis").json()
    assert body["provider"] == "template"
    assert [b["id"] for b in body["blocks"]] == [
        "safety", "peptide_origin", "linker_rationale",
        "expression_strategy", "comparison", "risk",
    ]
    # The linker block must describe a stored verified binding, not a request-time choice.
    linker_block = next(b for b in body["blocks"] if b["id"] == "linker_rationale")
    assert "verified" in linker_block["content"]
    assert "named at request time" not in linker_block["content"]

    reply = client.post(
        "/api/constructs/con_9001/chat",
        json={"construct_id": "con_9001", "message": "How does the safety gate read?"},
    ).json()
    assert reply["provider"] == "template"
    assert reply["llm_configured"] is False
    assert reply["message"]["content"]
    assert reply["suggested_questions"]


# ---------------------------------------------------------------------------
# Scaffolds and linkers
# ---------------------------------------------------------------------------

def test_scaffold_endpoints(client):
    assert len(client.get("/api/scaffolds").json()) == 2
    filtered = client.get("/api/scaffolds", params={"route_id": "mask-patch"}).json()
    assert [s["id"] for s in filtered] == ["fixture-silk-s1"]

    detail = client.get("/api/scaffolds/fixture-collagen-c1").json()
    assert detail["short_name"] == "Fixture C1"
    assert detail["route_ids"] == ["wound-dressing", "injectable-filler"]
    assert len(detail["sequences"]) == 1
    assert detail["sequences"][0]["sequence"] == BACKBONE_SEQUENCE
    # Fields the dataset does not carry are named rather than left as empty cards.
    assert "characteristics" in detail["unavailable_fields"]

    assert client.get("/api/scaffolds/fixture-collagen-c1/constructs").json() == []
    assert client.get("/api/scaffolds/nope").status_code == 404


def test_linker_endpoints(client):
    curated = client.get("/api/linkers").json()
    assert {row["source_table"] for row in curated} == {"linker_library"}

    with_placeholder = client.get("/api/linkers", params={"include_placeholder": True}).json()
    assert len(with_placeholder) == 5, "three curated entries and the two sample rows"
    assert {row["source_table"] for row in with_placeholder} == {"linker_library", "linkers"}

    detail = client.get("/api/linkers/LK_GGGGS").json()
    assert detail["unit_composition"] == [{"unit": "GGGGS", "count": 1, "label": "flexible"}]

    # The sample table stores 0.0/1.0 rather than a band, so the label on those rows is
    # derived; the curated rows carry it as text and it is served verbatim.
    assert client.get("/api/linkers/1").json()["sequence"] == "GGGGS"
    assert client.get("/api/linkers/1").json()["rigidity"] == "Flexible"
    assert client.get("/api/linkers/LK_GS3").json()["rigidity"] == "Mostly Flexible"
    assert client.get("/api/linkers/nope").status_code == 404
