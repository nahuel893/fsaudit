"""Tests for security allowlist (T09)."""

from __future__ import annotations

import pytest

from fsaudit.security.config import Allowlist


def test_path_glob_match_node_modules():
    """A path inside node_modules must be suppressed by glob."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(paths=["**/node_modules/**"])
    assert is_allowed(
        path="/project/node_modules/lodash/foo.js",
        rule_id="generic-api-key",
        match_context="some context",
        allowlist=al,
    ) is True


def test_path_glob_no_match():
    """A path that doesn't match any glob must not be suppressed."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(paths=["**/node_modules/**"])
    assert is_allowed(
        path="/project/src/app.py",
        rule_id="generic-api-key",
        match_context="token=abc123",
        allowlist=al,
    ) is False


def test_rule_id_suppressed():
    """A finding whose rule_id appears in allowlist.rules must be suppressed."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(rules=["generic-api-key"])
    assert is_allowed(
        path="/project/src/app.py",
        rule_id="generic-api-key",
        match_context="token=abc123",
        allowlist=al,
    ) is True


def test_rule_id_not_in_list_allowed():
    """A finding whose rule_id is NOT in allowlist.rules must not be suppressed."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(rules=["other-rule"])
    assert is_allowed(
        path="/project/src/app.py",
        rule_id="aws-access-key",
        match_context="AKIA1234567890123456",
        allowlist=al,
    ) is False


def test_content_regex_suppresses():
    """A finding whose match_context matches a content regex must be suppressed."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(content=[r"PLACEHOLDER"])
    assert is_allowed(
        path="/project/src/app.py",
        rule_id="aws-access-key",
        match_context="PLACEHOLDER_KEY_HERE",
        allowlist=al,
    ) is True


def test_content_regex_no_match_not_suppressed():
    """A finding whose match_context does NOT match content regex must not be suppressed."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(content=[r"PLACEHOLDER"])
    assert is_allowed(
        path="/project/src/app.py",
        rule_id="aws-access-key",
        match_context="AKIAIOSFODNN7EXAMPLE",
        allowlist=al,
    ) is False


def test_all_three_gates_combined():
    """If any gate matches, the finding must be suppressed."""
    from fsaudit.security.allowlist import is_allowed
    # Only path gate matches
    al = Allowlist(
        paths=["**/.git/**"],
        rules=["other"],
        content=[r"NOMATCH"],
    )
    assert is_allowed(
        path="/project/.git/config",
        rule_id="aws-access-key",
        match_context="real secret value",
        allowlist=al,
    ) is True


def test_empty_allowlist_allows_all():
    """An empty allowlist must never suppress any finding (returns False)."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist()
    assert is_allowed(
        path="/project/src/app.py",
        rule_id="aws-access-key",
        match_context="AKIAIOSFODNN7EXAMPLE",
        allowlist=al,
    ) is False


def test_windows_path_separator_normalised():
    """Windows-style backslash paths must still match globs."""
    from fsaudit.security.allowlist import is_allowed
    al = Allowlist(paths=["**/node_modules/**"])
    # Backslash path should be normalised to forward slashes for matching
    assert is_allowed(
        path=r"C:\project\node_modules\lodash\foo.js",
        rule_id="generic-api-key",
        match_context="some context",
        allowlist=al,
    ) is True
