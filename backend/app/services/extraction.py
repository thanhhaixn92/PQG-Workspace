"""Deterministic extraction of workspace files into ordered, provenance-bearing records.

Supports only UTF-8 ``.txt``, ``.md``, ``.csv``, ``.json`` and ``.docx`` using the
Python standard library. No AI, no third-party dependencies, no PDF/OCR.

Design rules (DIRAP v3.0 Extraction slice):
* Records carry an ordinal ``seq`` (1-based) and a human-readable ``provenance``
  pointing back into the source file (line / row / item / paragraph).
* The original file stays in the workspace; only extracted records are stored.
* The extractor version is bumped whenever the extraction logic changes so that
  previously stored results can be identified.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

EXTRACTOR_VERSION = "1.0.0"

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".txt": "txt",
    ".md": "md",
    ".csv": "csv",
    ".json": "json",
    ".docx": "docx",
}

_DOCX_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_DOCX_XML_BYTES = 4 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100


def file_type_for(file_name: str) -> str | None:
    """Map a file name to a supported extraction type (e.g. 'txt', 'docx')."""
    return SUPPORTED_EXTENSIONS.get(Path(file_name).suffix.lower())


def sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 of a file's raw content, chunked for large files."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_bytes(content: bytes) -> str:
    """Compute the source revision for an immutable in-memory snapshot."""
    return hashlib.sha256(content).hexdigest()


def extract(path: Path, file_type: str) -> list[dict]:
    """Extract ordered records from *path*.

    Returns a list of ``{"seq": int, "content": str, "provenance": str}``.
    Raises ``ValueError`` for invalid content (bad encoding, malformed file).
    """
    return extract_bytes(path.read_bytes(), file_type)


def extract_bytes(content: bytes, file_type: str) -> list[dict]:
    """Extract records from one immutable raw-file snapshot.

    The caller may safely persist the SHA-256 of *content* with these records:
    none of the format readers re-open the source path.
    """
    if file_type in ("txt", "md"):
        return _extract_text(content)
    if file_type == "csv":
        return _extract_csv(content)
    if file_type == "json":
        return _extract_json(content)
    if file_type == "docx":
        return _extract_docx(content)
    raise ValueError(f"Unsupported file type: {file_type}")


def _decode_utf8(content: bytes, label: str) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8 {label}") from exc


def _extract_text(content: bytes) -> list[dict]:
    text = _decode_utf8(content, "text")
    records: list[dict] = []
    seq = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            seq += 1
            records.append({"seq": seq, "content": line, "provenance": f"line {lineno}"})
    return records


def _extract_csv(content: bytes) -> list[dict]:
    records: list[dict] = []
    try:
        rows = list(csv.reader(io.StringIO(_decode_utf8(content, "CSV"), newline="")))
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV file: {exc}") from exc

    for rowno, row in enumerate(rows, start=1):
        records.append(
            {
                "seq": rowno,
                "content": json.dumps(row, ensure_ascii=False),
                "provenance": f"row {rowno}",
            }
        )
    return records


def _extract_json(content: bytes) -> list[dict]:
    try:
        data = json.loads(_decode_utf8(content, "JSON"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {exc}") from exc

    records: list[dict] = []
    if isinstance(data, list):
        for i, item in enumerate(data, start=1):
            records.append(
                {
                    "seq": i,
                    "content": json.dumps(item, ensure_ascii=False),
                    "provenance": f"item[{i - 1}]",
                }
            )
    elif isinstance(data, dict):
        for i, (key, value) in enumerate(data.items(), start=1):
            records.append(
                {
                    "seq": i,
                    "content": json.dumps(value, ensure_ascii=False),
                    "provenance": f".{key}",
                }
            )
    else:
        records.append(
            {
                "seq": 1,
                "content": json.dumps(data, ensure_ascii=False),
                "provenance": "$",
            }
        )
    return records


def _extract_docx(content: bytes) -> list[dict]:
    """Extract non-empty paragraphs from a .docx via the ZIP + XML standard library."""
    try:
        with ZipFile(io.BytesIO(content)) as zf:
            if "word/document.xml" not in zf.namelist():
                return []
            info = zf.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise ValueError("DOCX document.xml exceeds extraction limit")
            if info.compress_size == 0 or info.file_size / info.compress_size > MAX_DOCX_COMPRESSION_RATIO:
                raise ValueError("DOCX compression ratio exceeds extraction limit")
            with zf.open("word/document.xml") as f:
                tree = ET.parse(f)
    except (BadZipFile, ET.ParseError) as exc:
        raise ValueError("Invalid docx file") from exc

    root = tree.getroot()
    records: list[dict] = []
    seq = 0
    for para in root.iter(f"{_DOCX_W_NS}p"):
        text = "".join(node.text or "" for node in para.iter(f"{_DOCX_W_NS}t"))
        if text.strip():
            seq += 1
            records.append({"seq": seq, "content": text, "provenance": f"paragraph {seq}"})
    return records
