import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from normalization.canonical import validate
from normalization.contracts import SOURCES, fields, schema_info
from normalization.engine import decimal, identifier, normalize
from normalization.evaluation import comparisons, coverage, cross_provider_checks, evaluate, reconcile, relationship_checks
from normalization.fixtures import generate
from normalization.mappings import MAPPINGS
from normalization.report import save_report
from normalization.__main__ import main


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = generate(count=6)
        cls.report = evaluate(cls.fixtures)

    def case(self, provider, entity, scenario="baseline"):
        return copy.deepcopy(next(c for c in self.fixtures["cases"] if c["provider"] == provider and c["entity"] == entity and c["scenario"] == scenario))

    def record(self, provider, entity, scenario="baseline"):
        case = self.case(provider, entity, scenario)
        return normalize(provider, entity, case["input"])[0]

    def test_all_fixtures_match_pinned_source_schemas_and_oracles(self):
        for result in self.report["results"]:
            with self.subTest(case=result["case_id"]):
                self.assertTrue(result["record"]["source_valid"])
                self.assertTrue(result["passed"], result)

    def test_all_supported_entities_have_evaluation_cases(self):
        observed = {(c["provider"], c["entity"]) for c in self.fixtures["cases"]}
        expected = {(p, e) for p, entities in SOURCES.items() for e in entities}
        self.assertEqual(observed, expected)

    def test_seeded_generation_is_reproducible_and_seed_changes_data(self):
        self.assertEqual(self.fixtures, generate(count=6))
        self.assertNotEqual(self.fixtures, generate(seed=43, count=6))

    def test_transformations_do_not_mutate_input(self):
        case = self.case("prismhr", "employee")
        before = copy.deepcopy(case)
        output = normalize("prismhr", "employee", case["input"])
        self.assertEqual(before, case)
        output[0]["source_data"]["firstName"] = "Edited"
        self.assertEqual(before, case)

    def test_unknown_codes_are_flagged_and_preserved(self):
        for provider in SOURCES:
            result = self.record(provider, "employee", "unknown_code")
            self.assertEqual(result["data"]["employment_status"], "unknown")
            self.assertTrue(any(d.get("raw") == "UNRECOGNIZED_STATUS" for d in result["diagnostics"]))
            self.assertIn("UNRECOGNIZED_STATUS", json.dumps(result["source_data"]))

    def test_tenant_status_labels_are_not_globally_assumed(self):
        case = self.case("isolved", "employee")
        case["input"]["context"].pop("status_lookup")
        output = normalize("isolved", "employee", case["input"])[0]
        self.assertEqual(output["data"]["employment_status"], "unknown")

    def test_zero_money_is_not_missing(self):
        result = self.record("prismhr", "employee", "zero_rate")
        self.assertEqual(result["data"]["compensation"]["hourly_rate"], "0")

    def test_missing_and_explicit_null_are_distinct(self):
        case = self.case("isolved", "employee", "missing_optional")
        self.assertNotIn("personal_email", normalize("isolved", "employee", case["input"])[0]["data"])
        case["input"]["records"][0]["emailAddress"] = None
        result = normalize("isolved", "employee", case["input"])[0]
        self.assertIn("personal_email", result["data"])
        self.assertIsNone(result["data"]["personal_email"])
        self.assertFalse(result["source_valid"])  # Source contract does not declare nullability.

    def test_arbitrary_fields_survive_in_extensions_and_original_source(self):
        case = self.case("isolved", "employee")
        case["input"]["records"][0]["futureProviderField"] = {"value": "kept"}
        record = normalize("isolved", "employee", case["input"])[0]
        self.assertEqual(record["extensions"]["futureProviderField.value"], "kept")
        self.assertEqual(record["source_data"], case["input"]["records"][0])

    def test_identifiers_are_scoped_and_delimiter_safe(self):
        ctx = {"tenant_id": "a:b", "company_id": "c"}
        left = identifier("prismhr", ctx, "employee", 1)
        right = identifier("prismhr", {"tenant_id": "a", "company_id": "b:c"}, "employee", 1)
        self.assertNotEqual(left, right)
        self.assertNotEqual(left, identifier("isolved", ctx, "employee", 1))
        self.assertNotEqual(identifier("isolved", {**ctx, "employee_id": 1}, "deduction", 2),
                            identifier("isolved", {**ctx, "employee_id": 3}, "deduction", 2))

    def test_prism_checking_and_pay_card_are_not_conflated(self):
        case = self.case("prismhr", "direct_deposit")
        case["input"]["records"][0]["accountType"] = "C"
        self.assertEqual(normalize("prismhr", "direct_deposit", case["input"])[0]["data"]["account_type"], "checking_or_pay_card")

    def test_leading_zero_bank_account_is_preserved(self):
        for provider in SOURCES:
            self.assertEqual(self.record(provider, "direct_deposit")["data"]["account_number"], "0000123400")

    def test_percentage_and_dollar_values_are_separate(self):
        result = self.record("isolved", "direct_deposit", "percentage_allocation")
        self.assertEqual(result["data"]["percentage"], "20")
        self.assertNotIn("amount", result["data"])

    def test_ambiguous_allocations_are_errors(self):
        case = self.case("isolved", "direct_deposit")
        case["input"]["records"][0]["percent"] = 20
        result = normalize("isolved", "direct_deposit", case["input"])[0]
        self.assertIn("ambiguous_allocation", [d["code"] for d in result["diagnostics"]])

    def test_isolved_net_sequence_is_documented_zero(self):
        case = self.case("isolved", "direct_deposit")
        row = case["input"]["records"][0]
        row.pop("amount")
        row["sequenceNumber"] = 0
        self.assertEqual(normalize("isolved", "direct_deposit", case["input"])[0]["data"]["allocation_method"], "remaining_balance")

    def test_negative_adjustments_remain_negative(self):
        self.assertEqual(self.record("isolved", "paycheck", "adjustment")["data"]["net_pay"], "-100")

    def test_employer_tax_is_excluded_from_employee_net(self):
        record = self.record("isolved", "paycheck")
        self.assertTrue(all(c["status"] == "passed" for c in reconcile(record)))
        record["data"]["taxes"][1]["amount"] = "999999"
        self.assertTrue(all(c["status"] == "passed" for c in reconcile(record)))

    def test_reconciliation_does_not_assume_absent_lines_are_zero(self):
        record = self.record("isolved", "paycheck")
        record["data"].pop("deductions")
        self.assertEqual(reconcile(record)[1]["status"], "insufficient_data")

    def test_ukg_does_not_invent_reported_totals_or_hour_units(self):
        record = self.record("ukg-ready", "paycheck")
        self.assertNotIn("gross_pay", record["data"])
        self.assertEqual(record["data"]["earnings"][0]["hours_raw"], 144000000)
        self.assertEqual(reconcile(record)[0]["status"], "insufficient_data")

    def test_record_validation_rejects_numeric_money(self):
        record = self.record("isolved", "paycheck")
        record["data"]["net_pay"] = 750
        self.assertTrue(validate(record))

    def test_decimal_rejects_nonfinite_and_boolean(self):
        for value in (True, "NaN", "Infinity", "-Infinity", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal(value)
        self.assertEqual(decimal("123.4500"), "123.4500")

    def test_context_is_required(self):
        for payload in ({}, {"context": {}, "records": []}, {"context": {"tenant_id": "x", "company_id": "y"}, "records": {}}):
            with self.assertRaises(ValueError):
                normalize("isolved", "employee", payload)

    def test_relationships_detect_broken_references(self):
        records = [r["record"] for r in self.report["results"]]
        self.assertFalse(any(r["status"] == "broken" for r in relationship_checks(records)))
        records = [r for r in records if not (r["provider"] == "isolved" and r["entity"] == "employee")]
        self.assertTrue(any(r["status"] == "broken" for r in relationship_checks(records)))

    def test_references_use_primary_snapshot_and_GET_ukg_schemas(self):
        for provider, entities in SOURCES.items():
            for entity in entities:
                _, _, evidence, _ = schema_info(provider, entity)
                self.assertNotIn("alternate", evidence)
        with self.assertRaises(ValueError):
            schema_info("ukg-ready", "company")

    def test_every_mapping_path_has_source_contract_evidence(self):
        for provider, entities in MAPPINGS.items():
            for entity, layout in entities.items():
                paths = [f["path"] for f in fields(provider, entity)]
                for path in layout:
                    with self.subTest(provider=provider, entity=entity, path=path):
                        self.assertTrue(any(p == path or p.startswith(path + ".") or p.startswith(path + "[") for p in paths))

    def test_coverage_does_not_count_extensions_as_semantic_mapping(self):
        rows = coverage(self.fixtures["cases"])
        self.assertGreater(sum(r["disposition"] == "extension_preserved" for r in rows), 0)
        self.assertLess(self.report["metrics"]["explicit_field_mapping"]["percent"], 100)

    def test_negative_controls_are_detected(self):
        self.assertTrue(all(c["detected"] for c in self.report["negative_controls"]))

    def test_equivalent_people_agree_across_providers_and_drift_is_detected(self):
        records = [copy.deepcopy(r["record"]) for r in self.report["results"]]
        self.assertTrue(all(c["passed"] for c in cross_provider_checks(records)))
        next(r for r in records if r["provider"] == "isolved" and r["entity"] == "employee")["data"]["first_name"] = "Wrong name"
        self.assertTrue(any(not c["passed"] for c in cross_provider_checks(records)))

    def test_missing_source_id_is_an_error(self):
        case = self.case("isolved", "employee")
        case["input"]["records"][0].pop("id")
        record = normalize("isolved", "employee", case["input"])[0]
        self.assertIn("missing_source_id", [d["code"] for d in record["diagnostics"]])

    def test_tampered_fixture_contract_fingerprint_is_rejected(self):
        fixture = copy.deepcopy(self.fixtures)
        fixture["contracts"] = {}
        with self.assertRaises(ValueError):
            evaluate(fixture)

    def test_reports_export_consistent_html_csv_json_and_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            save_report(self.report, directory)
            for file in ("index.html", "results.json", "coverage.csv", "canonical.schema.json", "normalized.sqlite", "normalized.json"):
                self.assertTrue((directory / file).is_file())
            self.assertNotIn("__REPORT_DATA__", (directory / "index.html").read_text(encoding="utf-8"))
            with closing(sqlite3.connect(directory / "normalized.sqlite")) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM records").fetchone()[0], len(self.report["results"]))

    def test_html_embedding_cannot_end_script_element(self):
        report = copy.deepcopy(self.report)
        report["limitations"].append("</script><script>alert('x')</script>")
        with tempfile.TemporaryDirectory() as tmp:
            save_report(report, tmp)
            text = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("</script><script>alert('x')", text)

    def test_cli_strict_validation_refuses_bad_input_and_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            case = self.case("isolved", "employee")
            case["input"]["records"][0]["hourlyRate"] = "not-money"
            (path / "in.json").write_text(json.dumps(case["input"]), encoding="utf-8")
            code = main(["normalize", "--provider", "isolved", "--entity", "employee", "--input", str(path / "in.json"), "--output", str(path / "out.json"), "--strict"])
            self.assertEqual(code, 1)
            self.assertFalse((path / "out.json").exists())
            (path / "in.json").write_text(json.dumps(self.case("isolved", "employee")["input"]), encoding="utf-8")
            args = ["normalize", "--provider", "isolved", "--entity", "employee", "--input", str(path / "in.json"), "--output", str(path / "out.json"), "--strict"]
            self.assertEqual(main(args), 0)
            before = (path / "out.json").read_bytes()
            self.assertEqual(main(args), 1)
            self.assertEqual(before, (path / "out.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
