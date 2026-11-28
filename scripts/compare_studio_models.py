"""Compare the offline Studio and locally installed Ollama models on the same brief.

Prepare a sample or full corpus, start Ollama, and pass --corpus and --output.
No remote model provider is accepted by this runner.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from presentation_search import local_model
from presentation_search.studio_service import StudioService

BRIEF = "Zambia outreach to livestock farmers and traditional leaders on antimicrobial stewardship"
SETTINGS = {"count": 2, "audience": "Veterinary outreach coordinators", "mode": "reconstruction",
            "language": "en", "template": "original"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", action="append", help="Installed local Ollama model; repeat for additional runs.")
    args = parser.parse_args()
    corpus = args.corpus.resolve()
    if not (corpus / "verified.csv").exists():
        manifests = sorted(corpus.glob("*/verified.csv"))
        if len(manifests) != 1:
            parser.error("Select exactly one verified corpus containing verified.csv.")
        corpus = manifests[0].parent
    report = {"input_corpus": "Prepared local manifest", "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "platform": platform.system() + " " + platform.machine(),
              "brief": BRIEF, "settings": SETTINGS, "model_calls_to_paid_services": 0,
              "corpus_manifest_sha256": hashlib.sha256((corpus / "verified.csv").read_bytes()).hexdigest(),
              "method": "One matched Studio drafting turn per provider using a preloaded source index. Wall time includes any model load; Ollama reports token counts and inference times separately. Source identity is checked against the offline control. One case measures functionality and supports a qualitative review.",
              "runs": []}

    with tempfile.TemporaryDirectory() as temp:
        service = StudioService(corpus, Path(temp))
        report["corpus_counts"] = service.snapshot(service.new_session())["stats"]
        baseline = None
        for model in ["offline", *(args.model or ["qwen3:4b"])]:
            provider = "offline" if model == "offline" else "ollama"
            if provider == "ollama":
                os.environ["PPT_STUDIO_OLLAMA_MODEL"] = model
            run = {"provider": provider, "model": model, "calls": []}
            if provider == "ollama":
                try:
                    with httpx.Client(base_url="http://127.0.0.1:11434",trust_env=False,timeout=8) as client:
                        run["ollama_version"] = client.get("/api/version").json()["version"]
                        tags = client.get("/api/tags").json()["models"]
                        meta = next((m for m in tags if m["name"] == model), {})
                        run["model_digest"] = meta.get("digest")
                        run["weights"] = meta.get("details", {})
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    run["environment_message"] = str(exc)
            original = local_model._post_json
            def measured(client, path, payload):
                response = original(client, path, payload)
                if path == "/api/chat":
                    metrics = {k:response[k] for k in ("prompt_eval_count", "eval_count", "done_reason") if k in response}
                    for key in ("total_duration","load_duration","prompt_eval_duration","eval_duration"):
                        if key in response:
                            metrics[key + "_seconds"] = round(response[key] / 1e9,3)
                    metrics["page_ids_returned"] = []
                    try:
                        structured = json.loads(response["message"]["content"])
                        metrics["page_ids_returned"] = [item.get("id") for item in structured["pages"]]
                        metrics["output_field_lengths"] = [
                            {f:len(item[f]) if isinstance(item.get(f), str) else None
                             for f in ("title", "body", "notes")} for item in structured["pages"]
                        ]
                    except (KeyError, TypeError, ValueError):
                        pass
                    run["calls"].append(metrics)
                return response

            started = time.perf_counter()
            try:
                with patch.object(local_model, "_post_json", measured):
                    state = service.new_session()
                    result = service.turn(state, BRIEF, {**SETTINGS, "model": provider})
                slides = result["slides"]
                run.update({"status":"completed", "model_used":result["model_used"], "warnings":result["warnings"]})
                run["pages"] = [{key:page[key] for key in ("title","body","notes","source","page","url","evidence","id")} for page in slides]
                identity = [(p["id"],p["source"],p["page"],p["url"],p["evidence"]) for p in slides]
                if model == "offline":
                    baseline = identity
                run["checks"] = {
                    "requested_pages_present": len(slides) == SETTINGS["count"],
                    "source_ids_urls_pages_evidence_match_control": baseline is not None and identity == baseline,
                    "notes_nonempty": bool(slides) and all(p["notes"].strip() for p in slides),
                    "unmatched_numeric_strings_in_bodies": [n for p in slides for n in re.findall(r"\b\d+(?:[.,]\d+)?\b",p["body"]) if n not in p["evidence"]],
                }
            except (ValueError, httpx.HTTPError, OSError) as exc:
                run.update({"status":"failed","error":str(exc)})
            run["wall_seconds"] = round(time.perf_counter() - started,3)
            report["runs"].append(run)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            draft = args.output.with_suffix(".tmp")
            draft.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            draft.replace(args.output)
            print(model,run["status"],run["wall_seconds"],flush=True)


if __name__ == "__main__":
    main()
