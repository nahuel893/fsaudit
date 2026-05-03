"""Security score computation for fsaudit.

The scorer translates a list of :class:`~fsaudit.security.models.SecurityFinding`
objects into a single integer score in the range [0, 100].

Algorithm
---------
For each severity bucket, sum the per-finding penalties and apply a bucket cap:

    bucket_penalty = min(count × weight, cap)

Then:

    score = max(0, 100 − sum(bucket_penalties))

Weights and caps
----------------
| Severity | Weight | Cap |
|----------|--------|-----|
| CRITICAL | 25     | 40  |
| HIGH     | 10     | 30  |
| MEDIUM   | 4      | 20  |
| LOW      | 1      | 10  |

A score of 100 means a completely clean scan.  A score of 0 means the maximum
possible penalty has been reached across one or more buckets.

Design rationale
----------------
Linear per-finding scoring would cause a flood of low-severity findings
(e.g. 10,000 low findings in a large repo) to floor the score, which is
unintuitive and punishes large codebases.  Per-severity bucket caps prevent
this: a flood of LOW findings cannot reduce the score by more than 10 points
in total, regardless of volume.

The ``security_score`` computed here is completely independent of the
``health_score`` computed by the analysis pipeline — the two scores are NEVER
averaged or combined.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from fsaudit.security.models import Severity

if TYPE_CHECKING:
    from fsaudit.security.models import SecurityFinding


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 10,
    Severity.MEDIUM: 4,
    Severity.LOW: 1,
}

_CAPS: dict[Severity, int] = {
    Severity.CRITICAL: 40,
    Severity.HIGH: 30,
    Severity.MEDIUM: 20,
    Severity.LOW: 10,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_security_score(findings: list["SecurityFinding"]) -> int:
    """Compute an integer security score (0–100) from a list of findings.

    A higher score is better.  100 means zero findings.  The score decreases
    as findings accumulate, but each severity bucket has a cap so that a flood
    of low-severity findings cannot dominate the overall score.

    Args:
        findings: All non-allowlisted findings from the security scan.

    Returns:
        Integer in [0, 100] — 100 = clean, 0 = maximum possible penalty.
    """
    if not findings:
        return 100

    # Count findings per severity
    counts: Counter[Severity] = Counter(f.severity for f in findings)

    total_penalty = 0
    for severity in Severity:  # CRITICAL, HIGH, MEDIUM, LOW (enum declaration order)
        count = counts.get(severity, 0)
        if count == 0:
            continue
        weight = _WEIGHTS[severity]
        cap = _CAPS[severity]
        bucket_penalty = min(count * weight, cap)
        total_penalty += bucket_penalty

    return max(0, 100 - total_penalty)
