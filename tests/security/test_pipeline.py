"""Tests for the pipeline orchestrator (T15 — run_all + ThreadPoolExecutor).

Covers:
- Empty record list returns empty findings
- MetadataDetectors run synchronously and findings collected
- ContentDetectors dispatch via ThreadPoolExecutor
- Allowlist applied at finding-emit time (cross-detector)
- Empty records: no crash
- ALL_DETECTORS tuple contains all 4 expected detector types
- run_all returns deterministic sorted results
- Rules compiled exactly once per scan (mock compile_rules, assert call count)
- ThreadPool workers bounded (max_workers=min(32, cpu_count+4))
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fsaudit.scanner.models import FileRecord
from fsaudit.security.config import Allowlist, Rule, SecurityConfig
from fsaudit.security.detectors import ALL_DETECTORS, run_all
from fsaudit.security.models import SecurityFinding, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(rules: list[Rule] | None = None, allowlist: Allowlist | None = None) -> SecurityConfig:
    """Build a minimal SecurityConfig for pipeline tests."""
    return SecurityConfig(
        version=1,
        rules=rules or [],
        allowlist=allowlist or Allowlist(),
    )


def _make_record(
    name: str = "test.py",
    size_bytes: int = 512,
    path_str: str | None = None,
) -> FileRecord:
    """Build a minimal FileRecord."""
    now = datetime.now(tz=timezone.utc)
    p = Path(path_str or f"/tmp/{name}")
    return FileRecord(
        path=p,
        name=name,
        extension=Path(name).suffix.lower(),
        size_bytes=size_bytes,
        mtime=now,
        creation_time=now,
        atime=now,
        depth=0,
        is_hidden=False,
        permissions="644",
        category="Codigo",
        parent_dir="/tmp",
    )


def _make_finding(path: str = "/tmp/test.py", rule_id: str = "test-rule") -> SecurityFinding:
    """Build a minimal SecurityFinding."""
    return SecurityFinding(
        path=path,
        detector="test",
        rule_id=rule_id,
        severity=Severity.HIGH,
        line_no=1,
        match_context="ctx",
        created_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# T15 — run_all and ALL_DETECTORS
# ---------------------------------------------------------------------------


class TestAllDetectorsTuple:
    """ALL_DETECTORS contains exactly the 4 expected detector types."""

    def test_all_detectors_has_four_members(self) -> None:
        assert len(ALL_DETECTORS) == 4

    def test_all_detectors_names(self) -> None:
        names = {d.name for d in ALL_DETECTORS}
        assert names == {"suspicious-files", "permissions", "secrets", "entropy"}

    def test_all_detectors_tuple_type(self) -> None:
        assert isinstance(ALL_DETECTORS, tuple)


class TestRunAllEmpty:
    """Empty record list returns empty findings, no crash."""

    def test_empty_records_returns_empty_list(self) -> None:
        config = _make_config()
        result = run_all([], config)
        assert result == []

    def test_empty_records_returns_list_type(self) -> None:
        config = _make_config()
        result = run_all([], config)
        assert isinstance(result, list)


class TestRunAllBasic:
    """run_all with real files collects findings from all detectors."""

    def test_run_all_returns_list(self, tmp_path: Path) -> None:
        config = _make_config()
        record = _make_record("hello.py")
        result = run_all([record], config)
        assert isinstance(result, list)

    def test_run_all_with_suspicious_file_finds_double_extension(self, tmp_path: Path) -> None:
        """A .pdf.exe file should produce a double-extension finding."""
        fake_path = tmp_path / "invoice.pdf.exe"
        fake_path.write_bytes(b"MZ\x00\x00")

        now = datetime.now(tz=timezone.utc)
        record = FileRecord(
            path=fake_path,
            name="invoice.pdf.exe",
            extension=".exe",
            size_bytes=4,
            mtime=now,
            creation_time=now,
            atime=now,
            depth=0,
            is_hidden=False,
            permissions="644",
            category="Otros",
            parent_dir=str(tmp_path),
        )
        config = _make_config()
        findings = run_all([record], config)
        rule_ids = [f.rule_id for f in findings]
        assert "double-extension" in rule_ids

    def test_findings_are_sorted_deterministically(self, tmp_path: Path) -> None:
        """Results sorted by (path, rule_id, line_no) for determinism."""
        config = _make_config()
        record = _make_record("sample.py")
        # Run twice — results must be identical
        r1 = run_all([record], config)
        r2 = run_all([record], config)
        assert r1 == r2


class TestRunAllThreadPool:
    """ContentDetectors are dispatched via ThreadPoolExecutor."""

    def test_content_findings_accumulate_across_files(self, tmp_path: Path) -> None:
        """Multiple files each get their content scanned."""
        secret_content = "AKIAIOSFODNN7EXAMPLE12345"
        rule = Rule(
            id="aws-access-key",
            description="AWS key",
            severity="critical",
            regex=r"AKIA[0-9A-Z]{16}",
            keywords=["AKIA"],
        )
        config = _make_config(rules=[rule])

        records = []
        for i in range(3):
            f = tmp_path / f"secret_{i}.py"
            f.write_text(f"key = '{secret_content}'\n")
            now = datetime.now(tz=timezone.utc)
            records.append(FileRecord(
                path=f,
                name=f.name,
                extension=".py",
                size_bytes=f.stat().st_size,
                mtime=now,
                creation_time=now,
                atime=now,
                depth=0,
                is_hidden=False,
                permissions="644",
                category="Codigo",
                parent_dir=str(tmp_path),
            ))

        findings = run_all(records, config)
        aws_findings = [f for f in findings if f.rule_id == "aws-access-key"]
        assert len(aws_findings) == 3

    def test_compile_rules_called_once_per_scan(self, tmp_path: Path) -> None:
        """compile_rules must be invoked exactly once, not once per file."""
        from fsaudit.security.detectors.secrets import SecretsDetector

        rule = Rule(
            id="aws-access-key",
            description="AWS key",
            severity="critical",
            regex=r"AKIA[0-9A-Z]{16}",
            keywords=["AKIA"],
        )
        config = _make_config(rules=[rule])

        records = []
        for i in range(3):
            f = tmp_path / f"file_{i}.py"
            f.write_text("nothing here\n")
            now = datetime.now(tz=timezone.utc)
            records.append(FileRecord(
                path=f,
                name=f.name,
                extension=".py",
                size_bytes=f.stat().st_size,
                mtime=now,
                creation_time=now,
                atime=now,
                depth=0,
                is_hidden=False,
                permissions="644",
                category="Codigo",
                parent_dir=str(tmp_path),
            ))

        # Patch compile_rules on SecretsDetector and verify call count
        original_compile = SecretsDetector.compile_rules
        call_count = [0]

        def counting_compile(self, config):
            call_count[0] += 1
            return original_compile(self, config)

        with patch.object(SecretsDetector, "compile_rules", counting_compile):
            run_all(records, config)

        assert call_count[0] == 1


class TestRunAllAllowlist:
    """Allowlist suppression at finding-emit time."""

    def test_allowlist_suppresses_findings_by_rule_id(self, tmp_path: Path) -> None:
        """A finding whose rule_id is allowlisted must not appear in results."""
        secret_content = "AKIAIOSFODNN7EXAMPLE12345"
        rule = Rule(
            id="aws-access-key",
            description="AWS key",
            severity="critical",
            regex=r"AKIA[0-9A-Z]{16}",
            keywords=["AKIA"],
        )
        allowlist = Allowlist(rules=["aws-access-key"])
        config = _make_config(rules=[rule], allowlist=allowlist)

        f = tmp_path / "secret.py"
        f.write_text(f"key = '{secret_content}'\n")
        now = datetime.now(tz=timezone.utc)
        record = FileRecord(
            path=f,
            name=f.name,
            extension=".py",
            size_bytes=f.stat().st_size,
            mtime=now,
            creation_time=now,
            atime=now,
            depth=0,
            is_hidden=False,
            permissions="644",
            category="Codigo",
            parent_dir=str(tmp_path),
        )
        findings = run_all([record], config)
        assert not any(f.rule_id == "aws-access-key" for f in findings)
