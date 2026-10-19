"""Starter plumbing checks only. These do not assess transformation correctness."""
import contextlib
import io
import unittest

from normalization.__main__ import main
from normalization.adapters import ADAPTERS, ENTITIES
from normalization.references import all_readiness_issues, load_reference


class StarterChecks(unittest.TestCase):
    def test_expected_providers_and_entities_are_exposed(self):
        self.assertEqual(set(ADAPTERS), {"prismhr", "isolved", "ukg-ready"})
        self.assertTrue({"company", "employee", "payroll", "direct_deposit", "deduction", "paycheck", "payroll_run"}.issubset(ENTITIES))

    def test_reference_readiness_matches_distributed_materials(self):
        issues = all_readiness_issues()
        self.assertEqual(load_reference("prismhr")["lookup_status"], "verified")
        self.assertEqual(issues["prismhr"], [])
        for provider in ("isolved", "ukg-ready"):
            with self.subTest(provider=provider):
                ref = load_reference(provider)
                self.assertEqual(ref["lookup_status"], "verified")
                self.assertTrue(ref["lookups"])
                self.assertEqual(ref["distribution"]["status"], "user_approved_private_upload")
                self.assertFalse(ref["distribution"]["provider_redistribution_permission_verified"])
                self.assertEqual(issues[provider], [])

    def test_adapters_require_explicit_context_and_source_records(self):
        for provider, adapter in ADAPTERS.items():
            for entity in ENTITIES:
                with self.subTest(provider=provider, entity=entity):
                    with self.assertRaises(ValueError):
                        adapter.normalize(entity, None, load_reference(provider))

    def test_distributed_local_pack_is_ready(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check-inputs"]), 0)


if __name__ == "__main__":
    unittest.main()
