"""Guard scientific interpretation independently of the chat provider."""
from fastapi.testclient import TestClient

from app.main import app


def test_short_peptide_developability_is_not_presented_as_calibrated_probability():
    with TestClient(app) as client:
        detail = client.get("/api/constructs/con_9001").json()
        tools = {item["key"]: item for item in client.get("/api/meta/tools").json()}

    for key in ("thermal_stability", "solubility"):
        assert detail["scores"][key] is not None
        assert detail["score_meta"][key]["semantics"] == "ranking_only"
        assert tools[key]["semantics"] == "ranking_only"
    assert "six temperature thresholds" in tools["thermal_stability"]["measures"]
    assert "not been calibrated" in tools["thermal_stability"]["threshold_note"]
    assert "shelf life" in tools["thermal_stability"]["threshold_note"]
    assert "exploratory" in detail["score_meta"]["composite"]["measures"]


def test_project_toxicity_cut_is_not_attributed_to_the_predictor():
    with TestClient(app) as client:
        detail = client.get("/api/constructs/con_9001").json()
    metadata = detail["score_meta"]["toxicity"]["applied_threshold"]
    gate = next(g for g in detail["safety"]["gates"] if g["key"] == "toxicity")
    assert metadata["value"] == gate["threshold"] == 0.38
    assert metadata["source"] == gate["threshold_source"] == "project"
