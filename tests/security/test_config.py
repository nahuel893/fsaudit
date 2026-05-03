"""Tests for security config (T04, T07, T08)."""

from __future__ import annotations

import importlib.resources
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T04 — bundled YAML
# ---------------------------------------------------------------------------

def test_bundled_patterns_yaml_loadable_via_importlib():
    """patterns.yaml must be accessible via importlib.resources from the package."""
    pkg = importlib.resources.files("fsaudit.security")
    yaml_file = pkg / "patterns.yaml"
    text = yaml_file.read_text(encoding="utf-8")
    assert "version:" in text
    assert "rules:" in text


# ---------------------------------------------------------------------------
# T07 — dataclasses: Rule, Allowlist, SecurityConfig
# ---------------------------------------------------------------------------

def test_rule_dataclass_fields():
    """Rule must expose id, description, severity, regex, keywords."""
    from fsaudit.security.config import Rule
    r = Rule(
        id="test-rule",
        description="A test rule",
        severity="high",
        regex=r"TEST[0-9]+",
        keywords=["TEST"],
    )
    assert r.id == "test-rule"
    assert r.description == "A test rule"
    assert r.severity == "high"
    assert r.regex == r"TEST[0-9]+"
    assert r.keywords == ["TEST"]


def test_rule_keywords_defaults_empty():
    """Rule.keywords should default to an empty list when not provided."""
    from fsaudit.security.config import Rule
    r = Rule(id="x", description="d", severity="low", regex="X")
    assert r.keywords == []


def test_allowlist_defaults_empty():
    """Allowlist constructed with no args must default all lists to empty."""
    from fsaudit.security.config import Allowlist
    al = Allowlist()
    assert al.paths == []
    assert al.rules == []
    assert al.content == []


def test_allowlist_custom_values():
    """Allowlist must accept explicit lists."""
    from fsaudit.security.config import Allowlist
    al = Allowlist(paths=["**/node_modules/**"], rules=["test-rule"], content=["dummy"])
    assert "**/node_modules/**" in al.paths
    assert "test-rule" in al.rules
    assert "dummy" in al.content


def test_security_config_has_rules_and_allowlist():
    """SecurityConfig must hold a list of Rules and an Allowlist."""
    from fsaudit.security.config import Allowlist, Rule, SecurityConfig
    r = Rule(id="r", description="d", severity="low", regex="R")
    al = Allowlist()
    cfg = SecurityConfig(version=1, rules=[r], allowlist=al)
    assert cfg.version == 1
    assert len(cfg.rules) == 1
    assert isinstance(cfg.allowlist, Allowlist)


# ---------------------------------------------------------------------------
# T08 — load_config()
# ---------------------------------------------------------------------------

def test_load_bundled_returns_min_5_rules():
    """load_config() with no args must return the bundled config (>=5 rules)."""
    from fsaudit.security.config import load_config
    cfg = load_config()
    assert cfg.version == 1
    assert len(cfg.rules) >= 5


def test_load_custom_path_overrides_bundled(tmp_path: Path):
    """load_config(path) must use the supplied YAML, not the bundled one."""
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        textwrap.dedent("""\
            version: 1
            rules:
              - id: custom-rule
                description: Custom
                severity: high
                regex: 'CUSTOM[0-9]+'
                keywords: [CUSTOM]
            allowlist:
              paths: []
              rules: []
              content: []
        """),
        encoding="utf-8",
    )
    from fsaudit.security.config import load_config
    cfg = load_config(str(custom))
    assert len(cfg.rules) == 1
    assert cfg.rules[0].id == "custom-rule"


def test_load_malformed_yaml_raises(tmp_path: Path):
    """load_config must raise SecurityConfigError on malformed YAML."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\nrules: [\nbad yaml {{\n", encoding="utf-8")
    from fsaudit.security.config import load_config
    from fsaudit.security.models import SecurityConfigError
    with pytest.raises(SecurityConfigError):
        load_config(str(bad))


def test_load_missing_version_raises(tmp_path: Path):
    """load_config must raise SecurityConfigError when 'version' key is absent."""
    no_ver = tmp_path / "nover.yaml"
    no_ver.write_text("rules: []\nallowlist: {paths: [], rules: [], content: []}\n", encoding="utf-8")
    from fsaudit.security.config import load_config
    from fsaudit.security.models import SecurityConfigError
    with pytest.raises(SecurityConfigError, match="version"):
        load_config(str(no_ver))


def test_load_missing_required_field_raises(tmp_path: Path):
    """load_config must raise SecurityConfigError when a rule is missing 'id' or 'regex'."""
    bad_rule = tmp_path / "badrule.yaml"
    bad_rule.write_text(
        textwrap.dedent("""\
            version: 1
            rules:
              - description: Missing id and regex
                severity: high
            allowlist:
              paths: []
              rules: []
              content: []
        """),
        encoding="utf-8",
    )
    from fsaudit.security.config import load_config
    from fsaudit.security.models import SecurityConfigError
    with pytest.raises(SecurityConfigError):
        load_config(str(bad_rule))
