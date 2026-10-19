"""CLI for local normalization, reproducible fixtures and evaluation reports."""
import argparse
import json
import sys
from pathlib import Path

from .adapters import ADAPTERS, ENTITIES
from .references import all_readiness_issues, load_reference, readiness_issues
from .canonical import validate
from .contracts import SOURCES


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tada AI normalization lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-providers")
    commands.add_parser("check-inputs")
    run = commands.add_parser("normalize")
    run.add_argument("--provider", choices=ADAPTERS, required=True)
    run.add_argument("--entity", choices=ENTITIES, required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--strict", action="store_true", help="Refuse output containing source, canonical or transformation errors")
    for name in ("generate-fixtures", "demo", "evaluate"):
        cmd = commands.add_parser(name)
        if name != "evaluate":
            cmd.add_argument("--seed", type=int, default=42)
            cmd.add_argument("--count", type=int, default=24, help="Employees per provider, minimum 6")
        if name == "generate-fixtures":
            cmd.add_argument("--output", type=Path, default=Path("artifacts/fixtures.json"))
        else:
            cmd.add_argument("--output-dir", type=Path, default=Path("artifacts/report"))
        if name == "evaluate":
            cmd.add_argument("--input", type=Path, default=Path("artifacts/fixtures.json"))
    serve = commands.add_parser("serve")
    serve.add_argument("--directory", type=Path, default=Path("artifacts/report"))
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.command == "list-providers":
        print("\n".join(f"{p}: {', '.join(entities)}" for p, entities in SOURCES.items()))
        return 0
    if args.command == "check-inputs":
        issues = all_readiness_issues()
        print(json.dumps(issues, indent=2))
        return 2 if any(issues.values()) else 0
    if args.command == "serve":
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        from functools import partial
        if not (args.directory / "index.html").is_file():
            parser.error("Generate a report with the demo command first")
        server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(args.directory.resolve())))
        print(f"Report: http://127.0.0.1:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    if args.command in ("demo", "evaluate", "generate-fixtures"):
        from .fixtures import write_fixtures
        from .evaluation import evaluate
        from .report import save_report
        try:
            if args.command == "generate-fixtures":
                fixture_set = write_fixtures(args.output, args.seed, args.count)
                print(f"Generated {len(fixture_set['cases'])} cases: {args.output.resolve()}")
                return 0
            if args.command == "demo":
                fixture_set = write_fixtures(args.output_dir.parent / "fixtures.json", args.seed, args.count)
            else:
                fixture_set = json.loads(args.input.read_text(encoding="utf-8"))
            report = evaluate(fixture_set)
            path = save_report(report, args.output_dir)
            print(json.dumps({"report": str(path.resolve()), "records": report["metadata"]["record_count"], "metrics": report["metrics"]}, indent=2))
            failed = (any(not r["passed"] for r in report["results"])
                      or any(r["status"] == "failed" for r in report["reconciliations"])
                      or bool(report["duplicate_ids"])
                      or any(r["status"] == "broken" for r in report["relationships"])
                      or any(not c["detected"] for c in report["negative_controls"])
                      or any(not c["passed"] for c in report["cross_provider_checks"])
                      or report["metrics"]["determinism"]["passed"] != 1)
            return 1 if failed else 0
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    issues = readiness_issues(args.provider)
    if issues:
        print(json.dumps({"provider": args.provider, "readiness_issues": issues}, indent=2), file=sys.stderr)
        return 2
    try:
        with args.input.open(encoding="utf-8") as stream:
            response = json.load(stream)
        result = ADAPTERS[args.provider].normalize(args.entity, response, load_reference(args.provider))
        if args.strict and any(validate(r) or any(d["severity"] == "error" for d in r["diagnostics"]) for r in result):
            print("Strict validation failed; no output written", file=sys.stderr)
            return 1
        # Serialize first and refuse overwriting an existing file in this scaffold.
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    except (OSError, ValueError, TypeError, NotImplementedError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
