"""Secrets content detector for fsaudit.security.

This detector implements a multi-stage content gate pipeline to efficiently
locate secret material (API keys, tokens, private-key headers, etc.) inside
text files, while avoiding false positives from binary files, large files,
and files with no relevant keywords.

Pipeline (in order)
-------------------
1. **Size gate** — ``FileRecord.size_bytes <= config.max_size_bytes``.
   Default 1 MiB.  Oversize files are counted as skipped and ignored.
2. **Extension allowlist** — file extension must be in the configured text-
   extension set.  Binary-looking extensions (images, archives, …) are skipped.
3. **Null-byte probe** — first 8 192 bytes read in binary mode; if ``b'\\x00'``
   is present the file is treated as binary and skipped.
4. **Keyword pre-filter** (per rule) — if none of the rule's ``keywords`` appear
   in the file text the rule is not applied.  Prevents expensive regex work on
   clearly irrelevant files.
5. **Regex match** — compiled regex applied line-by-line (``enumerate/splitlines``
   for accurate 1-based ``line_no``).

Redaction
---------
``SecurityFinding.match_context`` is a slice of the matched line centred on
the match start: ``line[max(0, start-20):start+40]``.  This 60-char slice is
then passed to ``SecurityFinding.__post_init__``, which hard-truncates to 60
characters — so even if arithmetic produces a longer string, truncation is
always enforced at the model level.

Privacy guarantee
-----------------
Loggers in this module NEVER emit match content.  Only ``rule_id`` and
``path`` are logged at DEBUG level.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

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

_DEFAULT_MAX_SIZE_BYTES: int = 1_048_576  # 1 MiB

# Extensions considered "text" — the null-byte probe is the second filter;
# this set covers common source / config / doc / script extensions.
_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".env", ".yaml", ".yml", ".json", ".toml",
        ".ini", ".cfg", ".conf", ".properties",
        ".sh", ".bash", ".zsh", ".fish",
        ".txt", ".md", ".rst", ".log",
        ".xml", ".html", ".css",
        ".rb", ".go", ".java", ".cs", ".rs", ".php", ".sql", ".tf",
        ".pem", ".key", ".cer", ".crt",  # certificate files
        ".gitignore", ".dockerignore",
    }
)

_NULL_BYTE_PROBE_SIZE: int = 8_192
_MATCH_CONTEXT_BEFORE: int = 20
_MATCH_CONTEXT_AFTER: int = 40

# Severity string → Severity enum
_SEVERITY_MAP: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}


# ---------------------------------------------------------------------------
# Compiled rule container
# ---------------------------------------------------------------------------


class _CompiledRule(NamedTuple):
    """A fully compiled rule ready for matching."""

    rule_id: str
    pattern: re.Pattern[str]
    severity: Severity
    keywords: frozenset[str]


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class SecretsDetector(ContentDetector):
    """Content-based detector for secrets, tokens, and private-key material.

    Rules are compiled ONCE per scan via :meth:`compile_rules` and shared
    across calls to :meth:`scan_file`.  The orchestrator (T15) will dispatch
    ``scan_file`` calls via ``ThreadPoolExecutor``; the :mod:`re` module is
    thread-safe so compiled patterns can be shared freely.
    """

    @property
    def name(self) -> str:
        return "secrets"

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

    def compile_rules(self, config: "SecurityConfig") -> list[_CompiledRule]:
        """Compile all rules from *config* into regex patterns.

        Compiles ONCE per scan — the result is passed to every :meth:`scan_file`
        call.  Skips rules with invalid regex patterns (logs a warning).

        Args:
            config: Active :class:`~fsaudit.security.config.SecurityConfig`.

        Returns:
            List of :class:`_CompiledRule` named-tuples.
        """
        compiled: list[_CompiledRule] = []
        for rule in config.rules:
            try:
                pattern = re.compile(rule.regex, re.MULTILINE)
            except re.error as exc:
                _log.warning("Skipping rule %r: invalid regex — %s", rule.id, exc)
                continue
            severity = _SEVERITY_MAP.get(rule.severity, Severity.LOW)
            compiled.append(
                _CompiledRule(
                    rule_id=rule.id,
                    pattern=pattern,
                    severity=severity,
                    keywords=frozenset(rule.keywords),
                )
            )
        return compiled

    def scan_file(
        self,
        record: "FileRecord",
        compiled_rules: list[_CompiledRule],
        config: "SecurityConfig",
        *,
        max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
    ) -> list[SecurityFinding]:
        """Evaluate a single file and return findings.

        This method is designed to be called in isolation from a
        ``ThreadPoolExecutor`` (future T15 orchestrator).

        Args:
            record:         The file record to evaluate.
            compiled_rules: Pre-compiled rules from :meth:`compile_rules`.
            config:         Active security config (for allowlist checks).
            max_size_bytes: Size gate threshold in bytes (default 1 MiB).

        Returns:
            Zero or more :class:`~fsaudit.security.models.SecurityFinding`
            instances.  Empty list on any gate failure.
        """
        path_str = str(record.path)

        # --- Gate 1: size ---
        if record.size_bytes > max_size_bytes:
            _log.debug("secrets: skipping %s (size gate)", path_str)
            return []

        # --- Gate 2: extension ---
        if record.extension.lower() not in _TEXT_EXTENSIONS:
            _log.debug("secrets: skipping %s (extension gate: %s)", path_str, record.extension)
            return []

        # --- Gate 3: null-byte probe ---
        try:
            with open(record.path, "rb") as fh:
                probe = fh.read(_NULL_BYTE_PROBE_SIZE)
        except OSError as exc:
            _log.debug("secrets: cannot probe %s — %s", path_str, exc)
            return []

        if b"\x00" in probe:
            _log.debug("secrets: skipping %s (binary — null byte found)", path_str)
            return []

        # --- Read full text ---
        try:
            with open(record.path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError as exc:
            _log.debug("secrets: cannot read %s — %s", path_str, exc)
            return []

        findings: list[SecurityFinding] = []
        ts = datetime.now(tz=timezone.utc)
        lines = text.splitlines()

        for compiled_rule in compiled_rules:
            # --- Gate 4: keyword pre-filter ---
            if compiled_rule.keywords:
                if not any(kw in text for kw in compiled_rule.keywords):
                    continue

            # --- Gate 5: regex match (per-line for accurate line_no) ---
            for line_no, line in enumerate(lines, start=1):
                for match in compiled_rule.pattern.finditer(line):
                    # Build redacted context slice (≤ 60 chars enforced by model)
                    start = match.start()
                    ctx = line[max(0, start - _MATCH_CONTEXT_BEFORE): start + _MATCH_CONTEXT_AFTER]
                    # Log only rule_id + path — NEVER match content
                    _log.debug(
                        "secrets: match for rule %r in %s at line %d",
                        compiled_rule.rule_id,
                        path_str,
                        line_no,
                    )

                    finding = SecurityFinding(
                        path=path_str,
                        detector=self.name,
                        rule_id=compiled_rule.rule_id,
                        severity=compiled_rule.severity,
                        line_no=line_no,
                        match_context=ctx,  # model truncates to ≤ 60 chars
                        created_at=ts,
                    )

                    # --- Allowlist check ---
                    if is_allowed(path_str, compiled_rule.rule_id, finding.match_context, config.allowlist):
                        _log.debug(
                            "secrets: allowlisted finding for rule %r in %s",
                            compiled_rule.rule_id,
                            path_str,
                        )
                        continue

                    findings.append(finding)

        return findings

    def scan(
        self,
        records: list["FileRecord"],
        config: "SecurityConfig",
        *,
        max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
    ) -> list[SecurityFinding]:
        """Scan all *records* serially and return findings.

        The ``ThreadPoolExecutor`` wiring comes in T15 (pipeline orchestrator).
        For now each record is processed sequentially so ``scan_file`` can be
        tested in isolation.

        Args:
            records:        All file records to consider.
            config:         Active security configuration.
            max_size_bytes: Size gate threshold (default 1 MiB).

        Returns:
            All non-allowlisted findings across all records.
        """
        compiled_rules = self.compile_rules(config)
        findings: list[SecurityFinding] = []
        for record in records:
            findings.extend(
                self.scan_file(record, compiled_rules, config, max_size_bytes=max_size_bytes)
            )
        return findings
