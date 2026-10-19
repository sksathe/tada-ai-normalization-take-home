"""Transparent counts, independent expected values, reconciliation and negative controls."""
import copy
import platform
import statistics
import time
from collections import Counter
from decimal import Decimal

from .canonical import validate
from .contracts import SOURCES, fields, fingerprints
from .engine import LINE_RULES, MISSING, flatten, get, normalize, path_pattern
from .mappings import MAPPINGS


def metric(passed, total):
    return {"passed": passed, "total": total, "percent": round(passed / total * 100, 2) if total else None}


def coverage(cases):
    exercised = {}
    for case in cases:
        key = case["provider"], case["entity"]
        exercised.setdefault(key, set()).update(path_pattern(p) for p, _ in flatten(case["input"]["records"][0]))
    result = []
    for provider, entities in SOURCES.items():
        for entity in entities:
            explicit = dict(MAPPINGS[provider][entity])
            if entity == "paycheck":
                for dest, (source, layout) in LINE_RULES[provider].items():
                    explicit.update({f"{source}[].{f}": (f"{dest}[].{t}", kind) for f, (t, kind) in layout.items()})
            for field in fields(provider, entity):
                path = field["path"]
                target = explicit.get(path)
                parent = next((p for p in explicit if path.startswith(p + ".") or path.startswith(p + "[")), None)
                disposition = "normalized" if target else "structured_preserved" if parent else "extension_preserved"
                result.append({"provider": provider, "entity": entity, **field, "disposition": disposition,
                               "canonical_field": target[0] if target else explicit[parent][0] if parent else None,
                               "rule": target[1] if target else "retain", "exercised": path in exercised.get((provider, entity), set())})
    return result


def comparisons(data, expected):
    return [{"field": path, "expected": value, "actual": get(data, path), "passed": get(data, path, MISSING) == value}
            for path, value in expected.items()]


def total_lines(data, key, field="amount", predicate=None):
    rows = data.get(key)
    if not isinstance(rows, list):
        return None
    total = Decimal(0)
    for row in rows:
        if predicate:
            include = predicate(row)
            if include is None:
                return None
            if not include:
                continue
        if row.get(field) is None:
            return None
        total += Decimal(row[field])
    return total


def reconcile(record):
    if record["entity"] != "paycheck":
        return []
    data, provider = record["data"], record["provider"]
    output = []

    def check(name, actual, expected, reason="Required totals or complete line details are absent"):
        delta = actual - expected if actual is not None and expected is not None else None
        output.append({"record_id": record["id"], "provider": provider, "check": name,
                       "status": "insufficient_data" if delta is None else "passed" if abs(delta) <= Decimal("0.01") else "failed",
                       "actual": str(actual) if actual is not None else None,
                       "expected": str(expected) if expected is not None else None,
                       "difference": str(delta) if delta is not None else None,
                       "reason": reason if delta is None else None})

    gross = Decimal(data["gross_pay"]) if data.get("gross_pay") is not None else None
    net = Decimal(data["net_pay"]) if data.get("net_pay") is not None else None
    if provider == "prismhr":
        # Do not multiply Earning.payAmount: source describes a per-hour/unit value.
        earned = (Decimal(data["timesheet_earnings"]) + Decimal(data["other_earnings_total"])) if all(data.get(k) is not None for k in ("timesheet_earnings", "other_earnings_total")) else None
        taxes = total_lines(data, "employee_taxes")
        deductions = total_lines(data, "deductions")
        other = total_lines(data, "other_deductions")
        check("earnings_to_reported_gross", gross, earned)
        expected_net = gross - taxes - deductions - other if all(v is not None for v in (gross, taxes, deductions, other)) else None
        check("gross_to_net", net, expected_net)
    elif provider == "isolved":
        earned = total_lines(data, "earnings", predicate=lambda row: None if "is_memo" not in row else not row["is_memo"])
        taxes = total_lines(data, "taxes", predicate=lambda row: row.get("is_employee"))
        deductions = total_lines(data, "deductions")
        garnishments = total_lines(data, "garnishments")
        check("earnings_to_reported_gross", gross, earned)
        expected_net = gross - taxes - deductions - garnishments if all(v is not None for v in (gross, taxes, deductions, garnishments)) else None
        check("gross_to_net", net, expected_net)
    else:
        earned = total_lines(data, "earnings")
        check("earnings_to_reported_gross", None, earned, "Cached UKG pay-statement schema has no reported gross total")
        deductions = total_lines(data, "deductions")
        taxes = total_lines(data, "taxes", "employee_amount")
        payments = total_lines(data, "payments")
        expected_cash = earned - taxes - deductions if all(v is not None for v in (earned, taxes, deductions)) else None
        check("line_cash_flow_to_payments", payments, expected_cash)
    return output


def relationship_checks(records):
    ids = {r["id"] for r in records}
    rows = []
    for record in records:
        for name, target in record["relationships"].items():
            state = "resolved_record" if target in ids else "context_only" if name == "company_id" and record["provider"] == "ukg-ready" else "broken"
            rows.append({"record_id": record["id"], "relationship": name, "target": target, "status": state})
    return rows


def negative_controls(records):
    """Inject known faults into already-normalized output; require detectors to catch them."""
    sample = next(r for r in records if r["provider"] == "isolved" and r["entity"] == "paycheck")
    bad_net = copy.deepcopy(sample)
    bad_net["data"]["net_pay"] = "99999"
    bad_ref = copy.deepcopy(sample)
    bad_ref["relationships"]["employee_id"] = "missing-employee"
    bad_type = copy.deepcopy(sample)
    bad_type["data"]["gross_pay"] = 123.45
    bad_field = copy.deepcopy(sample)
    bad_field["data"].pop("net_pay", None)
    return [
        {"fault": "incorrect_net_pay", "detected": any(x["status"] == "failed" for x in reconcile(bad_net))},
        {"fault": "broken_employee_link", "detected": any(x["status"] == "broken" for x in relationship_checks([*records, bad_ref]))},
        {"fault": "numeric_money_in_canonical_output", "detected": bool(validate(bad_type))},
        {"fault": "dropped_expected_field", "detected": not comparisons(bad_field["data"], {"net_pay": sample["data"]["net_pay"]})[0]["passed"]},
    ]


def cross_provider_checks(records):
    groups = {}
    for record in records:
        if record["entity"] == "employee":
            groups.setdefault(record["source"]["record_id"], {})[record["provider"]] = record
    checks = []
    for source_id, providers in sorted(groups.items()):
        if len(providers) != 3:
            continue
        for field in ("first_name", "last_name", "employment_status", "personal_email"):
            values = {p: get(r["data"], field, MISSING) for p, r in providers.items()}
            if all(v is MISSING for v in values.values()):
                continue
            checks.append({"synthetic_person": source_id, "field": field,
                           "values": {p: None if v is MISSING else v for p, v in values.items()},
                           "passed": all(v == next(iter(values.values())) for v in values.values())})
    return checks


def evaluate(fixture_set):
    if fixture_set.get("contracts") != fingerprints():
        raise ValueError("Fixture contract fingerprints do not match pinned local references")
    cases, results, records = fixture_set["cases"], [], []
    start = time.perf_counter()
    for case in cases:
        record = normalize(case["provider"], case["entity"], case["input"])[0]
        assertions = comparisons(record["data"], case["expected"])
        canonical_errors = validate(record)
        results.append({"case_id": case["case_id"], "provider": case["provider"], "entity": case["entity"],
                        "scenario": case["scenario"], "assertions": assertions,
                        "passed": all(a["passed"] for a in assertions) and not canonical_errors and not any(d["severity"] == "error" for d in record["diagnostics"]),
                        "canonical_errors": canonical_errors, "record": record})
        records.append(record)
    elapsed = time.perf_counter() - start
    reconciliations = [item for r in records for item in reconcile(r)]
    for run in (r for r in records if r["entity"] == "payroll_run"):
        checks = [r for r in records if r["entity"] == "paycheck" and r["relationships"].get("payroll_run_id") == run["id"]]
        amounts = [r["data"].get("gross_pay") for r in checks]
        available = run["data"].get("gross_pay") is not None and bool(checks) and all(a is not None for a in amounts)
        expected = sum((Decimal(a) for a in amounts), Decimal(0)) if available else None
        actual = Decimal(run["data"]["gross_pay"]) if available else None
        reconciliations.append({"record_id": run["id"], "provider": run["provider"], "check": "paychecks_to_run_gross",
                               "status": "insufficient_data" if not available else "passed" if abs(actual - expected) <= Decimal("0.01") else "failed",
                               "actual": str(actual) if available else None, "expected": str(expected) if available else None,
                               "reason": None if available else "Reported run gross or complete linked paycheck totals are unavailable"})
    links = relationship_checks(records)
    inventory = coverage(cases)
    controls = negative_controls(records)
    equivalence = cross_provider_checks(records)
    assertions = [a for r in results for a in r["assertions"]]
    unknown = [r for r in results if r["scenario"] == "unknown_code"]
    repeats = []
    for _ in range(3):
        start = time.perf_counter()
        replay = [normalize(c["provider"], c["entity"], c["input"])[0] for c in cases]
        repeats.append(time.perf_counter() - start)
    deterministic = all(a == b for a, b in zip(records, replay))
    ids = Counter(r["id"] for r in records)
    return {"metadata": {"seed": fixture_set["seed"], "synthetic_only": True, "contracts": fingerprints(),
                         "python": platform.python_version(), "platform": platform.platform(),
                         "record_count": len(records), "first_pass_seconds": elapsed,
                         "benchmark": {"runs": 3, "median_seconds": statistics.median(repeats),
                                       "records_per_second": round(len(records) / statistics.median(repeats), 1),
                                       "scope": "Warm in-memory normalization including source validation; excludes fixture generation, disk I/O, report rendering and canonical validation"}},
            "metrics": {
                "semantic_accuracy": metric(sum(a["passed"] for a in assertions), len(assertions)),
                "case_pass_rate": metric(sum(r["passed"] for r in results), len(results)),
                "source_validation": metric(sum(r["source_valid"] for r in records), len(records)),
                "canonical_validation": metric(sum(not r["canonical_errors"] for r in results), len(results)),
                "relationship_integrity": metric(sum(l["status"] == "resolved_record" for l in links), len(links)),
                "unknown_code_handling": metric(sum(r["record"]["data"].get("employment_status") == "unknown" and any(d["code"] == "unknown_enum" for d in r["record"]["diagnostics"]) for r in unknown), len(unknown)),
                "determinism": metric(int(deterministic), 1),
                "negative_controls": metric(sum(c["detected"] for c in controls), len(controls)),
                "cross_provider_equivalence": metric(sum(c["passed"] for c in equivalence), len(equivalence)),
                "explicit_field_mapping": metric(sum(f["disposition"] == "normalized" for f in inventory), len(inventory)),
                "fixture_field_exercise": metric(sum(f["exercised"] for f in inventory), len(inventory)),
                "reconciliation": metric(sum(r["status"] == "passed" for r in reconciliations), sum(r["status"] != "insufficient_data" for r in reconciliations)),
            }, "coverage": inventory, "results": results, "reconciliations": reconciliations,
            "relationships": links, "negative_controls": controls, "cross_provider_checks": equivalence,
            "duplicate_ids": [key for key, count in ids.items() if count > 1],
            "limitations": [
                "Scores describe synthetic fixtures and asserted fields only; they are not production accuracy estimates.",
                "Field denominator covers selected response schemas and reachable leaves, not every provider endpoint.",
                "Structured preservation and extension retention are separate from semantic field normalization.",
                "UKG company relationships are context anchors; a company master response schema is not supplied in the selected pack.",
                "isolved employee status mappings use explicitly supplied synthetic tenant lookups, not invented global enums.",
                "Payroll reconciliation assumes the selected arrays are complete for these synthetic records; live completeness is unverified.",
                "UKG paycheck hours are preserved as raw values because the selected schema does not document their unit.",
                "Optional live API access and provider writes are not exercised by this offline evaluation.",
            ]}
