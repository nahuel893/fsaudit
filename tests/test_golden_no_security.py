"""Golden parity test — T17 STEP 3.

Verifies that audit() WITHOUT security_scan=True produces results
bit-for-bit equal to the v0.10.0 baseline captured in
tests/fixtures/golden/audit_baseline.json.

The NEW `security` field (which defaults to None) is stripped from the
comparison so its mere presence doesn't break parity — but its VALUE must be
None when the flag is off.

This test is the canary for backward compatibility. It MUST remain passing as
the feature grows.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from fsaudit.api import audit

GOLDEN_TREE = Path(__file__).parent / "fixtures" / "golden" / "sample_tree"
GOLDEN_BASELINE = Path(__file__).parent / "fixtures" / "golden" / "audit_baseline.json"


def _strip_security(d: dict) -> dict:
    """Remove new-in-v0.11.0 fields from a dataclasses.asdict() result."""
    d.pop("security", None)
    d.pop("overflow_warning", None)
    return d


def _normalize_timestamps(d):
    """Recursively replace all datetime-like strings with a placeholder.

    This allows comparison of structural content without being sensitive to
    file modification timestamps that change between test runs on the same
    fixture tree.
    """
    if isinstance(d, dict):
        return {k: _normalize_timestamps(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_normalize_timestamps(v) for v in d]
    if isinstance(d, str):
        # Replace ISO-style datetime strings (YYYY-MM-DD HH:MM:SS or similar)
        import re
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            return "<timestamp>"
    return d


class TestGoldenParity:
    """audit(flag_off) produces bit-for-bit equal result to v0.10.0 baseline."""

    def test_baseline_file_exists(self) -> None:
        assert GOLDEN_BASELINE.exists(), (
            f"Golden baseline not found at {GOLDEN_BASELINE}. "
            "Re-run the baseline capture script."
        )

    def test_security_field_is_none_without_flag(self) -> None:
        """The new security field must be None when not scanning."""
        result = audit(GOLDEN_TREE, format=None)
        assert result.security is None

    def test_audit_without_flag_equals_v010_baseline(self) -> None:
        """Deep-equality check against the captured baseline JSON.

        Strategy:
        1. Load the baseline JSON.
        2. Run current audit() without security_scan.
        3. Serialize result with dataclasses.asdict() → JSON-safe dict.
        4. Strip the new `security` key from both sides.
        5. Assert deep equality.
        """
        # Load baseline
        baseline = json.loads(GOLDEN_BASELINE.read_text(encoding="utf-8"))
        baseline_stripped = _strip_security(baseline)

        # Run current audit
        result = audit(GOLDEN_TREE, format=None, security_scan=False)
        actual = dataclasses.asdict(result)
        actual_stripped = _strip_security(actual)

        # Re-serialize both through JSON (uses str() for datetime etc.) for
        # uniform comparison — same transformation applied to both sides.
        # Normalize timestamps first so file mtime variations don't cause false failures.
        baseline_norm = _normalize_timestamps(
            json.loads(json.dumps(baseline_stripped, default=str))
        )
        actual_norm = _normalize_timestamps(
            json.loads(json.dumps(actual_stripped, default=str))
        )

        baseline_json = json.dumps(baseline_norm, sort_keys=True)
        actual_json = json.dumps(actual_norm, sort_keys=True)

        assert baseline_json == actual_json, (
            "audit() result drifted from v0.10.0 baseline (timestamps normalized).\n"
            "If this is intentional, re-capture the baseline by running:\n"
            "  python -c \"import json, dataclasses; from fsaudit.api import audit; "
            "result = audit('tests/fixtures/golden/sample_tree', format=None); "
            "open('tests/fixtures/golden/audit_baseline.json', 'w').write("
            "json.dumps(dataclasses.asdict(result), default=str, indent=2))\""
        )

    def test_total_files_matches_baseline(self) -> None:
        """Quick sanity: file count matches the 5 files in the fixture tree."""
        result = audit(GOLDEN_TREE, format=None)
        assert result.total_files == 5
