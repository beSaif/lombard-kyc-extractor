"""CLI: python -m kyc_demo {generate,fetch-real,run,eval,compare,serve}"""

import argparse
import json
from datetime import date
from pathlib import Path

GENERATED_AS_OF = "2026-10-21"  # the synthetic cases are drawn relative to this date, so the corpus is reproducible


def main() -> None:
    ap = argparse.ArgumentParser(prog="kyc_demo", description="KYC document extraction demo (synthetic data)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="create synthetic client files (3 quality tiers) with ground truth")
    g.add_argument("--out", type=Path, default=Path("cases"))
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--n", type=int, help="only the first N cases")
    g.add_argument("--suite", choices=["standard", "hard", "blind", "all"], default="all",
                   help="all = standard + hard; the blind suite is generated on its own (see kyc_demo/blind.py)")
    g.add_argument("--as-of", default=GENERATED_AS_OF, help="date the cases are drawn relative to (YYYY-MM-DD)")

    f = sub.add_parser("fetch-real", help="download the public specimen passports (kyc_demo/real.py) into cases/real/")
    f.add_argument("--out", type=Path, default=Path("cases"))
    f.add_argument("--as-of", default=GENERATED_AS_OF)

    r = sub.add_parser("run", help="process one client file and print the result")
    r.add_argument("case", type=Path)
    r.add_argument("-e", "--extractor", default="rules",
                   help="rules | oracle | azure:prebuilt | openai:<model>@<text|vision|both> | ollama:<model>@...")
    r.add_argument("--second", help="a second extractor to cross-check against")
    r.add_argument("--reader", choices=["auto", "text", "ocr"], default="auto")
    r.add_argument("--steps", action="store_true", help="include the full step trace")
    r.add_argument("--as-of", help="review date (YYYY-MM-DD); default: the case's truth.json date, else today")

    e = sub.add_parser("eval", help="score extractors on every case of the chosen tiers")
    e.add_argument("--cases", type=Path, default=Path("cases"))
    e.add_argument("-e", "--extractor", action="append", required=True, help="repeat to compare several")
    e.add_argument("--second", help="cross-check every extractor against this one")
    e.add_argument("--reader", choices=["auto", "text", "ocr"], default="auto")
    e.add_argument("--tiers", default="clean,scan,photo")
    e.add_argument("--limit", type=int, help="first N cases per tier")
    e.add_argument("--workers", type=int, help="parallel files (default: 6 for openai, else 1)")
    e.add_argument("--suite", choices=["standard", "hard", "blind", "real"], default="standard")
    e.add_argument("--as-of", help="review date for every case (YYYY-MM-DD); default: each case's own")

    c = sub.add_parser("compare", help="write results/comparison.md from every saved eval")
    c.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "results" / "comparison.md")

    s = sub.add_parser("serve", help="start the web UI's API on http://localhost:8000")
    s.add_argument("--port", type=int, default=8000)

    args = ap.parse_args()

    if args.cmd == "generate":
        dirs = []
        if args.suite == "blind":
            from .blind import generate as generate_blind
            dirs = generate_blind(args.out, date.fromisoformat(args.as_of))
        for suite in (["standard", "hard"] if args.suite == "all" else [] if args.suite == "blind" else [args.suite]):
            from .synth import generate
            dirs += generate(args.out, date.fromisoformat(args.as_of), args.seed, args.n, suite=suite)
        print(f"wrote {len(dirs)} case folders to {args.out}/{{clean,scan,photo}}/")
    elif args.cmd == "fetch-real":
        from .real import fetch
        dirs = fetch(args.out, date.fromisoformat(args.as_of))
        print(f"wrote {len(dirs)} specimen passports to {args.out}/real/")
    elif args.cmd == "run":
        from .extract import make_extractor
        from .pipeline import run_case
        truth = args.case / "truth.json"
        as_of = (date.fromisoformat(args.as_of) if args.as_of else
                 date.fromisoformat(json.loads(truth.read_text())["as_of"]) if truth.exists() else date.today())
        res = run_case(args.case, make_extractor(args.extractor), as_of, args.reader,
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
            reports.append(run_eval(args.cases, spec, args.tiers.split(","),
                                    date.fromisoformat(args.as_of) if args.as_of else None,
                                    args.limit, workers, args.second, args.reader, suite=args.suite))
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
