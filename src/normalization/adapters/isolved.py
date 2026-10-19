"""isolved primary v6 response-record adapter."""
from typing import Any, Dict
from ..engine import normalize as _normalize


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Return the candidate-designed JSON-serializable canonical result.

    Do not infer units, endpoint shapes, or enum meanings from this stub.
    Preserve documented source semantics and define diagnostics in your design.
    """
    return _normalize("isolved", entity, response, reference)
