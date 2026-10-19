"""Portable HTML and machine-readable evaluation artifacts, without external assets."""
import csv
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .canonical import SCHEMA


def save_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    def write_json(name, value):
        (directory / name).write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    write_json("results.json", report)
    write_json("canonical.schema.json", SCHEMA)
    write_json("normalized.json", [r["record"] for r in report["results"]])
    with (directory / "coverage.csv").open("w", newline="", encoding="utf-8") as stream:
        columns = ["provider", "entity", "path", "disposition", "canonical_field", "rule", "exercised", "evidence"]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["coverage"])
    # Rebuild a local analytical snapshot. No live credentials or downloaded records.
    with closing(sqlite3.connect(directory / "normalized.sqlite")) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
              id TEXT PRIMARY KEY, provider TEXT NOT NULL, entity TEXT NOT NULL,
              company_id TEXT NOT NULL, employee_id TEXT, payroll_run_id TEXT, data_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS diagnostics (
              record_id TEXT NOT NULL, severity TEXT NOT NULL, code TEXT NOT NULL, detail_json TEXT NOT NULL);
            DELETE FROM diagnostics;
            DELETE FROM records;
        """)
        for result in report["results"]:
            r = result["record"]
            db.execute("INSERT OR IGNORE INTO records VALUES (?, ?, ?, ?, ?, ?, ?)", (
                r["id"], r["provider"], r["entity"], r["relationships"]["company_id"],
                r["relationships"].get("employee_id"), r["relationships"].get("payroll_run_id"), json.dumps(r["data"])))
            db.executemany("INSERT INTO diagnostics VALUES (?, ?, ?, ?)",
                           [(r["id"], d["severity"], d["code"], json.dumps(d)) for d in r["diagnostics"]])
    embedded = json.dumps(report, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    (directory / "index.html").write_text(template.replace("__REPORT_DATA__", embedded), encoding="utf-8")
    return directory / "index.html"
