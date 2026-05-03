"""Security configuration loader for fsaudit.

Classes
-------
Rule
    Single detection rule (id, description, severity, regex, keywords).
Allowlist
    Suppression rules — paths, rule IDs, content regexes.
SecurityConfig
    Complete parsed configuration (version + rules + allowlist).

Functions
---------
load_config(path=None) -> SecurityConfig
    Load from explicit path → ~/.fsaudit/security.yaml → bundled patterns.yaml.
    Raises SecurityConfigError on malformed YAML or missing required fields.
"""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyYAML is required for fsaudit security features. "
        "Install it with: pip install pyyaml"
    ) from exc

from fsaudit.security.models import SecurityConfigError


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Rule:
    """A single detection rule loaded from YAML.

    Attributes:
        id:          Unique rule identifier (e.g. ``"aws-access-key"``).
        description: Human-readable description.
        severity:    Severity string: ``"critical"`` | ``"high"`` | ``"medium"`` | ``"low"``.
        regex:       Regular expression pattern string.
        keywords:    Optional list of keyword strings used as a pre-filter.
    """

    id: str
    description: str
    severity: str
    regex: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class Allowlist:
    """Suppression configuration for the security scan.

    Attributes:
        paths:   Glob patterns — findings whose file path matches are suppressed.
        rules:   Rule IDs that are globally suppressed.
        content: Regex patterns matched against ``match_context`` — suppress on match.
    """

    paths: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """Complete parsed security configuration.

    Attributes:
        version:   Config schema version (must be 1).
        rules:     Active detection rules.
        allowlist: Suppression configuration.
    """

    version: int
    rules: list[Rule]
    allowlist: Allowlist


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_BUNDLED_DEFAULT_USER_PATH = Path.home() / ".fsaudit" / "security.yaml"


def load_config(path: Optional[str] = None) -> SecurityConfig:
    """Load and parse a security configuration YAML.

    Resolution order:
    1. *path* — if provided, load that file (raises if missing).
    2. ``~/.fsaudit/security.yaml`` — if it exists.
    3. Bundled ``patterns.yaml`` (always present).

    Args:
        path: Optional explicit path to a YAML configuration file.

    Returns:
        Parsed :class:`SecurityConfig` instance.

    Raises:
        SecurityConfigError: If the YAML is malformed, the ``version`` key is
            absent, or any rule is missing required fields (``id``, ``regex``,
            ``severity``).
    """
    if path is not None:
        source_path = Path(path)
        if not source_path.exists():
            raise SecurityConfigError(
                f"Security config file not found: {source_path}"
            )
        return _load_from_path(source_path)

    if _BUNDLED_DEFAULT_USER_PATH.exists():
        return _load_from_path(_BUNDLED_DEFAULT_USER_PATH)

    return _load_bundled()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_from_path(path: Path) -> SecurityConfig:
    """Parse a YAML file at *path* into a SecurityConfig."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SecurityConfigError(f"Cannot read config file '{path}': {exc}") from exc

    return _parse_yaml(text, filename=str(path))


def _load_bundled() -> SecurityConfig:
    """Load the bundled patterns.yaml shipped with the package."""
    pkg = importlib.resources.files("fsaudit.security")
    yaml_file = pkg / "patterns.yaml"
    text = yaml_file.read_text(encoding="utf-8")
    return _parse_yaml(text, filename="<bundled:patterns.yaml>")


def _parse_yaml(text: str, filename: str) -> SecurityConfig:
    """Parse YAML *text* and return a validated SecurityConfig.

    Raises:
        SecurityConfigError: On any parse or validation failure.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SecurityConfigError(
            f"Malformed YAML in '{filename}': {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise SecurityConfigError(
            f"Config '{filename}' must be a YAML mapping, got {type(data).__name__}"
        )

    # --- version ---
    if "version" not in data:
        raise SecurityConfigError(
            f"Config '{filename}' is missing required key 'version'."
        )
    version = data["version"]
    if version != 1:
        raise SecurityConfigError(
            f"Config '{filename}' has unsupported version {version!r} (expected 1)."
        )

    # --- rules ---
    raw_rules = data.get("rules", []) or []
    rules: list[Rule] = []
    for i, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise SecurityConfigError(
                f"Config '{filename}': rule[{i}] must be a mapping, got {type(raw).__name__}"
            )
        for required in ("id", "regex", "severity"):
            if required not in raw:
                raise SecurityConfigError(
                    f"Config '{filename}': rule[{i}] is missing required field '{required}'."
                )
        rules.append(
            Rule(
                id=raw["id"],
                description=raw.get("description", ""),
                severity=raw["severity"],
                regex=raw["regex"],
                keywords=list(raw.get("keywords") or []),
            )
        )

    # --- allowlist ---
    raw_al = data.get("allowlist") or {}
    allowlist = Allowlist(
        paths=list(raw_al.get("paths") or []),
        rules=list(raw_al.get("rules") or []),
        content=list(raw_al.get("content") or []),
    )

    return SecurityConfig(version=version, rules=rules, allowlist=allowlist)
