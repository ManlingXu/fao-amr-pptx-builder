"""Keep imported Copilot tool inputs aligned with the real API contract."""
import pytest

from presentation_search.api import DraftRequest, SearchRequest
from scripts.export_connector import specification


@pytest.mark.parametrize("auth", ["api-key", "entra"])
@pytest.mark.parametrize(
    ("path", "model"), [("/api/search", SearchRequest), ("/api/drafts", DraftRequest)]
)
def test_connector_requires_api_inputs_and_preserves_bounds(auth, path, model):
    spec = specification(
        "https://approved.example.invalid", auth,
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
    )
    imported = spec["paths"][path]["post"]["parameters"][0]["schema"]
    actual = model.model_json_schema()
    assert set(imported["required"]) == set(actual["required"])
    for name, field in actual["properties"].items():
        tool_field = imported["properties"][name]
        for constraint in ("minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems"):
            if constraint in field:
                assert tool_field.get(constraint) == field[constraint], (name, constraint)
        if "items" in field:
            for constraint in ("minLength", "maxLength"):
                assert tool_field["items"].get(constraint) == field["items"].get(constraint)
