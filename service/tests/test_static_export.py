"""Actual SQLite exports must preserve the API's complete route-specific context."""
from __future__ import annotations

import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import constructs as constructs_repo
from app.services import analysis as analysis_service, reference
from scripts.export_static import Exporter


@pytest.fixture(scope="module")
def export_snapshot(tmp_path_factory):
    output = tmp_path_factory.mktemp("route-context-export")
    calls: Counter = Counter()
    real_peers = analysis_service._direction_peers

    def tracked_peers(direction, limit=5, route_id=None):
        calls[(direction, route_id)] += 1
        return real_peers(direction, limit=limit, route_id=route_id)

    with TestClient(app) as client:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(analysis_service, "_direction_peers", tracked_peers)
            Exporter(output).run(include_builds=False, include_peptide_details=False)
        yield output, client, calls


def read_json(output, relative):
    return json.loads((output / relative).read_text(encoding="utf-8"))


def test_exported_route_contexts_match_complete_api_safety_and_composite(export_snapshot):
    output, client, _ = export_snapshot
    rows, _ = constructs_repo.list_constructs(limit=100000, offset=0)
    for row in rows:
        construct_id = f"con_{row['id']:04d}"
        exported = read_json(output, f"constructs/{construct_id}.json")
        assert set(exported["route_contexts"]) == set(reference.ROUTES_BY_ID)
        for route in reference.ROUTES:
            response = client.get(f"/api/constructs/{construct_id}", params={"route_id": route.id})
            assert response.status_code == 200
            live = response.json()
            context = exported["route_contexts"][route.id]
            assert context["safety"] == live["safety"]
            assert context["composite"] == live["composite"] == live["scores"]["composite"]
            assert context["safety"]["route_id"] == route.id
            assert "route_contexts" not in live, "route_contexts is export metadata, not an API-model field"
        hair = exported["route_contexts"]["hair-coating"]
        assert hair["safety"]["immunogenicity_threshold"] == 0.6
        immune_gate = next(gate for gate in hair["safety"]["gates"] if gate["key"] == "immunogenicity")
        assert immune_gate["threshold"] == 0.6
        assert exported["safety"] == exported["route_contexts"][reference.ROUTES[0].id]["safety"]


def test_each_route_analysis_matches_api_and_default_file_remains_available(export_snapshot):
    output, client, _ = export_snapshot
    rows, _ = constructs_repo.list_constructs(limit=100000, offset=0)
    manifest = read_json(output, "manifest.json")
    for row in rows:
        construct_id = f"con_{row['id']:04d}"
        path = f"constructs/{construct_id}/analysis_by_route.json"
        analyses = read_json(output, path)
        assert path in manifest["files"]
        assert set(analyses) == set(reference.ROUTES_BY_ID)
        for route in reference.ROUTES:
            response = client.get(f"/api/constructs/{construct_id}/analysis", params={"route_id": route.id})
            assert response.status_code == 200
            assert analyses[route.id] == response.json()
            assert analyses[route.id]["route_id"] == route.id
            assert analyses[route.id]["provider"] == "template"
        default = read_json(output, f"constructs/{construct_id}/analysis.json")
        assert default == analyses[reference.ROUTES[0].id]
        assert default == client.get(f"/api/constructs/{construct_id}/analysis").json()
        hair_safety = next(block for block in analyses["hair-coating"]["blocks"] if block["id"] == "safety")
        assert "Hair Care" in hair_safety["content"]
        assert "0.6" in hair_safety["content"]


def test_export_caches_peer_queries_only_within_one_direction_route_snapshot(export_snapshot):
    _, _, calls = export_snapshot
    rows, _ = constructs_repo.list_constructs(limit=100000, offset=0)
    expected = {(row["direction"], route.id) for row in rows for route in reference.ROUTES}
    assert set(calls) == expected
    assert all(count == 1 for count in calls.values())
