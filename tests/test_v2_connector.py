"""Validate the checked-in V2 Copilot tool specs against the code exporter and API contracts."""
import json
from pathlib import Path

import pytest
from presentation_search.api import (
    PlanCreateRequest, PlanRevisionRequest, PlanFinalizeRequest,
)
from scripts.export_connector import specification

ROOT = Path(__file__).resolve().parents[1]
TENANT = "00000000-0000-0000-0000-000000000000"
TOOLS = ["PlanPresentation", "GetPresentationPlan", "RevisePresentationPlan", "CreateDraftFromPlan"]


@pytest.mark.parametrize("auth", ["entra", "api-key"])
def test_checked_in_v2_connector_matches_exporter(auth):
    rendered = specification("https://api.example.invalid", auth, TENANT, TENANT)
    name = f"openapi-{auth}.swagger.json"
    checked_in = json.loads(
        (ROOT / "integrations" / "copilot-studio" / name).read_text(encoding="utf-8")
    )
    assert checked_in == rendered, "Regenerate the checked-in Swagger from scripts/export_connector.py"
    assert rendered["info"]["version"] == "1.2.0"
    assert set(TOOLS) <= {
        method["operationId"]
        for path in rendered["paths"].values()
        for method in path.values()
    }


@pytest.mark.parametrize("path,method,model", [
    ("/api/plans", "post", PlanCreateRequest),
    ("/api/plans/{plan_id}", "put", PlanRevisionRequest),
    ("/api/plans/{plan_id}/draft", "post", PlanFinalizeRequest),
])
def test_v2_connector_required_fields_match_pydantic_api(path, method, model):
    spec = specification("https://api.example.invalid", "entra", TENANT, TENANT)
    body = next(p["schema"] for p in spec["paths"][path][method]["parameters"]
                if p["in"] == "body")
    api = model.model_json_schema()
    assert set(body["required"]) == set(api["required"])
    assert body["properties"]["expected_revision"]["minimum"] == 1 if "expected_revision" in body["properties"] else True
