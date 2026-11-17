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


def reading_copy(result: Converted) -> bytes | None:
    """A plain text copy for reading elsewhere: title, author, then the text with no header and no control codes.

    It is made from the reader file, so the two always hold the same words. Paragraphs are separated by a blank
    line; list items stay together."""
    if result.data is None or result.header is None:
        return None
    lines = result.data.decode("utf-8").split("\n")
    body = lines[lines.index("---", 1) + 1 :]
    if body and body[-1] == "":
        body.pop()
    out = [_clean(result.header.title)]
    if result.header.author:
        out.append(_clean(result.header.author))
    out.append("")
    previous_item = False
    for line in body:
        text = line.replace("\x1e", "").replace("\x0e", "").replace("\x0f", "")
        item = text.startswith("- ")
        if out[-1] != "" and not (item and previous_item):
            out.append("")
        out.append(text)
        previous_item = item
    return ("\n".join(out) + "\n").encode("utf-8")
