"""Tests for the author enricher module (OOXML, ODF, PDF extractors + enrich_authors)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from fsaudit.scanner.models import FileRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(tmp_path: Path, name: str, author: str | None = None) -> FileRecord:
    """Build a minimal FileRecord pointing to a real file path."""
    ext = Path(name).suffix
    p = tmp_path / name
    p.touch()
    return FileRecord(
        path=p,
        name=name,
        extension=ext,
        size_bytes=0,
        mtime=datetime(2025, 1, 1),
        creation_time=datetime(2025, 1, 1),
        atime=datetime(2025, 1, 1),
        depth=0,
        is_hidden=False,
        permissions="644",
        author=author,
    )


def _create_ooxml_fixture(tmp_path: Path, name: str, author: str) -> Path:
    path = tmp_path / name
    core_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:creator>{author}</dc:creator>
</cp:coreProperties>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core_xml)
    return path


def _create_ooxml_fixture_no_core(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", "<root/>")
    return path


def _create_ooxml_fixture_empty_creator(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    core_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:creator></dc:creator>
</cp:coreProperties>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core_xml)
    return path


def _create_ooxml_fixture_whitespace_creator(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    core_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:creator>   </dc:creator>
</cp:coreProperties>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core_xml)
    return path


def _create_odf_fixture(tmp_path: Path, name: str, author: str) -> Path:
    path = tmp_path / name
    meta_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                      xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0">
    <office:meta>
        <meta:initial-creator>{author}</meta:initial-creator>
    </office:meta>
</office:document-meta>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("meta.xml", meta_xml)
    return path


def _create_odf_fixture_no_meta(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("content.xml", "<root/>")
    return path


def _create_odf_fixture_empty_creator(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    meta_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                      xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0">
    <office:meta>
        <meta:initial-creator></meta:initial-creator>
    </office:meta>
</office:document-meta>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("meta.xml", meta_xml)
    return path


def _create_pdf_fixture(tmp_path: Path, name: str, author: str | None = None) -> Path:
    from pypdf import PdfWriter
    path = tmp_path / name
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    if author is not None:
        writer.add_metadata({"/Author": author})
    with open(path, "wb") as f:
        writer.write(f)
    return path


# ===========================================================================
# OOXML extractor tests
# ===========================================================================

class TestExtractOoxmlAuthor:
    """Tests for _extract_ooxml_author()."""

    def test_extract_ooxml_docx_with_author(self, tmp_path: Path) -> None:
        path = _create_ooxml_fixture(tmp_path, "doc.docx", "Alice")
        from fsaudit.enricher.author import _extract_ooxml_author
        assert _extract_ooxml_author(str(path)) == "Alice"

    def test_extract_ooxml_xlsx_with_author(self, tmp_path: Path) -> None:
        path = _create_ooxml_fixture(tmp_path, "sheet.xlsx", "Bob")
        from fsaudit.enricher.author import _extract_ooxml_author
        assert _extract_ooxml_author(str(path)) == "Bob"

    def test_extract_ooxml_pptx_with_author(self, tmp_path: Path) -> None:
        path = _create_ooxml_fixture(tmp_path, "slides.pptx", "Carol")
        from fsaudit.enricher.author import _extract_ooxml_author
        assert _extract_ooxml_author(str(path)) == "Carol"

    def test_extract_ooxml_missing_core_xml(self, tmp_path: Path) -> None:
        path = _create_ooxml_fixture_no_core(tmp_path, "no_core.docx")
        from fsaudit.enricher.author import _extract_ooxml_author
        with pytest.raises(Exception):
            _extract_ooxml_author(str(path))

    def test_extract_ooxml_empty_creator(self, tmp_path: Path) -> None:
        path = _create_ooxml_fixture_empty_creator(tmp_path, "empty.docx")
        from fsaudit.enricher.author import _extract_ooxml_author
        assert _extract_ooxml_author(str(path)) is None

    def test_extract_ooxml_whitespace_creator(self, tmp_path: Path) -> None:
        path = _create_ooxml_fixture_whitespace_creator(tmp_path, "ws.docx")
        from fsaudit.enricher.author import _extract_ooxml_author
        assert _extract_ooxml_author(str(path)) is None

    def test_extract_ooxml_corrupt_zip(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.docx"
        path.write_bytes(b"not a zip file at all")
        from fsaudit.enricher.author import _extract_ooxml_author
        with pytest.raises(Exception):
            _extract_ooxml_author(str(path))


# ===========================================================================
# ODF extractor tests
# ===========================================================================

class TestExtractOdfAuthor:
    """Tests for _extract_odf_author()."""

    def test_extract_odf_odt_with_author(self, tmp_path: Path) -> None:
        path = _create_odf_fixture(tmp_path, "doc.odt", "Diana")
        from fsaudit.enricher.author import _extract_odf_author
        assert _extract_odf_author(str(path)) == "Diana"

    def test_extract_odf_ods_with_author(self, tmp_path: Path) -> None:
        path = _create_odf_fixture(tmp_path, "sheet.ods", "Eve")
        from fsaudit.enricher.author import _extract_odf_author
        assert _extract_odf_author(str(path)) == "Eve"

    def test_extract_odf_odp_with_author(self, tmp_path: Path) -> None:
        path = _create_odf_fixture(tmp_path, "slides.odp", "Frank")
        from fsaudit.enricher.author import _extract_odf_author
        assert _extract_odf_author(str(path)) == "Frank"

    def test_extract_odf_missing_meta_xml(self, tmp_path: Path) -> None:
        path = _create_odf_fixture_no_meta(tmp_path, "no_meta.odt")
        from fsaudit.enricher.author import _extract_odf_author
        with pytest.raises(Exception):
            _extract_odf_author(str(path))

    def test_extract_odf_empty_creator(self, tmp_path: Path) -> None:
        path = _create_odf_fixture_empty_creator(tmp_path, "empty.odt")
        from fsaudit.enricher.author import _extract_odf_author
        assert _extract_odf_author(str(path)) is None


# ===========================================================================
# PDF extractor tests
# ===========================================================================

class TestExtractPdfAuthor:
    """Tests for _extract_pdf_author()."""

    def test_extract_pdf_with_author(self, tmp_path: Path) -> None:
        path = _create_pdf_fixture(tmp_path, "doc.pdf", "Grace")
        from fsaudit.enricher.author import _extract_pdf_author
        assert _extract_pdf_author(str(path)) == "Grace"

    def test_extract_pdf_no_metadata(self, tmp_path: Path) -> None:
        path = _create_pdf_fixture(tmp_path, "nometa.pdf", None)
        from fsaudit.enricher.author import _extract_pdf_author
        # pypdf returns empty metadata dict or None author — either way, None
        result = _extract_pdf_author(str(path))
        assert result is None

    def test_extract_pdf_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.pdf"
        path.write_bytes(b"not a PDF")
        from fsaudit.enricher.author import _extract_pdf_author
        with pytest.raises(Exception):
            _extract_pdf_author(str(path))


# ===========================================================================
# enrich_authors() public function tests
# ===========================================================================

class TestEnrichAuthors:
    """Tests for enrich_authors() public function."""

    def test_enrich_authors_mixed_list(self, tmp_path: Path) -> None:
        """Only .docx and .pdf get enriched; .txt stays as-is."""
        docx_path = _create_ooxml_fixture(tmp_path, "doc.docx", "Alice")
        pdf_path = _create_pdf_fixture(tmp_path, "report.pdf", "Bob")
        txt_path = tmp_path / "notes.txt"
        txt_path.write_text("hello")

        docx_rec = FileRecord(
            path=docx_path, name="doc.docx", extension=".docx", size_bytes=0,
            mtime=datetime(2025, 1, 1), creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1), depth=0, is_hidden=False, permissions="644",
        )
        pdf_rec = FileRecord(
            path=pdf_path, name="report.pdf", extension=".pdf", size_bytes=0,
            mtime=datetime(2025, 1, 1), creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1), depth=0, is_hidden=False, permissions="644",
        )
        txt_rec = FileRecord(
            path=txt_path, name="notes.txt", extension=".txt", size_bytes=5,
            mtime=datetime(2025, 1, 1), creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1), depth=0, is_hidden=False, permissions="644",
        )

        from fsaudit.enricher import enrich_authors
        result = enrich_authors([docx_rec, txt_rec, pdf_rec])

        assert result[0].author == "Alice"
        assert result[1] is txt_rec  # unchanged
        assert result[2].author == "Bob"

    def test_enrich_authors_empty_list(self) -> None:
        from fsaudit.enricher import enrich_authors
        assert enrich_authors([]) == []

    def test_enrich_authors_unsupported_unchanged(self, tmp_path: Path) -> None:
        """A .txt record is returned as the same object (not replaced)."""
        txt_path = tmp_path / "file.txt"
        txt_path.write_text("content")
        rec = FileRecord(
            path=txt_path, name="file.txt", extension=".txt", size_bytes=7,
            mtime=datetime(2025, 1, 1), creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1), depth=0, is_hidden=False, permissions="644",
        )
        from fsaudit.enricher import enrich_authors
        result = enrich_authors([rec])
        assert result[0] is rec

    def test_enrich_authors_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        """Corrupt .docx does not raise — returns record with author=None."""
        bad_path = tmp_path / "bad.docx"
        bad_path.write_bytes(b"not a zip")
        rec = FileRecord(
            path=bad_path, name="bad.docx", extension=".docx", size_bytes=9,
            mtime=datetime(2025, 1, 1), creation_time=datetime(2025, 1, 1),
            atime=datetime(2025, 1, 1), depth=0, is_hidden=False, permissions="644",
        )
        from fsaudit.enricher import enrich_authors
        result = enrich_authors([rec])
        assert result[0].author is None

    def test_enrich_authors_preserves_list_length(self, tmp_path: Path) -> None:
        """Output always has the same length as input."""
        records = []
        for i in range(5):
            p = tmp_path / f"file{i}.txt"
            p.write_text("x")
            records.append(FileRecord(
                path=p, name=p.name, extension=".txt", size_bytes=1,
                mtime=datetime(2025, 1, 1), creation_time=datetime(2025, 1, 1),
                atime=datetime(2025, 1, 1), depth=0, is_hidden=False, permissions="644",
            ))
        from fsaudit.enricher import enrich_authors
        result = enrich_authors(records)
        assert len(result) == 5
