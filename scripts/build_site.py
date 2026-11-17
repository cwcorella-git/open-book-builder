#!/usr/bin/env python3
"""Build the localhost mockup of the collections site into site/_out/ (a static site).

  uv run python scripts/build_site.py                 # build
  python3 -m http.server -d site/_out --bind 127.0.0.1 8000

Every download is made by the converter, so a work with a rejected line stops the build and prints its report.
This is a mockup to look at, not the public site: no accounts, no ordering, no scripts.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from open_book_builder.convert import convert, reading_copy  # noqa: E402

SITE = ROOT / "site"
DOCS = ROOT / "docs"
ZIP_DATE = (2026, 1, 1, 0, 0, 0)  # fixed, so a rebuild gives the same bytes


class BuildError(Exception):
    pass


# -- a small Markdown renderer for the site's own pages -------------------------------------------------------------

def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", text)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)


def render_markdown(source: str, link_map: dict[str, str] | None = None) -> str:
    """Headings, paragraphs, lists, tables, fenced code and inline code, bold, italic and links."""
    out: list[str] = []
    lines = source.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            i += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            cells = lambda row: [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i]:
                rows.append(cells(lines[i]))
                i += 1
            table = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            table += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(table + "</tbody></table>")
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>")
            continue
        if not line.strip():
            i += 1
            continue
        paragraph = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|```|\s*([-*]|\d+\.)\s)", lines[i]):
            paragraph.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(paragraph))}</p>")
    return "\n".join(out)


# -- page shell ---------------------------------------------------------------------------------------------------

STYLE = """
:root{--bg:#fbfaf7;--fg:#1f1d1a;--muted:#6b665e;--line:#d9d4ca;--accent:#8a3b12;--code:#efece5}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--fg:#ece8e0;--muted:#a39d92;--line:#3a3732;--accent:#e3a06f;--code:#24221f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 Georgia,'Times New Roman',serif}
header,main,footer{max-width:46rem;margin:0 auto;padding:0 16px}
header{padding-top:20px;padding-bottom:12px;border-bottom:1px solid var(--line)}
header a.name{font-weight:bold;color:var(--fg);text-decoration:none;font-size:1.15rem}
nav{margin-top:6px;display:flex;gap:16px;flex-wrap:wrap;font-family:system-ui,sans-serif;font-size:.95rem}
a{color:var(--accent)}h1,h2,h3{line-height:1.25}h1{font-size:1.8rem}main{padding-top:12px;padding-bottom:40px}
code{background:var(--code);padding:0 .25em;border-radius:3px;font-size:.92em}
pre{background:var(--code);padding:12px;overflow-x:auto;border-radius:4px}pre code{padding:0;background:none}
table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.meta{color:var(--muted);font-family:system-ui,sans-serif;font-size:.9rem}
.card{border:1px solid var(--line);border-radius:6px;padding:12px 16px;margin:12px 0}
.notice{border-left:4px solid var(--accent);padding:4px 12px;margin:16px 0;color:var(--muted);font-family:system-ui,sans-serif;font-size:.9rem}
footer{border-top:1px solid var(--line);padding-top:12px;padding-bottom:24px;color:var(--muted);font-family:system-ui,sans-serif;font-size:.85rem}
"""


def page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>
<header><a class="name" href="{up}index.html">Open Book collections</a>
<nav><a href="{up}index.html">Collections</a><a href="{up}guide.html">Author's guide</a><a href="{up}card.html">Preparing a card</a></nav></header>
<main>{body}</main>
<footer>A localhost mockup. Nothing here is published, and the files have not been loaded on a reader yet.</footer>
</body></html>
"""


# -- the build ----------------------------------------------------------------------------------------------------

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def kib(n: int) -> str:
    return f"{n / 1024:.1f} KiB"


def make_zip(path: Path, files: dict[str, bytes]) -> bytes:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    return path.read_bytes()


def load_works(works_dir: Path) -> dict:
    works = {}
    problems = []
    for path in sorted(works_dir.glob("*.md")):
        result = convert(path.read_bytes())
        for item in result.report.items:
            if item.level == "error":
                problems.append(f"{path.name}: {item}")
        if result.data is None:
            continue
        if path.stem != result.header.id:
            problems.append(f"{path.name}: the file name must match the id '{result.header.id}'.")
        if not result.header.rights:
            problems.append(f"{path.name}: a work without rights text is refused.")
        works[result.header.id] = {"header": result.header, "data": result.data, "plain": reading_copy(result)}
    if problems:
        raise BuildError("\n".join(problems))
    return works


def load_collections(collections_dir: Path, works: dict) -> list[dict]:
    collections = []
    problems = []
    for path in sorted(collections_dir.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        for key in ("id", "title", "description", "works"):
            if key not in c:
                problems.append(f"{path.name}: missing '{key}'.")
        for w in c.get("works", []):
            if w not in works:
                problems.append(f"{path.name}: unknown work '{w}'.")
        collections.append(c)
    if problems:
        raise BuildError("\n".join(problems))
    return collections


def build(out: Path, site: Path = SITE, docs: Path = DOCS) -> dict:
    works = load_works(site / "works")
    collections = load_collections(site / "collections", works)
    if out.exists():
        shutil.rmtree(out)
    for sub in ("works", "collections", "downloads"):
        (out / sub).mkdir(parents=True)
    manifest: dict = {"works": {}, "collections": {}}

    for wid, w in works.items():
        h = w["header"]
        (out / "downloads" / f"{wid}.txt").write_bytes(w["data"])
        (out / "downloads" / f"{wid}.reading.txt").write_bytes(w["plain"])
        manifest["works"][wid] = {"version": h.version, "file": f"downloads/{wid}.txt", "sha256": sha(w["data"]),
                                  "bytes": len(w["data"])}
        in_collections = [c for c in collections if wid in c["works"]]
        body = f"<h1>{html.escape(h.title)}</h1>\n<p class=\"meta\">"
        parts = [h.type.capitalize()]
        if h.author:
            parts.append("by " + html.escape(h.author))
        parts.append(f"version {h.version}")
        parts.append(f"language {html.escape(h.language)}")
        body += " · ".join(parts) + "</p>\n"
        if h.tags:
            body += f"<p class=\"meta\">Tags: {html.escape(', '.join(h.tags))}</p>\n"
        body += f"<p class=\"meta\">Rights: {html.escape(h.rights)}</p>\n"
        body += (f"<h2>Downloads</h2><ul><li><a href=\"../downloads/{wid}.txt\">{wid}.txt</a> for the reader "
                 f"({kib(len(w['data']))}). Copy it to the top folder of the card.</li>"
                 f"<li><a href=\"../downloads/{wid}.reading.txt\">{wid}.reading.txt</a>, plain text for reading on "
                 f"another device. Do not put this one on the card.</li></ul>\n")
        if in_collections:
            body += "<h2>In these collections</h2><ul>" + "".join(
                f"<li><a href=\"../collections/{c['id']}.html\">{html.escape(c['title'])}</a></li>" for c in in_collections
            ) + "</ul>"
        (out / "works" / f"{wid}.html").write_text(page(h.title, body, 1), encoding="utf-8")

    for c in collections:
        cid = c["id"]
        files = {f"{w}.txt": works[w]["data"] for w in c["works"]}
        # Named README with no extension, so the reader never lists it as a book and "copy every .txt file" is true.
        readme = (f"{c['title']}\n\nCopy every .txt file in this folder to the top folder of the reader's microSD card, "
                  f"next to babel.bin. Do not put them in a folder. This file (README) is not a book: leave it behind.\n\n"
                  f"If you already have an older copy of a work on the card, delete its .pag file (same name) first on a "
                  f"stock reader.\n").encode()
        zipped = make_zip(out / "downloads" / f"{cid}.zip", {**files, "README": readme})
        total = sum(len(d) for d in files.values())
        manifest["collections"][cid] = {"file": f"downloads/{cid}.zip", "sha256": sha(zipped), "works": c["works"]}
        body = f"<h1>{html.escape(c['title'])}</h1>\n<p>{html.escape(c['description'])}</p>\n"
        body += (f"<p class=\"meta\">{len(c['works'])} work{'s' if len(c['works']) != 1 else ''}, "
                 f"{kib(total)} for the reader.</p>\n")
        body += f"<p><a href=\"../downloads/{cid}.zip\">Download this collection</a> ({kib(len(zipped))} zip)</p>\n<h2>Works</h2>\n"
        for wid in c["works"]:
            h = works[wid]["header"]
            body += (f"<div class=\"card\"><a href=\"../works/{wid}.html\"><strong>{html.escape(h.title)}</strong></a>"
                     f"<div class=\"meta\">{h.type.capitalize()}{' · ' + html.escape(h.author) if h.author else ''}</div></div>\n")
        (out / "collections" / f"{cid}.html").write_text(page(c["title"], body, 1), encoding="utf-8")

    body = ("<h1>Open Book collections</h1>\n<p>Texts prepared for the Open Book reader. Pick the collections you want "
            "on your card, or download single works to add later.</p>\n"
            "<div class=\"notice\">This is a mockup that runs on this computer only. The sample works were written for it.</div>\n"
            "<h2>Collections</h2>\n")
    for c in collections:
        body += (f"<div class=\"card\"><a href=\"collections/{c['id']}.html\"><strong>{html.escape(c['title'])}</strong></a>"
                 f"<div>{html.escape(c['description'])}</div>"
                 f"<div class=\"meta\">{len(c['works'])} work{'s' if len(c['works']) != 1 else ''}</div></div>\n")
    (out / "index.html").write_text(page("Open Book collections", body), encoding="utf-8")

    guide = (docs / "author-guide.md").read_text(encoding="utf-8")
    (out / "guide.html").write_text(page("Author's guide", render_markdown(guide)), encoding="utf-8")
    start = guide.index("## Trying a file on a reader")
    end = guide.index("\n## ", start + 5)
    card_body = ("<h1>Preparing a card</h1>\n<p>Format the microSD card as FAT32 with your disk tool first. "
                 "The card tool does not format.</p>\n" + render_markdown(guide[start:end]))
    (out / "card.html").write_text(page("Preparing a card", card_body), encoding="utf-8")

    (out / "index.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, default=SITE / "_out")
    args = parser.parse_args(argv)
    try:
        manifest = build(args.output)
    except BuildError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Built {len(manifest['works'])} works and {len(manifest['collections'])} collections into {args.output}.")
    print(f"Serve it with: python3 -m http.server -d {args.output} --bind 127.0.0.1 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
