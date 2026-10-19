# Tada normalization lab

A local, contract-backed normalization pipeline with reproducible synthetic fixtures,
an evaluation dashboard, payroll reconciliation, field-level mapping evidence, and
JSON / CSV / SQLite exports.

## Run the solution

Requires Python 3.10+. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m normalization check-inputs
.\.venv\Scripts\python.exe -m normalization demo --seed 42 --count 24
.\.venv\Scripts\python.exe -m normalization serve
```

Open [the local dashboard](http://127.0.0.1:8765). The generated
`artifacts/report/index.html` is also self-contained and can be opened directly;
neighboring export files must accompany it for the download links to work.

On macOS/Linux, use `python3` and `.venv/bin/python` instead. The current workspace
already has a configured `.venv`. Fixture generation, tests and evaluation require
no credentials, live provider access, Node, or external frontend assets after setup.

```powershell
# Run all tests, including reference integrity and deliberate error detection
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Normalize an individual extracted response record
.\.venv\Scripts\python.exe -m normalization normalize --provider isolved --entity employee --input examples/isolved-employee.json --output artifacts/employee.json --strict

# Generate inputs separately, then evaluate them
.\.venv\Scripts\python.exe -m normalization generate-fixtures --seed 42 --count 24
.\.venv\Scripts\python.exe -m normalization evaluate --input artifacts/fixtures.json

# List supported provider/entity combinations
.\.venv\Scripts\python.exe -m normalization list-providers
```

`--count` is employees per provider, minimum six. The default demo contains 100
records across employee and related entities. `normalize` refuses to overwrite its
output file. `--strict` refuses invalid input/output or transformation errors;
without it, diagnostics remain available alongside partial output. Evaluation writes
its report even when checks fail, then exits nonzero. Demo/evaluate replace generated
files in their output directory. Stop the report server with Ctrl+C.

## What to inspect

The dashboard includes:

1. **Overview:** provider/entity matrix, metric denominators and field dispositions.
2. **Field coverage:** searchable contract fields, canonical targets, evidence and fixture exercise.
3. **Record explorer:** source versus canonical data, provenance, relationships and diagnostics.
4. **Reconciliation:** arithmetic checks, differences and insufficient-data cases.
5. **Evaluation:** expected-value assertions, equivalent cross-provider scenarios, fault detection,
   measured throughput, environment, contract hashes and scope limits.

Generated outputs live in ignored `artifacts/`:

| Artifact | Purpose |
| --- | --- |
| `fixtures.json` | Seeded source records and independently authored expected-value assertions |
| `report/index.html` | Self-contained interactive report |
| `report/results.json` | Full results, numerators/denominators and evidence |
| `report/coverage.csv` | Selected-schema field inventory and mapping decisions |
| `report/normalized.json` | Canonical records with lossless source retention |
| `report/normalized.sqlite` | Queryable normalized snapshot and diagnostics |
| `report/canonical.schema.json` | Canonical envelope/common-field schema |

Example SQLite query:

```sql
SELECT provider, entity, COUNT(*) AS records
FROM records
GROUP BY provider, entity;
```

## Design and current scope

```text
Pinned provider contracts + authored synthetic scenarios
                         |
          Source validation + explicit request context
                         |
             Provider-specific mapping registry
                         |
     Canonical records + provenance + retained extensions
                         |
 Expected assertions / relationships / reconciliation / fault injection
                         |
            HTML + JSON + CSV + SQLite report
```

The core is Python with `jsonschema`; the report uses portable HTML/CSS/JavaScript.
No LLM is used at runtime. Mapping semantics are reviewable in code, source evidence
is retained, unknown enums are flagged, and monetary arithmetic uses Decimal.

**The working pipeline is not an exhaustive semantic mapping of every available
employee field.** It currently has 330 explicit mappings across 2,417 selected contract
leaves; other fields are retained as structured data or extensions. The dashboard
does not label retention as semantic normalization. UKG company links use explicit
context anchors, and live fetching/write-back are outside this implementation.
See [assumptions and decisions](docs/ASSUMPTIONS.md) for precise scope, field/unit
choices, reference gaps, reconciliation assumptions and the remaining coverage work.

### Input and output contracts

An adapter accepts extracted response **records**, not a guessed endpoint envelope:

```json
{
  "context": {"tenant_id": "synthetic-demo", "company_id": "100"},
  "records": [{"id": 1, "nameAddress": {"firstName": "Alex", "lastName": "Synthetic"}}]
}
```

`tenant_id` and `company_id` are required. Child entities need `employee_id` unless
their source record supplies it. For paycheck records without a run ID, supply
`payroll_run_id`. Optional `status_lookup` and `lookup_basis` supply explicit tenant
status semantics; labels are otherwise unknown. Company/employee relationships remain
provider-scoped. Payroll is a compatibility alias for `paycheck`; runs are separate.

Output is an array of versioned canonical records containing `id`, `entity`, `provider`,
`source`, `relationships`, `data`, `provenance`, `extensions`, `source_data`, `diagnostics`
and `source_valid`. Missing fields remain absent, zeros remain zero, and original codes
are retained. Source contracts and original notices are not modified.

### Code map

| Module | Responsibility |
| --- | --- |
| `contracts.py` | Pinned record selections, schema validation, field inventory and fingerprints |
| `mappings.py` | Explicit source-to-canonical fields and documented enum mappings |
| `engine.py` / `adapters/` | Deterministic transforms, scoped IDs, diagnostics and preservation |
| `canonical.py` | Canonical envelope and common-field constraints |
| `fixtures.py` | Seeded scenarios and expected values independent of the mapping registry |
| `evaluation.py` | Metrics, cross-provider comparisons, relationships and arithmetic checks |
| `report.py` / `dashboard.html` | Portable dashboard and analytical exports |

Repository-root execution is supported. This package intentionally reads the supplied
`contracts/` folder alongside the source; a wheel alone is not a self-contained contract
distribution. No provider assets are copied into package distributions.

---

# Original assignment: Tada AI · Data Normalization Take-Home

Build a local platform that normalizes company, employee, direct deposit,
deduction, and payroll data from
**PrismHR, isolved, and UKG Ready** into a consistent model. Discover the provider
mappings, design your own canonical schemas and enums, generate synthetic test
data, and implement transformations that preserve the meaning of the source data.
Use any programming language or stack.
You can use AI as much as you want throughout this project.

## Data to normalize

Normalize these four data types across **PrismHR, isolved, and UKG Ready**:

| Data type | What to cover |
| --- | --- |
| **Employee data** | The complete employee data available from each provider, including profile/contact information, employment status and dates, job and organization details, and compensation. Cover all available employee fields, rather than only a small summary. |
| **Direct deposits** | Employee direct-deposit setup, including account types, deposit allocations, amounts or percentages, priority, and status/effective dates where available. |
| **Deductions** | Employee deduction setup and deductions recorded in payroll, including provider codes/types, amounts or percentages, and applicable rules or dates where available. |
| **Payroll data** | Payroll runs/periods and employee paycheck records, including earnings, hours, gross/net pay, taxes, deductions, and benefit contributions where available. |

Keep the company and employee relationships so these records can be linked in
your normalized model. If a provider does not expose a field or data type, document
that gap and your assumptions or decisions in the Markdown explanation described
under Submission.

## Reference materials

| Provider | Source specifications | Lookup reference |
| --- | --- | --- |
| PrismHR | [OpenAPI 3.0.1, API 2025.09](contracts/prismhr/openapi/prismhr-2025.09.openapi.json) | [Documented codes and meanings](contracts/prismhr/lookup-reference.json) |
| isolved | [Primary Swagger 2.0, API version 6](contracts/isolved/openapi/isolved-v6.swagger.json); [alternate snapshot](contracts/isolved/openapi/isolved-v6.alternate.swagger.json) for comparison | [Documented enum values](contracts/isolved/lookup-reference.json) |
| UKG Ready | [Cached reference pages](contracts/ukg-ready/reference-docs/index.html) and [extracted JSON schemas](contracts/ukg-ready/reference-schemas.json) | [Documented enum values](contracts/ukg-ready/lookup-reference.json) |

UKG Ready's material is cached HTML documentation and an extracted schema bundle,
**not an official Swagger/OpenAPI contract**. Read the pages for endpoint bindings,
parameters, response statuses, XML schemas, and opaque schema blocks. Use isolved's
primary snapshot consistently; do not mix schemas between its two snapshots.
The reference versions have not been verified against the latest live APIs.

The lookup files contain actual, cited source values. They are partial references;
undocumented meanings remain unknown, and tenant-configured lookup values are not
supplied. Discover the mappings and define your own canonical enums. Documented
sample payloads are retained as illustrative source examples; generate and validate
your own fixtures rather than treating those samples as exhaustive contracts.

**Reference status:** this repository is public. PrismHR's artifact license is
retained, and the organizer has approved sharing this reference pack with candidates.
The organizer provides the handoff, scope, deadline, and timezone. Use the
organizer-approved sharing channel.

Source history and evidence remain in the [reference audit](docs/REFERENCE_AUDIT.md),
[isolved manifest](contracts/isolved/SOURCE_MANIFEST.json), and
[UKG manifest](contracts/ukg-ready/SOURCE_MANIFEST.json). Attribution/modification
notices and PrismHR's license stay alongside the specifications.

## Access live demo data

You can inspect live demo responses from all three providers to understand their
data and validate mapping assumptions. The organizer supplies the **API key
privately**; it is not included in this repository.

Send `POST https://tada-demo-provider-signin.onrender.com/signin` with an
`X-API-Key` header and a JSON body containing `tenant`:

```sh
curl -X POST 'https://tada-demo-provider-signin.onrender.com/signin' \
  -H "X-API-Key: $DEMO_SIGNIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"tenant":"ukg"}'
```

Set `DEMO_SIGNIN_API_KEY` locally to the key provided by the organizer. Change
`tenant` to `prism`, `isol`, or `ukg` to select the corresponding demo account.

| Tenant | Authentication returned | Demo identifiers returned |
| --- | --- | --- |
| `prism` | `auth.sessionId`; use it in the provider's `sessionId` header | `context.companies[].client_id` |
| `isol` | `auth.access_token` and the refresh token when issued; use `Authorization: Bearer <access_token>` | `context.companies[].client_id` and `legal_id` |
| `ukg` | `auth.access_token`; use `Authorization: Bearer <access_token>` | `context.companies[].company_id` |

Each response also includes the provider's `base_url`, `tenant_id`, token expiry
when supplied, and `usage.header_name` / `usage.header_prefix`. Use the returned
authentication and identifiers with the provider endpoints in the reference
materials. Retrieve company names, employees, and payroll records through those
provider APIs; company names and employee/payroll records are not returned by
the sign-in endpoint. Prism client IDs and isolved client/legal-entity IDs identify
the seeded demo companies available for exploration.

Call `/signin` again when authentication expires. A refresh token is returned
only if the provider issues one; Prism uses a session ID. The hosted service may
take longer on its first request after inactivity. See the
[sign-in service README](https://github.com/Niwant/demo-provider-signin) for the
response fields and error behavior.

Live access is optional for discovery. Keep fixture generation and submitted
tests deterministic and able to run locally without credentials or live services.
Use the demo accounts for inspection, and keep returned tokens and any downloaded
records out of Git and your submission.

## Submission

Submit a link to your own repository containing everything needed to run your
solution locally. Include:

- A README explaining your approach, how you built it, and the steps to set up
  and run it.
- A Markdown file documenting your assumptions and decisions, with an explanation
  of why you made them.

If something fails, or data seems incorrect, inconsistent, or different from
what you expected, you are free to make your own assumptions and decisions.
Clearly document the issue, what you assumed or decided, and your reasoning in
that Markdown file. Be prepared to explain those choices.

## Optional extension: write canonical data to a provider

If you want to take the project further, add a write path that accepts canonical
employee data and a destination tenant, such as UKG Ready or PrismHR. Map the
canonical data into that provider's format and use its API to create or update
the employee in the selected destination tenant. Explain which operations and
fields you support, how you handle provider differences, and any assumptions
or limitations. You can demonstrate the mapping with a dry run or use a demo
tenant for the write.

This is an open-ended project. You can build an end-to-end system or application,
covering provider data access, normalization into your canonical model, and,
if you choose, writing canonical employee data to a destination tenant. Choose
your own design, architecture, interfaces, and implementation approach. Build
it in the way you think works best, and explain your decisions in your Markdown
file.
