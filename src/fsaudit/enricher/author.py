"""Author metadata extractor for common document formats.

Supports OOXML (.docx, .xlsx, .pptx), ODF (.odt, .ods, .odp), and PDF.
All private extractors raise on error — _safe_extract() wraps them for
use in enrich_authors().
"""

from __future__ import annotations

import logging
import zipfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import replace

from fsaudit.scanner.models import FileRecord

logger = logging.getLogger("fsaudit.enricher.author")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _normalize(value: str | None) -> str | None:
    """Strip whitespace; return None if result is empty."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Format-specific extractors (raise on any failure)
# ---------------------------------------------------------------------------

def _extract_ooxml_author(path: str) -> str | None:
    """Extract dc:creator from OOXML docProps/core.xml.

    Raises:
        zipfile.BadZipFile: If the file is not a valid ZIP.
        KeyError: If docProps/core.xml is missing from the archive.
    """
    with zipfile.ZipFile(path) as zf:
        with zf.open("docProps/core.xml") as f:
            tree = ET.parse(f)
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            elem = tree.find(".//dc:creator", ns)
            return _normalize(elem.text if elem is not None else None)


def _extract_odf_author(path: str) -> str | None:
    """Extract meta:initial-creator from ODF meta.xml.

    Raises:
        zipfile.BadZipFile: If the file is not a valid ZIP.
        KeyError: If meta.xml is missing from the archive.
    """
    with zipfile.ZipFile(path) as zf:
        with zf.open("meta.xml") as f:
            tree = ET.parse(f)
            ns = {"meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"}
            elem = tree.find(".//meta:initial-creator", ns)
            return _normalize(elem.text if elem is not None else None)


_pypdf_warned = False

def _extract_pdf_author(path: str) -> str | None:
    """Extract /Author from PDF metadata via pypdf.

    Raises:
        Exception: Any pypdf or IO error propagates to caller.
    """
    global _pypdf_warned
    try:
        from pypdf import PdfReader
    except ImportError:
        if not _pypdf_warned:
            logger.warning("pypdf not installed — PDF author extraction disabled")
            _pypdf_warned = True
        return None
    reader = PdfReader(path)
    if reader.metadata is None:
        return None
    return _normalize(reader.metadata.author)


# ---------------------------------------------------------------------------
# Extension → extractor mapping
# ---------------------------------------------------------------------------

_EXTENSION_EXTRACTORS: dict[str, Callable[[str], str | None]] = {
    ".docx": _extract_ooxml_author,
    ".xlsx": _extract_ooxml_author,
    ".pptx": _extract_ooxml_author,
    ".odt": _extract_odf_author,
    ".ods": _extract_odf_author,
    ".odp": _extract_odf_author,
    ".pdf": _extract_pdf_author,
}


# ---------------------------------------------------------------------------
# Safe wrapper
# ---------------------------------------------------------------------------

def _safe_extract(extractor: Callable[[str], str | None], path: str) -> str | None:
    """Call extractor and return None on any exception."""
    try:
        return extractor(path)
    except PermissionError:
        logger.warning("Permission denied reading metadata: %s", path)
        return None
    except zipfile.BadZipFile:
        logger.debug("Not a valid ZIP (may be locked by another app): %s", path)
        return None
    except Exception:
        logger.debug("Failed to extract author from %s", path, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_authors(records: list[FileRecord]) -> list[FileRecord]:
    """Enrich FileRecord list with author metadata where extractable.

    For each record whose extension is in _EXTENSION_EXTRACTORS, attempt
    to extract the author and return a new FileRecord with author set.
    Records with unsupported extensions are returned unchanged (same object).
    Extraction failures silently set author=None.

    Args:
        records: List of FileRecord instances (typically classifier output).

    Returns:
        New list of the same length with author fields populated where possible.
    """
    if not records:
        return []

    result: list[FileRecord] = []
    for record in records:
        ext = record.extension.lower()
        extractor = _EXTENSION_EXTRACTORS.get(ext)
        if extractor is not None:
            author = _safe_extract(extractor, str(record.path))
            result.append(replace(record, author=author))
        else:
            result.append(record)
    return result
