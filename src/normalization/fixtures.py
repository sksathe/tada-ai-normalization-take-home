"""Seeded, synthetic response records, completed against pinned source contracts."""
import copy
import json
import random
from pathlib import Path

from .contracts import SOURCES, fingerprints, resolve, schema_info, validate_source
from .engine import get, put


def complete(schema, doc, supplied=None, depth=0):
    """Fill required fields only. Never use vendor examples as fixture truth."""
    schema = resolve(schema, doc)
    if depth > 15:
        raise ValueError("Recursive required schema exceeds fixture generator limit")
    if supplied is None:
        if "enum" in schema:
            return copy.deepcopy(schema["enum"][0])
        kind = schema.get("type", "object" if "properties" in schema else "string")
        if isinstance(kind, list):
            kind = next((k for k in kind if k != "null"), "null")
        if kind == "object":
            supplied = {}
        elif kind == "array":
            return []
        elif kind == "boolean":
            return False
        elif kind in ("integer", "number"):
            return schema.get("minimum", 0)
        elif schema.get("format") == "date-time":
            return "2026-01-15T00:00:00Z"
        elif schema.get("format") == "date":
            return "2026-01-15"
        else:
            return ""
    if isinstance(supplied, dict):
        result = copy.deepcopy(supplied)
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in result:
                result[key] = complete(props.get(key, {}), doc, depth=depth + 1)
        for key, value in list(result.items()):
            if key in props and value is not None:
                result[key] = complete(props[key], doc, value, depth + 1)
        return result
    if isinstance(supplied, list):
        return [complete(schema.get("items", {}), doc, v, depth + 1) for v in supplied]
    return supplied


def employee(provider, number, scenario, rng):
    first = rng.choice(["Alex", "Morgan", "Taylor", "Jordan", "Casey"])
    last = f"Synthetic{number}"
    status = "terminated" if scenario == "terminated" else "on_leave" if scenario == "on_leave" else "active"
    rate = 0 if scenario == "zero_rate" else 25
    # Independent common-field oracle; it does not import mapping definitions.
    expected = {"first_name": first, "last_name": last, "employment_status": "unknown" if scenario == "unknown_code" else status}
    unknown = "UNRECOGNIZED_STATUS"
    if provider == "prismhr":
        payload = {"id": str(number), "firstName": first, "lastName": last, "middleInitial": "Q", "preferredName": first,
                   "contactInformation": {"emailAddress": f"person{number}@example.invalid", "zipcode": "02108"},
                   "client": {"statusClass": unknown if scenario == "unknown_code" else {"active": "A", "terminated": "T", "on_leave": "L"}[status],
                              "lastHireDate": "2024-01-15", "jobCode": "ENG", "homeDepartment": "RND"},
                   "compensation": {"hourlyPay": str(rate), "payMethod": "H", "standardHours": "80"}}
        if scenario == "missing_optional":
            payload.pop("contactInformation")
        else:
            expected["personal_email"] = f"person{number}@example.invalid"
        expected["compensation.hourly_rate"] = str(rate)
    elif provider == "isolved":
        payload = {"id": number, "nameAddress": {"firstName": first, "lastName": last, "zipCode": "02108"},
                   "employeeNumber": str(number), "employmentStatus": unknown if scenario == "unknown_code" else status.upper(),
                   "hourlyRate": rate, "hireDate": "2024-01-15T00:00:00Z", "jobCode": "ENG"}
        if scenario != "missing_optional":
            payload["emailAddress"] = f"person{number}@example.invalid"
            expected["personal_email"] = payload["emailAddress"]
        expected["compensation.hourly_rate"] = str(rate)
    else:
        payload = {"id": number, "username": f"synthetic{number}", "first_name": first, "last_name": last,
                   "employee_id": str(number), "status": unknown if scenario == "unknown_code" else status.upper(),
                   "dates": {"hired": "2024-01-15"}, "address": {"country": "USA", "zip": "02108"}}
        if scenario != "missing_optional":
            payload["primary_email"] = f"person{number}@example.invalid"
            expected["personal_email"] = payload["primary_email"]
    return payload, expected


def generate(seed=42, count=24):
    if count < 6:
        raise ValueError("Use at least six employees per provider to cover the scenarios")
    rng = random.Random(seed)
    cases = []

    def add(provider, entity, payload, expected, context, scenario="baseline", fault=False):
        schema, doc, _, _ = schema_info(provider, entity)
        payload = complete(schema, doc, payload)
        issues = validate_source(provider, entity, payload)
        if issues and not fault:
            raise ValueError(f"Generated fixture {provider}/{entity} is invalid: {issues[:3]}")
        cases.append({"case_id": f"{provider}/{entity}/{len(cases):05}", "provider": provider,
                      "entity": entity, "scenario": scenario, "expected": expected, "fault_injection": fault,
                      "input": {"context": copy.deepcopy(context), "records": [payload]}})

    for provider in SOURCES:
        context = {"tenant_id": "synthetic-demo", "company_id": "100", "currency": "USD",
                   "status_lookup": {"ACTIVE": "active", "TERMINATED": "terminated", "ON_LEAVE": "on_leave"},
                   "lookup_basis": "Synthetic tenant dictionary, explicitly supplied by fixture author; not a provider-wide enum"}
        if provider != "ukg-ready":
            company = {"id": "100", "clientName": "Synthetic Labs", "legalName": "Synthetic Labs"} if provider == "prismhr" else {"id": 100, "legalName": "Synthetic Labs", "dbaName": "Synthetic Labs"}
            add(provider, "company", company, {"legal_name": "Synthetic Labs"}, context)
        scenarios = ["baseline", "terminated", "on_leave", "unknown_code", "missing_optional", "zero_rate"]
        for n in range(count):
            number = n + 1
            scenario = scenarios[n % len(scenarios)]
            # Equivalent people across providers, using independent source shapes.
            emp, expected = employee(provider, number, scenario, random.Random(seed * 1000003 + number))
            ctx = {**context, "employee_id": str(number)}
            add(provider, "employee", emp, expected, ctx, scenario)
        ctx = {**context, "employee_id": "1", "payroll_run_id": "500"}
        if provider == "prismhr":
            deposit = {"accountNum": "0000123400", "transitNum": "000000000", "accountType": "S", "method": "F", "amount": 150, "status": "D"}
            deduction = {"deductionCode": "SYN401", "description": "Synthetic retirement", "usePercent": False, "amount": 50, "period": "1"}
            run = {"batchId": "500", "payDate": "2026-01-30", "grossEarnings": "1000", "employeesPaid": "1"}
            check = {"voucherId": "900", "employeeId": "1", "batchId": "500", "payDate": "2026-01-30", "payPeriodStart": "2026-01-01", "payPeriodEnd": "2026-01-15", "totalEarnings": 1000, "netPay": 750,
                     "earnAmount": 1000, "otherEarnAmount": 0,
                     "employeeTax": [{"empTaxDeductCode": "SYNFIT", "empTaxAmount": 200}],
                     "deduction": [{"deductCode": "SYN401", "deductAmount": 50}], "otherDeduction": [],
                     "earning": [{"payCode": "SYNREG", "hoursWorked": 40, "hoursUnits": 40, "unitRate": 25, "payAmount": 25}],
                     "employerContributions": [{"code": "SYNMATCH", "description": "Employer match", "amount": 25}]}
            dep_expected = {"account_number": "0000123400", "allocation_method": "fixed", "allocation_value": "150"}
        elif provider == "isolved":
            deposit = {"id": 200, "accountNumber": "0000123400", "routingNumber": "000000000", "accountType": "Synthetic savings", "amount": 150, "sequenceNumber": 1, "status": "Synthetic active", "frequency": "Synthetic every pay"}
            deduction = {"id": 300, "employeeId": 1, "payItemCode": "SYN401", "payItemName": "Synthetic retirement", "payItemType": "Synthetic deduction", "calcParams": [{"paramType": "TenantDefinedFixed", "paramValue": 50}]}
            run = {"id": 500, "runNumber": 7, "payDate": "2026-01-30T00:00:00Z"}
            check = {"id": 900, "employeeId": 1, "payrollRunNumber": 7, "grossPay": 1000, "netPay": 750,
                     "earnings": [{"itemCode": "SYNREG", "checkDollars": 1000, "checkHours": 40, "isMemoEarning": False}],
                     "taxes": [{"itemCode": "SYNFIT", "checkDollars": 200, "isEmployeeTax": True}, {"itemCode": "SYNERTAX", "checkDollars": 60, "isEmployeeTax": False}],
                     "deductions": [{"itemCode": "SYN401", "checkDollars": 50}], "garnishments": []}
            dep_expected = {"account_number": "0000123400", "allocation_method": "fixed", "amount": "150"}
        else:
            deposit = {"id": 200, "type": "DIRECT_DEPOSIT", "sequence": 1, "account_number": "0000123400", "account_type": "SAVINGS", "amount": 150, "active": True, "active_from": "2026-01-01", "active_to": "2027-01-01", "calc_method": {"type": "FLAT_AMOUNT", "display_name": "Flat amount"}, "_links": {"self": "/synthetic/deposits/200"}}
            deduction = {"id": 300, "deduction": {"code": "SYN401", "name": "Synthetic retirement"}, "effective_from": "2026-01-01", "effective_to": "2027-01-01", "ee_calc_method": {"amount": 50}}
            run = {"id": 500, "pay_date": "2026-01-30", "type": {"id": 1}, "status": "FINALIZED"}
            check = {"id": 900, "employee": {"account_id": 1}, "pay_date": "2026-01-30",
                     "earnings": [{"earning": {"code": "SYNREG"}, "ee_amount": 1000, "hours": 144000000}],
                     "taxes": [{"company_tax": {"code": "SYNFIT"}, "ee_amount": 200, "er_amount": 60}],
                     "deductions": [{"deduction": {"code": "SYN401"}, "ee_amount": 50, "er_amount": 25}],
                     "payments": [{"ee_amount": 750}]}
            dep_expected = {"account_number": "0000123400", "allocation_method": "fixed", "amount": "150"}
        add(provider, "direct_deposit", deposit, dep_expected, ctx)
        add(provider, "deduction", deduction, {"code": "SYN401", "description": "Synthetic retirement"}, ctx)
        add(provider, "payroll_run", run, {"source_id": "500" if provider == "prismhr" else 500}, context)
        check_expected = {"gross_pay": "1000", "net_pay": "750"} if provider != "ukg-ready" else {"earnings": [{"code": "SYNREG", "amount": "1000", "hours_raw": 144000000}], "payments": [{"amount": "750"}]}
        add(provider, "paycheck", check, check_expected, ctx)
        if provider in ("prismhr", "ukg-ready"):
            comp = {"payMethod": "H", "hourlyPay": "25", "standardHours": "80"} if provider == "prismhr" else {"id": 400, "employee": {"account_id": 1}, "effective_from": "2026-01-01", "amount": 25, "hourly_pay": 25, "amount_period": "HOUR", "time": 288000000, "time_period": "PAY_PERIOD", "num_pp_in_year": 26, "currency": "USD"}
            add(provider, "compensation", comp, {"hourly_rate": "25"}, ctx)
        if provider == "ukg-ready":
            add(provider, "demographics", {"gender": "UNDEFINED", "seasonal": False}, {"gender_raw": "UNDEFINED", "seasonal": False}, ctx)
            add(provider, "pay_info", {"payroll_classification": "REGULAR", "standard_work_day": 28800000, "default_job": {"id": 10}, "job_change_reason_code": {"display_name": "Synthetic assignment"}}, {"standard_work_day_milliseconds": 28800000, "job_source_id": 10}, ctx)
            add(provider, "custom_fields", {"hr_custom_fields": [{"index": 0, "value": "Synthetic custom value"}]}, {"custom_fields": [{"index": 0, "value": "Synthetic custom value"}]}, ctx)
        # A second deposit demonstrates percentage allocation without rewriting its basis.
        pct = copy.deepcopy(deposit)
        if provider == "prismhr":
            pct.update(method="P", amount=20)
            pct_expected = {"allocation_method": "percentage", "allocation_value": "20"}
        else:
            pct.pop("amount")
            pct.update({"id": 201, "percent" if provider == "isolved" else "percentage": 20})
            if provider == "ukg-ready":
                pct["calc_method"]["type"] = "NET_PAY"
            pct_expected = {"percentage": "20"}
        add(provider, "direct_deposit", pct, pct_expected, ctx, "percentage_allocation")
        # Negative adjustments stay negative; checks and assertions are independent of source mapping.
        adjustment = copy.deepcopy(check)
        if provider == "prismhr":
            adjustment.update(voucherId="901", totalEarnings=-100, netPay=-100, earnAmount=-100)
            adjustment.update(employeeTax=[], deduction=[], earning=[])
        elif provider == "isolved":
            adjustment.update(id=901, grossPay=-100, netPay=-100, earnings=[{"itemCode": "SYNADJ", "checkDollars": -100, "isMemoEarning": False}], taxes=[], deductions=[], garnishments=[])
        else:
            adjustment.update(id=901, earnings=[{"earning": {"code": "SYNADJ"}, "ee_amount": -100}], taxes=[], deductions=[], payments=[{"ee_amount": -100}])
        # Separate run linkage prevents mixing a second adjustment into the baseline run total.
        adj_ctx = {**ctx, "payroll_run_id": "501"}
        if provider == "prismhr":
            adjustment["batchId"] = "501"
        adj_run = copy.deepcopy(run)
        adj_run["batchId" if provider == "prismhr" else "id"] = "501" if provider == "prismhr" else 501
        if provider == "prismhr":
            adj_run["grossEarnings"] = "-100"
        add(provider, "payroll_run", adj_run, {}, context, "adjustment")
        add(provider, "paycheck", adjustment, {"net_pay": "-100"} if provider != "ukg-ready" else {"payments": [{"amount": "-100"}]}, adj_ctx, "adjustment")
    return {"seed": seed, "employees_per_provider": count, "synthetic_only": True,
            "contracts": fingerprints(), "cases": cases}


def write_fixtures(path, seed=42, count=24):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = generate(seed, count)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result
