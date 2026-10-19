# Assumptions, decisions, and limitations

## Implemented scope

This solution is a functioning offline normalization and evaluation platform. It implements
response-record adapters for all three providers and the four required data domains,
with company and payroll-run linkage. It accepts extracted response records and explicit
request context rather than assuming every endpoint uses the same response envelope.

**It is not an exhaustive semantic mapping of every employee field or provider endpoint.**
The current selected-schema inventory includes 2,417 reachable leaves: 330 explicit field
mappings, 227 leaves under structured preservation mappings, and 1,860 extension leaves.
Every supplied input field is retained in `source_data`; unconsumed fields are also
indexed in `extensions`. Retention preserves information for later mapping but does
not satisfy the same cross-provider contract as semantic normalization. The dashboard
shows these categories separately. This is the principal remaining area before claiming
full coverage of the assignment's "all available employee fields" requirement.

The coverage denominator includes selected record schemas and their reachable nested
schemas. Arrays use `[]` paths; recursive references end at an explicit boundary.
It is not a count of all endpoints or of every optional feature in the product. The
registry in `contracts.py` is the authoritative list of selections. UKG employee
demographics, pay info, custom fields and compensation use separate employee-linked
canonical records, since they are separate response resources. Their values are not
implicitly assumed current or merged into a single employee snapshot.

## Reference evidence and local readiness

- PrismHR uses the supplied 2025.09 derivative.
- isolved uses only the **primary** v6 Swagger snapshot. The alternate is never used.
- UKG uses GET response blocks selected from the extracted schema bundle. Cached
  HTML pages establish the corresponding resource routes. These are not OpenAPI.
- Mappings cite local schema roots; the coverage CSV cites field-level schema pointers.
  Descriptions are evidence, not executable instructions.
- The assignment README authorizes using the supplied pack. Original distribution,
  license, manifest and audit files remain unmodified. The obsolete starter readiness
  gate is replaced with artifact checks, without inventing a provider redistribution license.
- Git CRLF checkout conversion changes byte hashes on Windows. Readiness accepts either
  the exact checksum or the checksum after normalizing CRLF to LF. Fixture fingerprints
  consistently use LF-normalized bytes. All other content still participates in the hash.
- Encoded source-schema assertions are checked with `jsonschema` and date format
  checking. Validation cannot enforce prose-only requirements, XML-only details,
  undocumented units, or opaque documentation blocks. No latest-live-contract claim is made.

## Canonical representation

Canonical records have a stable envelope: schema version, entity, scoped ID, provider,
source metadata, relationships, data, field provenance, extensions, original source,
source-validation status and diagnostics. The published JSON schema validates the
envelope and common typed fields; it deliberately permits additional data properties
for provider-specific concepts. It is not a closed exhaustive schema for every extension.

- Identifiers include provider, tenant and company, with escaped delimiters. Child
  deposit/deduction/compensation/supplement records additionally include employee context.
  IDs are not matched across providers by name, SSN, email, or employee number.
- Source record IDs are retained. Records without an ID receive a content-hash fallback
  plus a warning. Supply `context.record_id` for an identity stable across source edits;
  it must uniquely identify a record within that employee/entity. Identical content can
  collide intentionally; evaluation rejects duplicate canonical IDs.
- `context.company_id` is the Prism client ID, isolved legal ID, or UKG company ID.
  isolved client ID is represented by `tenant_id` in local examples; use a sufficiently
  scoped tenant identifier when integrating actual multi-client accounts.
- A payroll run number is not assumed to be its object ID. isolved and UKG paycheck
  ingestion supplies the run object ID in context. Prism vouchers carry `batchId`.
- UKG has no selected company-master response schema in this bundle. Company IDs remain
  explicit context anchors. They are reported as `context_only`, not as resolved records.
  This is a pack/implementation gap, not a claim that the live provider has no company API.
- Monetary values become decimal strings; arithmetic uses `Decimal`. No currency is
  silently assumed, and values are not rounded or converted between currencies.
  Inputs use Python's standard JSON parser: extremely high precision JSON numeric literals
  can lose precision during initial float parsing. Values that require lexical precision
  beyond that should be ingested with a Decimal-aware JSON transport before production use.
- Missing fields stay absent. Explicit null remains null and is flagged if the source
  contract disallows it. Blank source decimal/date strings become canonical null while
  the original blank remains in source data and provenance. Zero stays zero.
- Dates must be ISO dates or timestamps. Timestamps and offsets are preserved; no timezone
  is invented and no timestamp is truncated to a date.

## Enums and domain choices

Prism employee `client.statusClass` has documented A/L/T meanings. `employeeStatus`
is a separate tenant-defined identifier and is retained independently. The ambiguous
`Employee.firstName` prose says "family name"; the field name and the separate lastName
field are used to resolve this apparent documentation error.

isolved and UKG employee status strings are not assumed to have universal meanings.
Normalization accepts an explicit tenant `status_lookup` and a descriptive `lookup_basis`.
Demo lookups are synthetic author-supplied metadata, not discovered provider-wide enums.
Missing or unrecognized mappings emit `unknown_enum` and canonical `unknown`; source codes
remain intact. No AI model guesses values at runtime.

Prism account type C means **checking account or pay card**, so it maps to
`checking_or_pay_card`. Direct-deposit method distinctions (fixed, skip-underfunded,
percentage after fixed, remaining balance) are retained. Prism percentage numeric scale
is not converted to a fraction because the selected amount description does not establish
that scale. Its value is `allocation_value`, separate from the method. isolved `percent`
uses its documented 0–100 bounds; sequence 0 is net pay. UKG FULL is interpreted as
remaining balance; other calculation bases are retained separately. Active date ranges,
priority and prenote state remain distinct. Array order is never presented as a provider
priority if a priority field is absent.

Deduction setup and paycheck deductions are different canonical entities/line arrays.
isolved pay items can represent multiple item types: callers must select deductions using
tenant metadata. Calculation parameter names have no supplied universal meaning and are
preserved without guessing whether `paramValue` is dollars or percent. Prism `usePercent`
is implemented using the declared boolean type, despite its prose also mentioning T/F.
Unknown tax treatment, deduction type, and benefit classifications stay raw.

## Payroll arithmetic

Checks use an absolute tolerance of 0.01 source monetary units. This is a demo policy,
not a universal currency minor-unit rule. Amounts retain their original precision.

- Prism gross compares to `earnAmount + otherEarnAmount`. `Earning.payAmount` is described
  as pay per hour/unit and is **not** treated as a line total. Employee taxes, deductions
  and other deductions reduce net. Employer contributions are kept separate.
- isolved uses check-period accumulations (`checkDollars`), never YTD/current totals.
  Employer taxes are excluded using `isEmployeeTax`. Earnings marked memo are excluded.
  Missing memo/tax classification makes reconciliation insufficient rather than zero.
- UKG has line-level employee/employer amounts and payments, but the selected response
  schema does not expose reported gross/net totals. The report marks reported-gross
  reconciliation insufficient and checks **line cash flow versus payments** separately.
  This does not manufacture reported totals. Paycheck hours remain `hours_raw` because
  their unit is unspecified in the selected schema. Compensation `time` and pay-info
  standard work day explicitly document milliseconds, so those retain that unit.
- Run-gross checks need a reported run gross and linked paycheck gross totals. These
  are unavailable in the selected isolved/UKG run models and remain insufficient.
- Reconciliation assumes complete arrays and a complete set of paychecks for the run
  in this controlled synthetic corpus. A live sync needs explicit pagination/completeness,
  adjustment/void, reimbursement, benefit, currency and rounding policies before these
  equations can be treated as universal accounting assertions.

## Evaluation design

Seed 42 with 24 employees per provider generates 100 total records. Fixtures are authored
synthetic scenarios, with required properties completed from the local schemas. Source
examples are not reused. Names and shared scenarios represent equivalent people across
providers, with independent expected canonical assertions and cross-provider comparisons.

Required-field completion creates structurally valid defaults, not verified business-valid
live records. Baseline, terminated, leave, unknown status, missing optional data, zero rate,
fixed/percentage deposits and negative payroll adjustments are represented. This is not
exhaustive scenario coverage or a statistically representative population.

Expected-value assertions are authored in `fixtures.py`, without importing the mapping
registry. Cross-provider equality is checked independently on shared employee concepts.
The fixture generator and expected values still share scenario authoring; they are not an
externally adjudicated gold dataset. Structural validity and record pass rate are reported
separately from field assertion accuracy. A field being exercised means it appeared in a
fixture, not that every transformation of that field was asserted.

Negative controls deliberately alter normalized output: wrong net pay, broken employee
link, numeric canonical money and a dropped expected field. Each detector must flag its
fault. Unknown-code scenarios separately test forward compatibility. Tests cover input
immutability, identifiers, precision/units, null/zero handling, schema evidence and exports.

The benchmark reports the median of three warm runs over the corpus, including source
validation. It excludes fixture generation, disk I/O, report rendering and canonical
validation. Environment and contract hashes are recorded. Runtime varies by machine;
this is not a network/API benchmark.

## Local operation and outstanding work

The HTML report loads no external assets and runs offline. SQLite is a regenerated
analytical snapshot, not a production sync database. Report generation replaces generated
artifacts in the requested output directory; the normalize command refuses file overwrite.
Strict normalization refuses source, canonical or transformation errors. Non-strict mode
retains invalid records with diagnostics for inspection. Serve binds only to loopback.

Live sign-in/provider fetching and the optional employee write-back extension are not
implemented. Provider response pagination, retries and incremental sync are outside this
offline implementation. Demo fixtures are deterministic and credential-free. Real tokens
and downloads belong in ignored `.env` / `local-data`, never in source or shared reports.

Before a full submission claiming exhaustive normalization: finish semantically mapping
the extension fields, inventory and implement remaining employee subresources, resolve the
Prism payroll-history endpoint binding, supply tenant lookup metadata, and add independently
reviewed expectations for those fields. The report is designed to measure that progress
without turning retention into a misleading 100% mapping score.
