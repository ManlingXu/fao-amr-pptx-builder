"""Refresh the public Developer Mode reference from tracked project definitions."""

import ast
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "integrations" / "copilot-studio"


def main():
    def read_json(name):
        return json.loads((BLUEPRINT / name).read_text(encoding="utf-8"))

    swagger = read_json("openapi-entra.swagger.json")
    operations = [
        {"name": spec["operationId"], "method": method.upper(), "path": path,
         "purpose": spec["summary"], "detail": spec.get("description", "")}
        for path, methods in swagger["paths"].items() for method, spec in methods.items()
    ]
    prompts = []
    for name in ("presentation-brief", "query-expansion", "candidate-reranking", "layout-decision"):
        item = read_json(f"ai-prompts/{name}.json")
        prompts.append({
            "file": f"ai-prompts/{name}.json", "name": item["name"], "purpose": item["purpose"],
            "instructions": item["instructions"], "inputs": [field["name"] for field in item["inputs"]],
        })
    flow = read_json("flow-design.json")
    with (ROOT / "examples/public_corpus/amr/catalog.csv").open(encoding="utf-8-sig", newline="") as stream:
        corpus = list(csv.DictReader(stream))
    module = ast.parse((ROOT / "presentation_search/studio_model.py").read_text(encoding="utf-8"))
    prompts_by_use = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in module.body if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"ADAPT_INSTRUCTIONS", "DIALOGUE_INSTRUCTIONS"}
    }
    manifest = read_json("migration/agent-manifest.json")
    migration_skills = []
    for file in manifest["skills"]:
        text = (BLUEPRINT / "migration" / file).read_text(encoding="utf-8").strip()
        metadata, body = text.removeprefix("---\n").split("\n---\n", 1)
        fields = dict(line.split(": ", 1) for line in metadata.splitlines())
        migration_skills.append({**fields, "body": body.strip(), "file": "migration/" + file})
    snapshot = {
        "manifest": manifest, "migrationSkills": migration_skills,
        "modelInstructions": prompts_by_use,
        "instructions": (BLUEPRINT / "agent-instructions-en.txt").read_text(encoding="utf-8").strip(),
        "tools": operations, "skills": prompts, "steps": flow["steps"],
        "toolConfiguration": flow["toolConfiguration"],
        "catalog": {"decks": len(corpus), "pages": sum(int(row["slide_count"]) for row in corpus)},
    }
    (ROOT / "studio/studio-config.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
