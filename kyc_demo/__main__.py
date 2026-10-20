"""CLI: python -m kyc_demo {generate,run,eval}"""

import argparse
import json
from datetime import date
from pathlib import Path

from .evaluate import evaluate, to_markdown
from .extract import make_extractor
from .pipeline import run_case
from .synth import generate

DEFAULT_AS_OF = "2026-10-21"  # fixed so results are reproducible


def main() -> None:
    ap = argparse.ArgumentParser(prog="kyc_demo", description="KYC document extraction demo (synthetic data)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="create synthetic client files with ground truth")
    g.add_argument("--out", type=Path, default=Path("cases"))
    g.add_argument("--seed", type=int, default=7)

    for name, help_ in (("run", "process one client file"), ("eval", "score every case against truth.json")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("path", type=Path, nargs="?", default=Path("cases"))
        p.add_argument("--backend", choices=["rules", "ollama", "openai"], default="rules")
        p.add_argument("--model", help="model name for ollama/openai (default: $KYC_MODEL)")
        if name == "eval":
            p.add_argument("--report", type=Path, help="also write a Markdown report here")

    for p in sub.choices.values():
        p.add_argument("--as-of", default=DEFAULT_AS_OF, help="review date (YYYY-MM-DD)")

    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of)

    if args.cmd == "generate":
        cases = generate(args.out, as_of, args.seed)
        print(f"wrote {len(cases)} cases to {args.out}/")
    elif args.cmd == "run":
        print(json.dumps(run_case(args.path, make_extractor(args.backend, args.model), as_of),
                         indent=2, ensure_ascii=False))
    else:
        result = evaluate(args.path, make_extractor(args.backend, args.model), as_of)
        md = to_markdown(result)
        print(md)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(md)


if __name__ == "__main__":
    main()
