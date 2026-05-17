"""Shannon entropy detector for fsaudit.security.

This detector identifies tokens with high information entropy, which is a
strong indicator of secrets (random API keys, base64-encoded credentials,
high-entropy password values).

Algorithm
---------
1. **Content gate pipeline** — same as secrets detector:
   size gate → extension allowlist → null-byte probe → read text.
2. **Token extraction** — per line, extract candidate tokens using regex
   ``[A-Za-z0-9+/=_\\-]{20,}`` (base64-ish / long-identifier strings).
   Minimum token length is configurable (default 20 chars).
3. **Shannon entropy** — compute ``H = -sum(p_i * log2(p_i))`` over the
   character frequency distribution of the token.
4. **Threshold** — emit a finding when ``H >= entropy_threshold``
   (default 4.5 bits/char).

Redaction
---------
``match_context`` uses a **char-class mask** — each character in the token
is replaced with:
- ``L`` for letters (``[A-Za-z]``)
- ``D`` for digits (``[0-9]``)
- ``S`` for any other symbol

This reveals the token's *shape* (length, composition) without exposing its
value.  The masked string is hard-capped at 60 chars by
``SecurityFinding.__post_init__``.

Design note: dedup with secrets detector
-----------------------------------------
Tokens already matched by a secrets-rule regex could in principle be emitted
twice (once by SecretsDetector, once here).  v1 choice: entropy detector
emits independently and downstream callers (or the report) handle dedup via
path + line_no.  This is the simpler path — acknowledged in design docs.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fsaudit.security.allowlist import is_allowed
from fsaudit.security.detectors.base import ContentDetector
from fsaudit.security.models import SecurityFinding, Severity

if TYPE_CHECKING:
    from fsaudit.scanner.models import FileRecord
    from fsaudit.security.config import SecurityConfig

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_ENTROPY_THRESHOLD: float = 4.5
_DEFAULT_MIN_TOKEN_LENGTH: int = 20
_DEFAULT_MAX_SIZE_BYTES: int = 1_048_576  # 1 MiB
_NULL_BYTE_PROBE_SIZE: int = 8_192

# Token extraction regex: base64-ish / long identifier characters, min 20 chars.
# {20,} lower-bound is enforced by code (configurable), not hard-coded in regex,
# so we use a shorter fixed minimum here and filter by length after extraction.
_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")

# Extensions considered "text" — mirrors the secrets detector set.
_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".env", ".yaml", ".yml", ".json", ".toml",
        ".ini", ".cfg", ".conf", ".properties",
        ".sh", ".bash", ".zsh", ".fish",
        ".txt", ".md", ".rst", ".log",
        ".xml", ".html", ".css",
        ".rb", ".go", ".java", ".cs", ".rs", ".php", ".sql", ".tf",
        ".pem", ".key", ".cer", ".crt",
        ".gitignore", ".dockerignore",
    }
)

_RULE_ID = "entropy-high"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _shannon_entropy(token: str) -> float:
    """Return Shannon entropy (bits/char) for *token*.

    Args:
        token: Non-empty string to measure.

    Returns:
        Entropy in bits per character (0.0 if token is empty).
    """
    if not token:
        return 0.0
    counts = Counter(token)
    total = len(token)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _char_class_mask(token: str) -> str:
    """Replace each character with its class: L (letter), D (digit), S (symbol).

    Args:
        token: The raw high-entropy token string.

    Returns:
        A masked string of equal length using only ``L``, ``D``, ``S``.
    """
    chars: list[str] = []
    for ch in token:
        if ch.isalpha():
            chars.append("L")
        elif ch.isdigit():
            chars.append("D")
        else:
            chars.append("S")
    return "".join(chars)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class EntropyDetector(ContentDetector):
    """Content-based detector for high-entropy tokens (potential secrets).

    Implements the same content-gate pipeline as :class:`SecretsDetector` but
    uses Shannon entropy instead of regex matching, so no keyword pre-filter is
    applied (entropy is keyword-agnostic).

    ``scan_file`` is designed to be called directly from a
    ``ThreadPoolExecutor`` by the T15 pipeline orchestrator.
    """

    @property
    def name(self) -> str:
        return "entropy"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def should_scan(self, record: "FileRecord") -> bool:
        """Pre-filter: mirror size + extension gates from :meth:`scan_file`.

        Lets the orchestrator skip records that would be rejected at gates 1-2
        anyway, avoiding pointless future submissions.  Null-byte probe (gate
        3) requires I/O and stays inside ``scan_file``.
        """
        if record.size_bytes > _DEFAULT_MAX_SIZE_BYTES:
            return False
        if record.extension.lower() not in _TEXT_EXTENSIONS:
            return False
        return True

    def scan_file(
        self,
        record: "FileRecord",
        compiled_rules: object,  # unused — entropy is keyword-agnostic
        config: "SecurityConfig",
        *,
        entropy_threshold: float = _DEFAULT_ENTROPY_THRESHOLD,
        min_token_length: int = _DEFAULT_MIN_TOKEN_LENGTH,
        max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
    ) -> list[SecurityFinding]:
        """Evaluate a single file for high-entropy tokens.

        Args:
            record:           File record to inspect.
            compiled_rules:   Unused (entropy needs no regex rules).
            config:           Active security config (for allowlist).
            entropy_threshold: Minimum Shannon entropy (bits/char) to flag.
            min_token_length:  Minimum token length to consider.
            max_size_bytes:    Size gate threshold in bytes.

        Returns:
            Zero or more :class:`~fsaudit.security.models.SecurityFinding`
            instances.  Empty list on any gate failure.
        """
        path_str = str(record.path)

        # --- Gate 1: size ---
        if record.size_bytes > max_size_bytes:
            _log.debug("entropy: skipping %s (size gate)", path_str)
            return []

        # --- Gate 2: extension ---
        if record.extension.lower() not in _TEXT_EXTENSIONS:
            _log.debug("entropy: skipping %s (extension gate: %s)", path_str, record.extension)
            return []

        # --- Gate 3: null-byte probe ---
        try:
            with open(record.path, "rb") as fh:
                probe = fh.read(_NULL_BYTE_PROBE_SIZE)
        except OSError as exc:
            _log.debug("entropy: cannot probe %s — %s", path_str, exc)
            return []

        if b"\x00" in probe:
            _log.debug("entropy: skipping %s (binary — null byte found)", path_str)
            return []

        # --- Read full text ---
        try:
            with open(record.path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError as exc:
            _log.debug("entropy: cannot read %s — %s", path_str, exc)
            return []

        findings: list[SecurityFinding] = []
        ts = datetime.now(tz=timezone.utc)

        for line_no, line in enumerate(text.splitlines(), start=1):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Extract candidate tokens (20+ char alphanumeric-ish sequences)
            for match in _TOKEN_PATTERN.finditer(line):
                token = match.group()

                # Enforce configurable min-length (regex anchors at 20,
                # but caller may pass a different minimum)
                if len(token) < min_token_length:
                    continue

                entropy = _shannon_entropy(token)
                if entropy < entropy_threshold:
                    continue

                # Redact: char-class mask (shape without value)
                masked = _char_class_mask(token)[:60]  # hard cap before model enforces

                _log.debug(
                    "entropy: high-entropy token in %s at line %d (H=%.2f)",
                    path_str,
                    line_no,
                    entropy,
                )

                finding = SecurityFinding(
                    path=path_str,
                    detector=self.name,
                    rule_id=_RULE_ID,
                    severity=Severity.MEDIUM,
                    line_no=line_no,
                    match_context=masked,  # model truncates to ≤60 chars
                    created_at=ts,
                )

                # --- Allowlist check ---
                if is_allowed(path_str, _RULE_ID, finding.match_context, config.allowlist):
                    _log.debug(
                        "entropy: allowlisted finding in %s at line %d",
                        path_str,
                        line_no,
                    )
                    continue

                findings.append(finding)

        return findings

    def scan(
        self,
        records: list["FileRecord"],
        config: "SecurityConfig",
        *,
        entropy_threshold: float = _DEFAULT_ENTROPY_THRESHOLD,
        min_token_length: int = _DEFAULT_MIN_TOKEN_LENGTH,
        max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
    ) -> list[SecurityFinding]:
        """Scan all *records* serially and return findings.

        The ``ThreadPoolExecutor`` wiring comes in T15 (pipeline orchestrator).

        Args:
            records:           All file records to consider.
            config:            Active security configuration.
            entropy_threshold: Shannon entropy threshold.
            min_token_length:  Minimum token length.
            max_size_bytes:    Size gate threshold in bytes.

        Returns:
            All non-allowlisted high-entropy findings across all records.
        """
        findings: list[SecurityFinding] = []
        for record in records:
            findings.extend(
                self.scan_file(
                    record,
                    None,
                    config,
                    entropy_threshold=entropy_threshold,
                    min_token_length=min_token_length,
                    max_size_bytes=max_size_bytes,
                )
            )
        return findings
