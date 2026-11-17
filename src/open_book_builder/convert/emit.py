"""Write the reader's file from a parsed work. The output is the same bytes every time."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .body import check_runs, convert_body
from .parse import Header, parse_header
from .report import Report


@dataclass
class Converted:
    header: Header | None
    data: bytes | None  # None when the report holds an error
    report: Report

    @property
    def filename(self) -> str:
        return f"{self.header.id}.txt" if self.header else ""


def _clean(value: str) -> str:
    return unicodedata.normalize("NFC", value).replace("\n", " ").strip()


def convert(source: bytes | str) -> Converted:
    """Convert one source work. Nothing is written when the report has an error."""
    report = Report()
    if isinstance(source, bytes):
        try:
            text = source.decode("utf-8-sig")
        except UnicodeDecodeError:
            report.error(0, "The file is not valid UTF-8.")
            return Converted(None, None, report)
    else:
        text = source
    if "\r" in text:
        report.note(0, "The file had Windows or old Mac line ends. They were changed to plain line ends.")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    lines = text.split("\n")
    header, start = parse_header(lines, report)
    if header is None:
        return Converted(None, None, report)
    body, numbers = convert_body(lines[start:], start + 1, report)
    check_runs(body, numbers, report)
    if not body:
        report.error(0, "The work has no text after the header.")
    if not report.ok:
        return Converted(header, None, report)
    tags = list(header.tags) + [f"type:{header.type}"]
    front = ["---", f"TITL: {_clean(header.title)}"]
    if header.author:
        front.append(f"AUTH: {_clean(header.author)}")
    front += [f"GNRE: {';'.join(tags)}", f"LANG: {header.language}", "---"]
    for item in front:
        if "\x1e" in item or "\x0e" in item or "\x0f" in item:
            report.error(0, "The header holds a control character.")
    if not report.ok:
        return Converted(header, None, report)
    data = ("\n".join(front + body) + "\n").encode("utf-8")
    return Converted(header, data, report)
