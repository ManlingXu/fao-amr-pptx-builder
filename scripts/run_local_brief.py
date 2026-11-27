"""Build an editable, cited AMR brief on a local machine."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from presentation_search.local_brief import build_brief, restyle_brief


def main():
    if sys.argv[1:2] == ["restyle"]:
        parser = argparse.ArgumentParser(description="Apply another template to an existing draft.")
        parser.add_argument("--draft", type=Path, required=True)
        parser.add_argument("--template", type=Path, required=True)
        parser.add_argument("--output", type=Path, required=True)
        args = parser.parse_args(sys.argv[2:])
        try:
            restyle_brief(args.draft, args.template, args.output)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.exit(1, f"Template change: {exc}\n")
        print(args.output.resolve())
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--pages", required=True, type=int)
    parser.add_argument("--sector", action="append", choices=["animal", "one-health", "human"], default=[])
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / ".local" / "amr")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "amr-briefs")
    parser.add_argument("--model", help="Optional installed local Ollama model, e.g. qwen3:4b")
    parser.add_argument("--template", type=Path, help="Optional local PPTX/POTX with master layouts")
    parser.add_argument("--reflow", action="store_true", help="Arrange source evidence on uniform editable slides")
    args = parser.parse_args()
    try:
        summary = build_brief(args.corpus_dir, args.output_dir, topic=args.topic, pages=args.pages,
                              sectors=args.sector, model=args.model, template=args.template, reflow=args.reflow)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Local AMR brief: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
