"""Read only the pinned local contracts. Never resolve remote schema references."""
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "AOS.PayrollOffice.RestAPI.Models."

# Each selection is a response record, not necessarily the endpoint's envelope.
SOURCES = {
    "prismhr": {
        "company": "ClientMaster", "employee": "Employee", "direct_deposit": "AchVoucher",
        "deduction": "EmployeeDeductions-Deduction", "payroll_run": "PayrollHistory",
        "paycheck": "PayrollVoucher", "compensation": "Compensation",
    },
    "isolved": dict(zip(
        ("company", "employee", "direct_deposit", "deduction", "payroll_run", "paycheck"),
        (PREFIX + n for n in ("LegalModel", "EmployeeModel", "EmployeeDirectDepositModel",
                             "EmployeePayItemModel", "PayrollRunHistoryModel", "CheckModel")))),
    "ukg-ready": {"employee": 106, "direct_deposit": 85, "deduction": 133,
                  "payroll_run": 360, "paycheck": 364, "compensation": 33,
                  "demographics": 134, "pay_info": 159, "custom_fields": 142},
}
ENDPOINTS = {
    "prismhr": {"company": "/clientMaster/v1/getClientMaster", "employee": "/employee/v1/getEmployee",
                "deduction": "/deductions/v1/getDeductions", "paycheck": "/payroll/v1/getPayrollVoucherById",
                "direct_deposit": "/employee/v1/getEmployee (directDeposit.achVoucher)",
                "compensation": "/employee/v1/getEmployee (compensation)",
                "payroll_run": "PayrollHistory record; endpoint binding unresolved"},
    "isolved": {"company": "/api/clients/{clientId}/legals/{id}",
                "employee": "/api/clients/{clientId}/legals/{legalId}/employees/{id}",
                "direct_deposit": "/api/clients/{clientId}/legals/{legalId}/employees/{employeeId}/directdeposits",
                "deduction": "/api/clients/{clientId}/legals/{legalId}/employees/{employeeId}/payItems",
                "payroll_run": "/api/clients/{clientId}/legals/{legalId}/paygroupId/{paygroupId}/payrollRunHistory",
                "paycheck": "/api/clients/{clientId}/legals/{legalId}/employees/{employeeId}/checks/{id}"},
}


@lru_cache(maxsize=None)
def document(provider):
    path = ROOT / "contracts" / provider
    file = {"prismhr": "openapi/prismhr-2025.09.openapi.json",
            "isolved": "openapi/isolved-v6.swagger.json",
            "ukg-ready": "reference-schemas.json"}[provider]
    return json.loads((path / file).read_text(encoding="utf-8"))


def pointer(doc, ref):
    if not ref.startswith("#/"):
        raise ValueError("Only local contract references are supported")
    value = doc
    for part in ref[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


@lru_cache(maxsize=None)
def schema_info(provider, entity):
    key = SOURCES.get(provider, {}).get(entity)
    if key is None:
        raise ValueError(f"No evidenced source schema for {provider}/{entity}")
    doc = document(provider)
    if provider == "ukg-ready":
        item = doc["schemas"][key]
        if item["method"] != "GET" or "resp" not in item["source_container_id"]:
            raise ValueError("UKG selection must be a GET response schema")
        schema = item["schema"]
        evidence = f"contracts/ukg-ready/reference-schemas.json#/schemas/{key}/schema"
        return schema, schema, evidence, item["source_page"]
    section = "components/schemas" if provider == "prismhr" else "definitions"
    ref = "#/" + section + "/" + key
    filename = "prismhr-2025.09.openapi.json" if provider == "prismhr" else "isolved-v6.swagger.json"
    return pointer(doc, ref), doc, f"contracts/{provider}/openapi/{filename}{ref}", ENDPOINTS[provider][entity]


def resolve(schema, doc):
    return pointer(doc, schema["$ref"]) if "$ref" in schema else schema


def fields(provider, entity):
    """Enumerate reachable contract leaves, with cycle boundaries marked explicitly."""
    root, doc, evidence, _ = schema_info(provider, entity)
    result = []

    def walk(schema, path, cite, seen):
        if "$ref" in schema:
            ref = schema["$ref"]
            if ref in seen:
                result.append({"path": path, "type": "recursive", "evidence": cite, "description": "Recursive schema boundary"})
                return
            walk(pointer(doc, ref), path, evidence.split("#")[0] + ref, seen | {ref})
            return
        if "properties" in schema:
            for name, child in schema["properties"].items():
                walk(child, f"{path}.{name}".strip("."), cite + "/properties/" + name, seen)
        elif schema.get("type") == "array":
            walk(schema.get("items", {}), path + "[]", cite + "/items", seen)
        else:
            result.append({"path": path, "type": schema.get("type", "unspecified"),
                           "description": schema.get("description", ""), "evidence": cite,
                           "enum": schema.get("enum")})
    walk(root, "", evidence, set())
    return result


@lru_cache(maxsize=None)
def validator(provider, entity):
    from jsonschema import Draft4Validator, Draft7Validator, FormatChecker
    schema, doc, _, _ = schema_info(provider, entity)
    # Embed the selected schema alongside its original reference namespace.
    bundle = copy.deepcopy(doc)
    bundle.update(copy.deepcopy(schema))
    cls = Draft4Validator if provider != "prismhr" else Draft7Validator
    return cls(bundle, format_checker=FormatChecker())


def validate_source(provider, entity, record):
    return [{"path": ".".join(map(str, e.absolute_path)), "message": e.message}
            for e in sorted(validator(provider, entity).iter_errors(record), key=lambda e: str(e.path))]


def fingerprints():
    paths = [ROOT / "contracts/prismhr/openapi/prismhr-2025.09.openapi.json",
             ROOT / "contracts/isolved/openapi/isolved-v6.swagger.json",
             ROOT / "contracts/ukg-ready/reference-schemas.json"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}
