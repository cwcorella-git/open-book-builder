"""The localhost site mockup: pages, links, downloads and the failure on a bad work."""
import importlib.util
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
site = importlib.util.module_from_spec(spec)
sys.modules["build_site"] = site
spec.loader.exec_module(site)

from open_book_builder.convert import convert, reading_copy  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    manifest = site.build(out)
    return out, manifest


def test_pages_and_downloads_exist(built):
    out, manifest = built
    for name in ("index.html", "guide.html", "card.html", "index.json"):
        assert (out / name).is_file(), name
    for wid in manifest["works"]:
        for part in (f"works/{wid}.html", f"downloads/{wid}.txt", f"downloads/{wid}.reading.txt"):
            assert (out / part).is_file(), part
    for cid, c in manifest["collections"].items():
        assert (out / "collections" / f"{cid}.html").is_file() and (out / c["file"]).is_file()


def test_every_local_link_resolves(built):
    out, _ = built
    checked = 0
    for html_file in out.rglob("*.html"):
        for href in re.findall(r'href="([^"]+)"', html_file.read_text(encoding="utf-8")):
            if re.match(r"^(https?:|mailto:|#)", href):
                continue
            target = (html_file.parent / href.split("#")[0]).resolve()
            assert target.exists(), f"{html_file.name} links to {href}"
            checked += 1
    assert checked > 20


def test_collection_zip_holds_the_converters_bytes_and_a_readme(built):
    out, manifest = built
    with zipfile.ZipFile(out / manifest["collections"]["starter-stories"]["file"]) as z:
        assert sorted(z.namelist()) == ["README", "lighthouse.txt", "the-long-afternoon.txt"]
        expected = convert((ROOT / "site" / "works" / "lighthouse.md").read_bytes()).data
        assert z.read("lighthouse.txt") == expected
        assert not any(n.endswith(".reading.txt") for n in z.namelist())


def test_reading_copy_download_matches_the_converter(built):
    out, _ = built
    source = convert((ROOT / "site" / "works" / "a-note-on-slow-reading.md").read_bytes())
    assert (out / "downloads" / "a-note-on-slow-reading.reading.txt").read_bytes() == reading_copy(source)


def test_manifest_hashes_match_files(built):
    out, manifest = built
    for entry in list(manifest["works"].values()) + list(manifest["collections"].values()):
        assert site.sha((out / entry["file"]).read_bytes()) == entry["sha256"]
    assert json.loads((out / "index.json").read_text()) == manifest


def test_build_is_repeatable(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    site.build(a)
    site.build(b)
    for path in sorted(a.rglob("*")):
        if path.is_file():
            assert path.read_bytes() == (b / path.relative_to(a)).read_bytes(), path


def work_tree(tmp_path, extra_work=None, collection=None):
    root = tmp_path / "site"
    shutil.copytree(ROOT / "site", root, ignore=shutil.ignore_patterns("_out"))
    if extra_work:
        (root / "works" / "bad.md").write_text(extra_work)
    if collection:
        (root / "collections" / "x.json").write_text(json.dumps(collection))
    return root


def test_a_rejected_work_stops_the_build(tmp_path):
    bad = "---\nid: bad\nversion: 1\ntitle: Bad\ntype: book\nlanguage: en\nrights: x\n---\n\n![pic](p.png)\n"
    root = work_tree(tmp_path, bad)
    with pytest.raises(site.BuildError, match="bad.md.*image"):
        site.build(tmp_path / "out", site=root)


def test_a_work_without_rights_is_refused(tmp_path):
    norights = "---\nid: bad\nversion: 1\ntitle: Bad\ntype: book\nlanguage: en\n---\n\ntext\n"
    root = work_tree(tmp_path, norights)
    with pytest.raises(site.BuildError, match="rights"):
        site.build(tmp_path / "out", site=root)


def test_a_collection_naming_an_unknown_work_fails(tmp_path):
    root = work_tree(tmp_path, collection={"id": "x", "title": "X", "description": "d", "works": ["ghost"]})
    with pytest.raises(site.BuildError, match="ghost"):
        site.build(tmp_path / "out", site=root)


def test_markdown_renderer_handles_the_guides_shapes():
    html = site.render_markdown("# T\n\n| a | b |\n|---|---|\n| 1 | **2** |\n\n- x\n- y\n\n```\n<RS>\n```\n")
    assert "<table>" in html and "<strong>2</strong>" in html and "<ul>" in html and "&lt;RS&gt;" in html
