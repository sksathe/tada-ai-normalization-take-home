"""Basic input readiness checks, not licensing or OpenAPI validation."""
import json
import hashlib
from pathlib import Path

from .adapters import ADAPTERS

ROOT = Path(__file__).resolve().parents[2]


def matches_checksum(path, expected):
    """Git may check text artifacts out as CRLF on Windows."""
    payload = path.read_bytes()
    return expected in {hashlib.sha256(payload).hexdigest(),
                        hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()}


def load_reference(provider, root=ROOT):
    path = root / "contracts" / provider / "lookup-reference.json"
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def readiness_issues(provider, root=ROOT):
    """Check local artifact integrity, not provider redistribution authorization.

    The assignment README authorizes use of the distributed pack. Preserve its
    original provenance notices; local execution must not require UKG OpenAPI.
    """
    try:
        ref = load_reference(provider, root)
        if not isinstance(ref, dict):
            return ["Lookup reference must be a JSON object."]
        issues = []
        if ref.get("provider") != provider:
            issues.append("Reference provider identifier does not match the folder.")
        if ref.get("lookup_status") != "verified":
            issues.append("Lookup contents are a template or remain unverified.")
        if not isinstance(ref.get("lookups"), list):
            issues.append("Lookup domains must be an array.")
        if not ref.get("reference_version"):
            issues.append("Reference version is missing.")
        if provider == "ukg-ready":
            bundle = root / "contracts" / provider / "reference-schemas.json"
            manifest = json.loads((root / "contracts" / provider / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
            if not matches_checksum(bundle, manifest["reference_schemas_sha256"]):
                issues.append("Cached UKG schema bundle checksum does not match its manifest.")
            return issues
        spec = ref.get("openapi") or {}
        if spec.get("status") != "verified":
            issues.append("OpenAPI artifact is absent or unverified.")
        relative = spec.get("relative_path")
        base = (root / "contracts" / provider / "openapi").resolve()
        path = None
        if not isinstance(relative, str) or not relative:
            issues.append("Approved OpenAPI filename is missing.")
        else:
            path = (base / relative).resolve()
            if base not in path.parents or path.suffix.lower() not in (".json", ".yaml", ".yml") or not path.is_file():
                issues.append("Approved OpenAPI file must exist inside the provider openapi directory.")
        if not all(spec.get(key) for key in ("version", "source", "sha256")):
            issues.append("OpenAPI provenance/version/checksum metadata is incomplete.")
        elif path is not None and path.is_file() and not matches_checksum(path, spec["sha256"]):
            issues.append("Contract checksum does not match the pinned reference.")
        return issues
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return ["Cannot read reference metadata: " + str(exc)]


def all_readiness_issues(root=ROOT):
    return {provider: readiness_issues(provider, root) for provider in ADAPTERS}
