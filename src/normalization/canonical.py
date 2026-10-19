"""Published canonical envelope and common data-field constraints."""
from functools import lru_cache

DECIMAL = {"type": ["string", "null"], "pattern": r"^-?\d+(\.\d+)?$"}
TEXT = {"type": ["string", "null"]}
DATA_PROPERTIES = {
    **{k: TEXT for k in ("first_name", "last_name", "middle_name", "preferred_name", "personal_email", "work_email", "job_code", "job_title", "code", "description", "account_number", "routing_number")},
    **{k: DECIMAL for k in ("gross_pay", "net_pay", "amount", "percentage", "allocation_value", "allocation_limit", "value", "hourly_rate", "annual_salary", "period_salary", "standard_hours")},
    "employment_status": {"enum": ["active", "inactive", "on_leave", "terminated", "pending", "unknown", None]},
    "allocation_method": {"enum": ["fixed", "percentage", "remaining_balance", "fixed_skip_underfunded", "percentage_after_fixed", "percentage_of_gross", "percentage_of_net", "percentage_of_remainder", "unknown", None]},
    "priority": {"type": ["integer", "null"]},
    "active": {"type": ["boolean", "null"]},
    "compensation": {"type": "object", "properties": {k: DECIMAL for k in ("hourly_rate", "annual_salary", "period_salary", "standard_hours")}},
}
for name in ("earnings", "deductions", "employee_taxes", "taxes", "garnishments", "benefits", "other_deductions", "other_earnings", "employer_contributions", "payments"):
    DATA_PROPERTIES[name] = {"type": "array", "items": {"type": "object", "properties": {
        **{k: DECIMAL for k in ("amount", "hours", "rate", "units", "employee_amount", "employer_amount", "quantity")},
        "code": {"type": ["string", "null"]}, "is_employee": {"type": ["boolean", "null"]}}}}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#", "title": "Tada canonical record v1",
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "id", "entity", "provider", "source", "relationships", "data", "provenance", "extensions", "source_data", "diagnostics", "source_valid"],
    "properties": {
        "schema_version": {"const": "1.0"}, "id": {"type": "string", "minLength": 1},
        "entity": {"enum": ["company", "employee", "direct_deposit", "deduction", "payroll_run", "paycheck", "compensation", "demographics", "pay_info", "custom_fields"]},
        "provider": {"enum": ["prismhr", "isolved", "ukg-ready"]},
        "source": {"type": "object", "required": ["tenant_id", "company_id", "record_id", "schema", "endpoint"], "additionalProperties": {"type": "string"}},
        "relationships": {"type": "object", "required": ["company_id"], "additionalProperties": {"type": "string", "minLength": 1}},
        "data": {"type": "object", "properties": DATA_PROPERTIES},
        "provenance": {"type": "object", "additionalProperties": {"type": "object", "required": ["source_path", "rule", "schema"]}},
        "extensions": {"type": "object"}, "source_data": {"type": "object"},
        "diagnostics": {"type": "array", "items": {"type": "object", "required": ["code", "severity"]}},
        "source_valid": {"type": "boolean"},
    },
}


@lru_cache(maxsize=1)
def validator():
    from jsonschema import Draft7Validator
    return Draft7Validator(SCHEMA)


def validate(record):
    return [{"path": ".".join(map(str, e.path)), "message": e.message} for e in validator().iter_errors(record)]
