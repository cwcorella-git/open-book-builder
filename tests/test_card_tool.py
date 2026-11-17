"""The card tool, against a temp folder standing in for the card. No real card has been used."""
import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("prepare_card", Path(__file__).parent.parent / "scripts" / "prepare_card.py")
card_tool = importlib.util.module_from_spec(spec)
sys.modules["prepare_card"] = card_tool
spec.loader.exec_module(card_tool)

MOUNTINFO = (
    "29 1 8:2 / / rw,relatime shared:1 - ext4 /dev/sda2 rw\n"
    "40 29 8:17 / /media/user/CARD rw,relatime shared:2 - vfat /dev/sdb1 rw\n"
    "41 29 179:1 / /media/user/SDBUILTIN rw - vfat /dev/mmcblk0p1 rw\n"
)


def test_parse_mountinfo_and_block_names():
    mounts = card_tool.parse_mountinfo(MOUNTINFO)
    assert mounts["/media/user/CARD"] == "/dev/sdb1"
    assert card_tool.block_name("/dev/sdb1") == "sdb"
    assert card_tool.block_name("/dev/mmcblk0p1") == "mmcblk0"
    assert card_tool.block_name("/dev/nvme0n1p2") == "nvme0n1"


def test_a_plain_folder_is_not_a_card(tmp_path):
    problems = card_tool.check_card(tmp_path, MOUNTINFO)
    assert problems and "not the top of a mounted card" in problems[0]


def test_missing_path(tmp_path):
    assert "does not exist" in card_tool.check_card(tmp_path / "nope", MOUNTINFO)[0]


def fake_mount(tmp_path, monkeypatch, removable):
    card = tmp_path / "CARD"
    card.mkdir()
    info = f"40 29 8:17 / {card} rw - vfat /dev/sdb1 rw\n"
    sys_root = tmp_path / "sys"
    (sys_root / "block" / "sdb").mkdir(parents=True)
    if removable is not None:
        (sys_root / "block" / "sdb" / "removable").write_text(f"{removable}\n")
    return card, info, sys_root


@pytest.mark.parametrize("flag,refused", [(1, False), (0, True), (None, True)])
def test_removable_check(tmp_path, monkeypatch, flag, refused):
    card, info, sys_root = fake_mount(tmp_path, monkeypatch, flag)
    problems = card_tool.check_card(card, info, sys_root)
    assert bool(problems) is refused
    if refused:
        assert "--allow-fixed" in problems[0]
        assert card_tool.check_card(card, info, sys_root, allow_fixed=True) == []


def test_dry_run_writes_nothing(tmp_path):
    result = card_tool.prepare(tmp_path, {"a.txt": b"hello"}, write=False)
    assert result.actions == ["Copy a.txt (5 bytes)."] and not result.problems
    assert not (tmp_path / "a.txt").exists()


def test_copy_and_verify(tmp_path):
    result = card_tool.prepare(tmp_path, {"a.txt": b"hello", "babel.bin": b"\x00\x01"}, write=True)
    assert not result.problems
    assert (tmp_path / "a.txt").read_bytes() == b"hello" and (tmp_path / "babel.bin").read_bytes() == b"\x00\x01"


def test_identical_file_is_skipped(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"hello")
    result = card_tool.prepare(tmp_path, {"a.txt": b"hello"}, write=True)
    assert result.actions == [] and "already on the card" in result.notes[0]


def test_changed_work_loses_its_page_map_and_keeps_progress(tmp_path):
    for name in ("a.txt", "a.pag", "a.obp"):
        (tmp_path / name).write_bytes(b"old")
    result = card_tool.prepare(tmp_path, {"a.txt": b"new text"}, write=True)
    assert not (tmp_path / "a.pag").exists() and (tmp_path / "a.obp").exists()
    assert (tmp_path / "a.txt").read_bytes() == b"new text"
    assert any("Delete a.pag" in a for a in result.actions) and any("a.obp was kept" in n for n in result.notes)


def test_unrecognized_files_refuse_the_copy(tmp_path):
    (tmp_path / "holiday.jpg").write_bytes(b"x")
    (tmp_path / "System Volume Information").mkdir()
    result = card_tool.prepare(tmp_path, {"a.txt": b"hi"}, write=True)
    assert "holiday.jpg" in result.problems[0] and not (tmp_path / "a.txt").exists()


def test_reader_files_are_recognized(tmp_path):
    for name in ("_LIBRARY", "_STATE", "babel.bin", "x.pag", "x.obp", "x.txt", ".Trashes"):
        (tmp_path / name).write_bytes(b"x")
    assert card_tool.unrecognized(tmp_path) == []


@pytest.mark.parametrize("name", ["a" * 130 + ".txt", ".hidden.txt", "dir/a.txt"])
def test_bad_names_refused(tmp_path, name):
    result = card_tool.prepare(tmp_path, {name: b"x"}, write=True)
    assert result.problems and not any(tmp_path.iterdir())


def test_not_enough_space_refused(tmp_path):
    result = card_tool.prepare(tmp_path, {"a.txt": b"x" * 100}, write=True, free_bytes=1000)
    assert "free" in result.problems[0] and not (tmp_path / "a.txt").exists()


def test_readback_mismatch_is_reported(tmp_path, monkeypatch):
    real = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: real(self, data[:-1]))
    result = card_tool.prepare(tmp_path, {"a.txt": b"hello"}, write=True)
    assert "reads back differently" in result.problems[0]


def test_load_works_from_folder_zip_and_selection(tmp_path):
    (tmp_path / "one.txt").write_bytes(b"1")
    with zipfile.ZipFile(tmp_path / "pack.zip", "w") as z:
        z.writestr("two.txt", b"2")
        z.writestr("nested/three.txt", b"3")
        z.writestr("README.txt", b"r")
    works, problems = card_tool.load_works(tmp_path, None)
    assert set(works) == {"one.txt", "two.txt"} and not problems  # README.txt is an instruction file, not a book
    works, problems = card_tool.load_works(tmp_path, {"two", "ghost"})
    assert set(works) == {"two.txt"} and "ghost" in problems[0]


def test_reading_copies_are_never_copied_to_a_card(tmp_path):
    (tmp_path / "one.txt").write_bytes(b"1")
    (tmp_path / "one.reading.txt").write_bytes(b"plain")
    with zipfile.ZipFile(tmp_path / "pack.zip", "w") as z:
        z.writestr("two.txt", b"2")
        z.writestr("two.reading.txt", b"plain")
    works, _ = card_tool.load_works(tmp_path, None)
    assert set(works) == {"one.txt", "two.txt"}


# -- the site manifest ------------------------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
bspec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(bspec)
sys.modules["build_site"] = build_site
bspec.loader.exec_module(build_site)


@pytest.fixture()
def site(tmp_path):
    out = tmp_path / "site"
    build_site.build(out)
    return out


def test_readme_txt_is_never_a_book_even_loose_in_a_folder(tmp_path):
    (tmp_path / "README.txt").write_bytes(b"read me")
    (tmp_path / "a.txt").write_bytes(b"a")
    works, _ = card_tool.load_works(tmp_path, None)
    assert set(works) == {"a.txt"}


def test_a_site_collection_yields_exactly_its_works(site):
    files, problems = card_tool.resolve_site(site, ["starter-stories"])
    assert not problems and set(files) == {"lighthouse.txt", "the-long-afternoon.txt"}
    assert files["lighthouse.txt"] == (site / "downloads" / "lighthouse.txt").read_bytes()
    assert not any("README" in name for name in files)


def test_two_collections_merge(site):
    files, problems = card_tool.resolve_site(site, ["starter-stories", "short-essays"])
    assert not problems and len(files) == 3


def test_a_work_in_two_collections_is_copied_once(tmp_path):
    import json, shutil

    root = tmp_path / "src"
    shutil.copytree(ROOT / "site", root, ignore=shutil.ignore_patterns("_out"))
    (root / "collections" / "again.json").write_text(
        json.dumps({"id": "again", "title": "Again", "description": "d", "works": ["lighthouse"]}))
    out = tmp_path / "out"
    build_site.build(out, site=root)
    files, problems = card_tool.resolve_site(out, ["starter-stories", "again"])
    assert not problems and set(files) == {"lighthouse.txt", "the-long-afternoon.txt"}


def test_a_tampered_package_is_refused(site):
    zip_path = site / "downloads" / "starter-stories.zip"
    zip_path.write_bytes(zip_path.read_bytes() + b"x")
    files, problems = card_tool.resolve_site(site, ["starter-stories"])
    assert not files and "stale or damaged" in problems[0]


def test_a_tampered_work_inside_a_valid_hash_is_refused(site):
    import hashlib, json

    # swap a work for different bytes and fix the zip hash, so only the per-work hash can catch it
    zip_path = site / "downloads" / "short-essays.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("a-note-on-slow-reading.txt", b"changed")
    manifest = json.loads((site / "index.json").read_text())
    manifest["collections"]["short-essays"]["sha256"] = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (site / "index.json").write_text(json.dumps(manifest))
    files, problems = card_tool.resolve_site(site, ["short-essays"])
    assert not files and "a-note-on-slow-reading.txt" in problems[0]


def test_unknown_collection_names_the_available_ones(site):
    files, problems = card_tool.resolve_site(site, ["nope"])
    assert "short-essays" in problems[0] and "starter-stories" in problems[0] and not files


def test_a_site_without_a_manifest_is_refused(tmp_path):
    files, problems = card_tool.resolve_site(tmp_path, ["x"])
    assert not files and "index.json" in problems[0]


def test_argument_rules(tmp_path):
    card = str(tmp_path)
    for bad in ([card], [card, "--works", card, "--site", card, "--collection", "x"], [card, "--site", card],
                [card, "--works", card, "--collection", "x"]):
        with pytest.raises(SystemExit):
            card_tool.parse_args(bad)
    assert card_tool.parse_args([card, "--site", card, "--collection", "a", "--collection", "b"]).collection == ["a", "b"]


def test_gather_reads_collection_ids_from_a_selection_file_and_adds_babel(site, tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text("# order 1042\nstarter-stories\n\nshort-essays\n")
    babel = tmp_path / "babel.bin"
    babel.write_bytes(b"\x00\x01")
    args = card_tool.parse_args([str(tmp_path), "--site", str(site), "--select", str(ids), "--babel", str(babel)])
    files, problems = card_tool.gather(args)
    assert not problems and set(files) == {"lighthouse.txt", "the-long-afternoon.txt", "a-note-on-slow-reading.txt", "babel.bin"}
