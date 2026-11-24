"""Keep the checked-in Copilot connector aligned with the AI-assisted tools."""
import json
from pathlib import Path

import pytest

from presentation_search.api import AnalyzeSlidesRequest, ApplyTemplateRequest
from scripts.export_connector import specification


ROOT = Path(__file__).resolve().parents[1]
TENANT = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize("auth", ["entra", "api-key"])
def test_connector_exposes_analysis_and_layout_review_tools(auth):
    rendered = specification("https://api.example.invalid", auth, TENANT, TENANT)
    assert rendered["info"]["version"] == "1.3.0"
    operations = {
        method["operationId"]
        for path in rendered["paths"].values()
        for method in path.values()
    }
    assert {"AnalyzeSlides", "GetLayoutReport"} <= operations
    checked_in = json.loads(
        (ROOT / "integrations" / "copilot-studio" / f"openapi-{auth}.swagger.json").read_text()
    )
    assert checked_in == rendered


def test_connector_request_contracts_match_the_api_models():
    spec = specification("https://api.example.invalid", "entra", TENANT, TENANT)
    analyze = next(
        p["schema"] for p in spec["paths"]["/api/slides/analyze"]["post"]["parameters"]
        if p["in"] == "body"
    )
    apply = next(
        p["schema"] for p in spec["paths"]["/api/drafts/{job_id}/template"]["post"]["parameters"]
        if p["in"] == "body"
    )
    assert set(analyze["required"]) == set(AnalyzeSlidesRequest.model_json_schema()["required"])
    assert set(analyze["properties"]) == set(AnalyzeSlidesRequest.model_json_schema()["properties"])
    assert set(apply["required"]) == set(ApplyTemplateRequest.model_json_schema()["required"])
    assert set(apply["properties"]) == set(ApplyTemplateRequest.model_json_schema()["properties"])
