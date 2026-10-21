"""CLI: python -m kyc_demo {generate,run,eval,compare,serve}"""

import argparse
import json
from datetime import date
from pathlib import Path

DEFAULT_AS_OF = "2026-10-21"  # fixed so results are reproducible


def main() -> None:
    ap = argparse.ArgumentParser(prog="kyc_demo", description="KYC document extraction demo (synthetic data)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="create synthetic client files (3 quality tiers) with ground truth")
    g.add_argument("--out", type=Path, default=Path("cases"))
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--n", type=int, help="only the first N cases")

    r = sub.add_parser("run", help="process one client file and print the result")
    r.add_argument("case", type=Path)
    r.add_argument("-e", "--extractor", default="rules", help="rules | openai:<model>@<text|vision|both> | ollama:<model>@...")
    r.add_argument("--second", help="a second extractor to cross-check against")
    r.add_argument("--reader", choices=["auto", "text", "ocr"], default="auto")
    r.add_argument("--steps", action="store_true", help="include the full step trace")

    e = sub.add_parser("eval", help="score extractors on every case of the chosen tiers")
    e.add_argument("--cases", type=Path, default=Path("cases"))
    e.add_argument("-e", "--extractor", action="append", required=True, help="repeat to compare several")
    e.add_argument("--second", help="cross-check every extractor against this one")
    e.add_argument("--reader", choices=["auto", "text", "ocr"], default="auto")
    e.add_argument("--tiers", default="clean,scan,photo")
    e.add_argument("--limit", type=int, help="first N cases per tier")
    e.add_argument("--workers", type=int, help="parallel files (default: 6 for openai, else 1)")

    c = sub.add_parser("compare", help="write results/comparison.md from every saved eval")
    c.add_argument("--out", type=Path, default=Path("results/comparison.md"))

    s = sub.add_parser("serve", help="start the web UI's API on http://localhost:8000")
    s.add_argument("--port", type=int, default=8000)

    for p in (g, r, e):
        p.add_argument("--as-of", default=DEFAULT_AS_OF, help="review date (YYYY-MM-DD)")
    args = ap.parse_args()

    if args.cmd == "generate":
        from .synth import generate
        dirs = generate(args.out, date.fromisoformat(args.as_of), args.seed, args.n)
        print(f"wrote {len(dirs)} case folders to {args.out}/{{clean,scan,photo}}/")
    elif args.cmd == "run":
        from .extract import make_extractor
        from .pipeline import run_case
        res = run_case(args.case, make_extractor(args.extractor), date.fromisoformat(args.as_of), args.reader,
                       make_extractor(args.second) if args.second else None)
        if not args.steps:
            res.pop("steps")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "eval":
        from .evaluate import comparison_markdown, run_eval
        reports = []
        for spec in args.extractor:
            print(f"== {spec}")
            workers = args.workers or (6 if spec.startswith("openai") else 1)
            reports.append(run_eval(args.cases, spec, args.tiers.split(","), date.fromisoformat(args.as_of),
                                    args.limit, workers, args.second, args.reader))
        print(comparison_markdown(reports))
    elif args.cmd == "compare":
        from .evaluate import comparison_markdown, load_reports
        md = comparison_markdown(load_reports())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md)
        print(md)
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("kyc_demo.web:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
