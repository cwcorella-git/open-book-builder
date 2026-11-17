"""The body: a line-based pass over the Markdown subset the reader can show."""
from __future__ import annotations

import re

from .report import Report

RS, SI, SO = "\x1e", "\x0f", "\x0e"
PLAIN, ITALIC, BOLD, BOTH = 0, 1, 2, 3

# What one Shift In or Shift Out does to the style. Shift In goes plain, italic, bold, bold and italic.
# Shift Out goes bold and italic to bold, and bold or italic to plain (read from the libros source).
_SI_NEXT = {PLAIN: ITALIC, ITALIC: BOLD, BOLD: BOTH}
_SO_NEXT = {BOTH: BOLD, BOLD: PLAIN, ITALIC: PLAIN}


def _shortest_paths() -> dict[tuple[int, int], str]:
    paths = {}
    for start in (PLAIN, ITALIC, BOLD, BOTH):
        seen = {start: ""}
        queue = [start]
        while queue:
            state = queue.pop(0)
            for code, table in ((SI, _SI_NEXT), (SO, _SO_NEXT)):
                nxt = table.get(state)
                if nxt is not None and nxt not in seen:
                    seen[nxt] = seen[state] + code
                    queue.append(nxt)
        for end, codes in seen.items():
            paths[(start, end)] = codes
    return paths


PATHS = _shortest_paths()


def transition(old: int, new: int) -> str:
    """The control codes that move the reader from one style to another."""
    return PATHS[(old, new)]


LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
HTML_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(\s[^>]*)?/?>|<!--")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^\s{0,3}[-*+]\s+(.*)$")
RUN_LIMIT = 127


def _inline(text: str, line: int, report: Report, strip: bool = False) -> str:
    """Turn one run of inline Markdown into text with style codes. Reports what it cannot show."""
    if "![" in text:
        report.error(line, "An image. The first batch of readers shows text only.")
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    if "[^" in text:
        report.error(line, "A footnote. Move the note into the text.")
    if "`" in text:
        report.error(line, "Code. The reader shows ordinary text only.")
    if "$$" in text or "\\(" in text or "\\[" in text:
        report.error(line, "Math. The reader cannot draw it.")
    if HTML_RE.search(text):
        report.error(line, "Raw HTML. Write the text without tags.")
    text = LINK_RE.sub(lambda m: m.group(1), text)
    out: list[str] = []
    italic = bold = False
    state = PLAIN
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "\\*#-[]()_`":
            out.append(text[i + 1])
            i += 2
            continue
        if ch == "*":
            n = 1
            while i + n < len(text) and text[i + n] == "*" and n < 3:
                n += 1
            if n >= 2:
                bold = not bold
            if n in (1, 3):
                italic = not italic
            new = (ITALIC if italic else PLAIN) + (BOLD if bold else PLAIN)
            if not strip:
                out.append(transition(state, new))
            state = new
            i += n
            continue
        out.append(ch)
        i += 1
    if state != PLAIN:
        report.error(line, "Emphasis is opened with * and never closed on the same line.")
        if not strip:
            out.append(transition(state, PLAIN))
    return "".join(out)


def convert_body(lines: list[str], first_line: int, report: Report) -> tuple[list[str], list[int]]:
    """Device lines for the body and the source line each came from. `first_line` is the 1-based number of lines[0]."""
    out: list[str] = []
    numbers: list[int] = []
    paragraph: list[tuple[int, str]] = []
    in_fence = False

    def flush() -> None:
        if paragraph:
            number = paragraph[0][0]
            joined = " ".join(t.strip() for _, t in paragraph)
            out.append(_inline(joined, number, report))
            numbers.append(number)
            paragraph.clear()

    for offset, raw in enumerate(lines):
        number = first_line + offset
        if FENCE_RE.match(raw):
            flush()
            if not in_fence:
                report.error(number, "A code block. The reader shows ordinary text only.")
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        text = raw.rstrip()
        if not text.strip():
            flush()
            continue
        nxt = lines[offset + 1] if offset + 1 < len(lines) else ""
        if "|" in text and TABLE_SEP_RE.match(nxt):
            flush()
            report.error(number, "A table. The first batch of readers shows text only.")
            continue
        if TABLE_SEP_RE.match(text) and "|" in text:
            continue
        if re.match(r"^\s*\[\^[^\]]+\]:", text):
            flush()
            report.error(number, "A footnote. Move the note into the text.")
            continue
        heading = HEADING_RE.match(text)
        if heading:
            flush()
            level, title = len(heading.group(1)), heading.group(2)
            if level == 1:
                clean = _inline(title, number, report, strip=True)
                if len(clean.encode()) >= 100:
                    report.error(number, "A chapter title of 100 bytes or more. Shorten it.")
                out.append(RS + clean)
                numbers.append(number)
            else:
                clean = _inline(title, number, report, strip=True)
                out.append(SI + SI + clean + SO)
                numbers.append(number)
            continue
        item = LIST_RE.match(text)
        if item and not text.lstrip().startswith("**") and not re.match(r"^\s*\*[^\s*]", text):
            flush()
            out.append("- " + _inline(item.group(1), number, report))
            numbers.append(number)
            continue
        if text.lstrip().startswith(">"):
            text = text.lstrip()[1:].lstrip()
        paragraph.append((number, text))
    flush()
    return out, numbers


def check_runs(lines: list[str], numbers: list[int], report: Report) -> None:
    """Flag any run of 127 bytes or more without a space or newline in the device lines."""
    for text, number in zip(lines, numbers):
        for word in re.split(r"[ \t\x0e\x0f\x1e]", text):
            if len(word.encode()) >= RUN_LIMIT:
                report.error(number, f"A run of {len(word.encode())} bytes with no space. The reader cannot lay it out.")
