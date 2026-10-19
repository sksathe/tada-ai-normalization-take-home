"""Pure, deterministic transformations with source retention and diagnostics."""
import copy
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from .contracts import schema_info, validate_source
from .mappings import ENUMS, MAPPINGS

MISSING = object()


def get(value, path, default=None):
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def put(value, path, item):
    parts = path.split(".")
    for part in parts[:-1]:
        value = value.setdefault(part, {})
    value[parts[-1]] = item


def decimal(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a decimal")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("Decimal must be finite")
    return format(result, "f")


def identifier(provider, context, entity, source_id):
    pieces = [provider, context["tenant_id"], context["company_id"], entity, str(source_id)]
    if entity in ("direct_deposit", "deduction", "compensation", "demographics", "pay_info", "custom_fields"):
        pieces.insert(-1, str(context.get("employee_id", "")))
    return ":".join(quote(str(p), safe="") for p in pieces)


def flatten(value, prefix=""):
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from flatten(item, f"{prefix}.{key}".strip("."))
    elif isinstance(value, list) and value:
        for i, item in enumerate(value):
            yield from flatten(item, f"{prefix}[{i}]")
    else:
        yield prefix, value


def path_pattern(path):
    return re.sub(r"\[\d+\]", "[]", path)


def transform_value(value, kind, context):
    if value is None:
        return None
    if kind == "copy":
        return copy.deepcopy(value)
    if kind == "decimal":
        if value == "":
            return None
        return decimal(value)
    if kind == "integer":
        result = Decimal(decimal(value))
        if result != result.to_integral_value():
            raise ValueError("Expected a whole number")
        return int(result)
    if kind == "date":
        if value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("Expected ISO date or timestamp")
        if "T" in value:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            date.fromisoformat(value)
        return value
    choices = context.get("status_lookup", {}) if kind == "tenant_status" else ENUMS[kind]
    if str(value) not in choices:
        raise LookupError(f"Unmapped {kind} code")
    result = choices[str(value)]
    if kind == "tenant_status" and result not in {"active", "inactive", "on_leave", "terminated", "pending", "unknown"}:
        raise ValueError("Invalid canonical status in tenant lookup")
    return result


LINE_RULES = {
 "prismhr": {
  "employee_taxes": ("employeeTax", {"empTaxDeductCode": ("code", "copy"), "empTaxAmount": ("amount", "decimal")}),
  "deductions": ("deduction", {"deductCode": ("code", "copy"), "deductAmount": ("amount", "decimal")}),
  "other_deductions": ("otherDeduction", {"otherDeductCode": ("code", "copy"), "otherDeductAmount": ("amount", "decimal")}),
  "earnings": ("earning", {"payCode": ("code", "copy"), "hoursWorked": ("hours", "decimal"), "hoursUnits": ("units", "decimal"), "unitRate": ("rate", "decimal"), "payAmount": ("pay_per_hour_or_unit", "decimal")}),
  "other_earnings": ("otherEarningsDetail", {"otherEarnCode": ("code", "copy"), "otherEarnAmount": ("amount", "decimal")}),
  "employer_contributions": ("employerContributions", {"code": ("code", "copy"), "amount": ("amount", "decimal")}),
 },
 "isolved": {
  "earnings": ("earnings", {"itemCode": ("code", "copy"), "checkDollars": ("amount", "decimal"), "checkHours": ("hours", "decimal"), "isMemoEarning": ("is_memo", "copy")}),
  "deductions": ("deductions", {"itemCode": ("code", "copy"), "checkDollars": ("amount", "decimal")}),
  "garnishments": ("garnishments", {"itemCode": ("code", "copy"), "checkDollars": ("amount", "decimal")}),
  "taxes": ("taxes", {"itemCode": ("code", "copy"), "checkDollars": ("amount", "decimal"), "isEmployeeTax": ("is_employee", "copy")}),
  "benefits": ("benefits", {"itemCode": ("code", "copy"), "checkDollars": ("amount", "decimal")}),
 },
 "ukg-ready": {
  "earnings": ("earnings", {"earning.code": ("code", "copy"), "ee_amount": ("amount", "decimal"), "hours": ("hours_raw", "integer"), "quantity": ("quantity", "decimal"), "base_rate": ("rate", "decimal")}),
  "deductions": ("deductions", {"deduction.code": ("code", "copy"), "ee_amount": ("amount", "decimal"), "er_amount": ("employer_amount", "decimal")}),
  "taxes": ("taxes", {"company_tax.code": ("code", "copy"), "ee_amount": ("employee_amount", "decimal"), "er_amount": ("employer_amount", "decimal")}),
  "payments": ("payments", {"ee_amount": ("amount", "decimal")}),
 },
}


def normalize_record(provider, entity, source, context):
    if not isinstance(source, dict):
        raise ValueError("Each source record must be an object")
    _, _, evidence, endpoint = schema_info(provider, entity)
    diagnostics, data, provenance, consumed = [], {}, {}, set()
    errors = validate_source(provider, entity, source)
    diagnostics.extend({"severity": "error", "code": "source_schema", **e} for e in errors)

    def mapping(value, source_path, target, kind):
        consumed.add(source_path)
        provenance[target] = {"source_path": source_path, "rule": kind, "schema": evidence,
                              "lookup_basis": context.get("lookup_basis") if kind == "tenant_status" else None}
        try:
            return transform_value(value, kind, context)
        except LookupError:
            diagnostics.append({"severity": "warning", "code": "unknown_enum", "path": source_path, "raw": value})
            return "unknown"
        except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
            diagnostics.append({"severity": "error", "code": "invalid_value", "path": source_path, "message": str(exc)})
            return None

    for source_path, (target, kind) in MAPPINGS[provider][entity].items():
        value = get(source, source_path, MISSING)
        if value is not MISSING:
            put(data, target, mapping(value, source_path, target, kind))
    if entity == "paycheck":
        for target, (source_path, layout) in LINE_RULES[provider].items():
            rows = get(source, source_path, MISSING)
            if rows is MISSING:
                continue
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                diagnostics.append({"severity": "error", "code": "invalid_lines", "path": source_path})
                continue
            lines = []
            for i, row in enumerate(rows):
                line = {}
                for field, (dest, kind) in layout.items():
                    value = get(row, field, MISSING)
                    if value is not MISSING:
                        line[dest] = mapping(value, f"{source_path}[{i}].{field}", f"{target}[{i}].{dest}", kind)
                lines.append(line)
            data[target] = lines

    employee_id = data.get("employee_source_id", context.get("employee_id"))
    if entity == "employee":
        employee_id = data.get("source_id")
    if entity not in ("employee", "company", "payroll_run") and employee_id is None:
        diagnostics.append({"severity": "error", "code": "missing_employee_context", "path": "context.employee_id"})
    if "source_id" not in data or data["source_id"] in (None, ""):
        if entity in ("employee", "company", "payroll_run", "paycheck"):
            diagnostics.append({"severity": "error", "code": "missing_source_id", "path": "source_id"})
        source_id = context.get("record_id") or "content-" + hashlib.sha256(
            json.dumps(source, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
        diagnostics.append({"severity": "warning", "code": "content_identity", "path": "source_id",
                            "message": "Supply context.record_id for identity stable across edits"})
    else:
        source_id = data["source_id"]
    local_context = {**context, "employee_id": employee_id}
    if entity == "company" and str(source_id) != str(context["company_id"]):
        diagnostics.append({"severity": "error", "code": "company_context_mismatch", "path": "source_id"})
    relationships = {"company_id": identifier(provider, context, "company", context["company_id"])}
    if entity == "employee":
        relationships["employee_id"] = identifier(provider, context, "employee", source_id)
    elif employee_id is not None:
        relationships["employee_id"] = identifier(provider, context, "employee", employee_id)
    run_id = data.get("payroll_run_source_id", context.get("payroll_run_id"))
    if entity == "paycheck" and run_id is not None:
        relationships["payroll_run_id"] = identifier(provider, context, "payroll_run", run_id)
    elif entity == "paycheck":
        diagnostics.append({"severity": "warning", "code": "missing_payroll_run_context", "path": "context.payroll_run_id"})

    if entity == "direct_deposit":
        amount, percent = data.get("amount"), data.get("percentage")
        if provider == "isolved":
            data["allocation_method"] = ("remaining_balance" if data.get("priority") == 0 else
                                         "percentage" if percent is not None else "fixed" if amount is not None else "unknown")
        if amount is not None and percent is not None:
            diagnostics.append({"severity": "error", "code": "ambiguous_allocation", "path": "amount"})
        if percent is not None and not Decimal(0) <= Decimal(percent) <= Decimal(100):
            diagnostics.append({"severity": "error", "code": "invalid_percentage", "path": "percentage"})
        if provider == "prismhr" and data.get("allocation_method") == "remaining_balance" and "amount" in source:
            diagnostics.append({"severity": "error", "code": "balance_with_amount", "path": "amount"})
    if entity == "deduction":
        if provider == "prismhr":
            data["value_kind"] = "percentage_raw_scale" if data.get("is_percentage") is True else "amount" if data.get("is_percentage") is False else "unknown"
        elif provider == "isolved":
            diagnostics.append({"severity": "warning", "code": "pay_item_classification_required", "path": "payItemType",
                                "message": "Caller must select deductions using tenant pay-item metadata"})
    extensions = {}
    for path, value in flatten(source):
        if not any(path == root or path.startswith(root + ".") or path.startswith(root + "[") for root in consumed):
            extensions[path] = copy.deepcopy(value)
    return {"schema_version": "1.0", "id": identifier(provider, local_context, entity, source_id),
            "entity": entity, "provider": provider,
            "source": {"tenant_id": str(context["tenant_id"]), "company_id": str(context["company_id"]),
                       "record_id": str(source_id), "schema": evidence, "endpoint": endpoint},
            "relationships": relationships, "data": data, "provenance": provenance,
            "extensions": extensions, "source_data": copy.deepcopy(source),
            "diagnostics": diagnostics, "source_valid": not errors}


def normalize(provider, entity, response, reference=None):
    entity = "paycheck" if entity == "payroll" else entity
    if not isinstance(response, dict) or not isinstance(response.get("context"), dict) or "records" not in response:
        raise ValueError("Input must contain context and records; extract endpoint envelopes explicitly")
    context = response["context"]
    if any(context.get(k) in (None, "") for k in ("tenant_id", "company_id")):
        raise ValueError("context.tenant_id and context.company_id are required")
    if not isinstance(response["records"], list):
        raise ValueError("records must be an array")
    schema_info(provider, entity)
    return [normalize_record(provider, entity, record, context) for record in response["records"]]
