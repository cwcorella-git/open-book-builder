"""The source header: a block between two lines of three hyphens, one `key: value` per line."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .report import Report

REQUIRED = ("id", "version", "title", "type", "language")
OPTIONAL = ("author", "tags", "rights")
TYPES = ("book", "article", "document")
ID_RE = re.compile(r"^[a-z0-9-]{1,80}$")
LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


@dataclass
class Header:
    id: str = ""
    version: int = 0
    title: str = ""
    type: str = ""
    language: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    rights: str = ""


def _tags(value: str, line: int, report: Report) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    tags = [t.strip() for t in value.split(",") if t.strip()]
    for tag in tags:
        if ";" in tag or ":" in tag:
            report.error(line, f"The tag '{tag}' contains ';' or ':'. Those characters are reserved by the reader file.")
        elif "\n" in tag:
            report.error(line, "A tag cannot contain a line break.")
    return tags


def parse_header(lines: list[str], report: Report) -> tuple[Header | None, int]:
    """Read the header at the top of the file. Returns (header, index of the first body line)."""
    if not lines or lines[0].strip() != "---":
        report.error(1, "The file must start with a header between two lines of three hyphens.")
        return None, 0
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        report.error(1, "The header is never closed. Add a line of three hyphens after the last field.")
        return None, 0
    raw: dict[str, str] = {}
    for i in range(1, end):
        text = lines[i]
        if not text.strip():
            continue
        key, sep, value = text.partition(":")
        key = key.strip().lower()
        if not sep or not key:
            report.error(i + 1, "A header line must look like 'key: value'.")
            continue
        if key in raw:
            report.error(i + 1, f"The field '{key}' appears twice.")
            continue
        if key not in REQUIRED + OPTIONAL:
            report.note(i + 1, f"The field '{key}' is not used and is ignored.")
        raw[key] = value.strip()
        raw[f"_line_{key}"] = str(i + 1)

    def line_of(key: str) -> int:
        return int(raw.get(f"_line_{key}", "1"))

    header = Header()
    for key in REQUIRED:
        if not raw.get(key):
            report.error(1, f"The header needs a '{key}' field.")
    header.id = raw.get("id", "")
    if header.id and not ID_RE.match(header.id):
        report.error(line_of("id"), "The id may use only a-z, 0-9 and hyphen, and at most 80 characters.")
    version = raw.get("version", "")
    if version:
        if version.isdigit() and int(version) >= 1:
            header.version = int(version)
        else:
            report.error(line_of("version"), "The version must be a whole number, 1 or higher.")
    header.title = raw.get("title", "")
    header.type = raw.get("type", "")
    if header.type and header.type not in TYPES:
        report.error(line_of("type"), "The type must be book, article or document.")
    header.language = raw.get("language", "")
    if header.language and not LANG_RE.match(header.language):
        report.error(line_of("language"), "The language must be a language tag such as en, fr or pt-BR.")
    header.author = raw.get("author", "")
    header.rights = raw.get("rights", "")
    if "tags" in raw:
        header.tags = _tags(raw["tags"], line_of("tags"), report)
    for key in ("title", "author"):
        if "\x00" in getattr(header, key):
            report.error(line_of(key), f"The {key} holds an invalid character.")
    return header, end + 1
