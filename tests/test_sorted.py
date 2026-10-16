import os
import shutil
import sys
from pathlib import Path

import pytest

# Ensure sorted script in dotfiles can be imported
sys.path.insert(0, str(Path(__file__).parent.parent / "dotfiles" / "bin" / ".local" / "bin"))

import importlib.machinery
import importlib.util

loader = importlib.machinery.SourceFileLoader(
    "sorted_module",
    str(Path(__file__).parent.parent / "dotfiles" / "bin" / ".local" / "bin" / "sorted"),
)
spec = importlib.util.spec_from_loader("sorted_module", loader)
assert spec is not None and spec.loader is not None
sorted_mod = importlib.util.module_from_spec(spec)
sys.modules["sorted_module"] = sorted_mod
spec.loader.exec_module(sorted_mod)


def test_split_filename_and_ext():
    assert sorted_mod.split_filename_and_ext("document.pdf") == ("document", ".pdf")
    assert sorted_mod.split_filename_and_ext("archive.tar.gz") == ("archive", ".tar.gz")
    assert sorted_mod.split_filename_and_ext("bundle.tar.xz") == ("bundle", ".tar.xz")
    assert sorted_mod.split_filename_and_ext("data.tbz2") == ("data", ".tbz2")
    assert sorted_mod.split_filename_and_ext("Makefile") == ("Makefile", "")
    assert sorted_mod.split_filename_and_ext("PHOTO.JPG") == ("PHOTO", ".JPG")


def test_is_ignored():
    # Hidden files
    assert sorted_mod.is_ignored(Path(".bashrc")) is True
    assert sorted_mod.is_ignored(Path(".DS_Store")) is True

    # In-progress / incomplete downloads
    assert sorted_mod.is_ignored(Path("ubuntu.iso.crdownload")) is True
    assert sorted_mod.is_ignored(Path("video.mp4.part")) is True
    assert sorted_mod.is_ignored(Path("song.mp3.download")) is True
    assert sorted_mod.is_ignored(Path("file.tmp")) is True
    assert sorted_mod.is_ignored(Path("package.torrent.part")) is True

    # Valid files
    assert sorted_mod.is_ignored(Path("ubuntu.iso")) is False
    assert sorted_mod.is_ignored(Path("video.mp4")) is False
    assert sorted_mod.is_ignored(Path("document.pdf")) is False


def test_classify_file():
    # Documents
    cat, is_home = sorted_mod.classify_file(Path("notes.txt"))
    assert (cat, is_home) == ("Documents", True)
    cat, is_home = sorted_mod.classify_file(Path("paper.pdf"))
    assert (cat, is_home) == ("Documents", True)

    # Pictures
    cat, is_home = sorted_mod.classify_file(Path("wallpaper.png"))
    assert (cat, is_home) == ("Pictures", True)
    cat, is_home = sorted_mod.classify_file(Path("photo.JPG"))
    assert (cat, is_home) == ("Pictures", True)

    # Music
    cat, is_home = sorted_mod.classify_file(Path("track01.flac"))
    assert (cat, is_home) == ("Music", True)

    # Movies
    cat, is_home = sorted_mod.classify_file(Path("film.mkv"))
    assert (cat, is_home) == ("Movies", True)

    # Downloads subcategories
    cat, is_home = sorted_mod.classify_file(Path("backup.tar.gz"))
    assert (cat, is_home) == ("Archives", False)

    cat, is_home = sorted_mod.classify_file(Path("app.AppImage"))
    assert (cat, is_home) == ("Software", False)

    cat, is_home = sorted_mod.classify_file(Path("script.py"))
    assert (cat, is_home) == ("Code", False)

    cat, is_home = sorted_mod.classify_file(Path("linux.torrent"))
    assert (cat, is_home) == ("Torrents", False)

    cat, is_home = sorted_mod.classify_file(Path("font.otf"))
    assert (cat, is_home) == ("Fonts", False)

    cat, is_home = sorted_mod.classify_file(Path("unknown.xyz123"))
    assert (cat, is_home) == ("Other", False)


def test_collision_free_path(tmp_path):
    target_dir = tmp_path / "docs"
    target_dir.mkdir()

    # Case 1: File doesn't exist
    p1 = sorted_mod.get_collision_free_path(target_dir, "test.txt")
    assert p1 == target_dir / "test.txt"

    # Case 2: File exists -> append (1)
    (target_dir / "test.txt").write_text("first")
    p2 = sorted_mod.get_collision_free_path(target_dir, "test.txt")
    assert p2 == target_dir / "test(1).txt"

    # Case 3: test(1).txt also exists -> append (2)
    (target_dir / "test(1).txt").write_text("second")
    p3 = sorted_mod.get_collision_free_path(target_dir, "test.txt")
    assert p3 == target_dir / "test(2).txt"

    # Case 4: Compound extension collision
    (target_dir / "archive.tar.gz").write_text("archive1")
    p_comp = sorted_mod.get_collision_free_path(target_dir, "archive.tar.gz")
    assert p_comp == target_dir / "archive(1).tar.gz"


def test_dry_run_does_not_modify_filesystem(tmp_path):
    home_dir = tmp_path / "home"
    downloads_dir = home_dir / "Downloads"
    downloads_dir.mkdir(parents=True)

    test_file = downloads_dir / "document.pdf"
    test_file.write_text("dry run content")

    count = sorted_mod.run_once(home_dir=home_dir, downloads_dir=downloads_dir, dry_run=True)
    assert count == 1

    # Verify original file is still in Downloads
    assert test_file.exists()
    # Verify Documents folder was not created
    assert not (home_dir / "Documents").exists()


def test_full_sorting_run(tmp_path):
    home_dir = tmp_path / "home"
    downloads_dir = home_dir / "Downloads"
    downloads_dir.mkdir(parents=True)

    # Populate downloads directory
    (downloads_dir / "doc.pdf").write_text("pdf content")
    (downloads_dir / "image.png").write_text("image content")
    (downloads_dir / "track.mp3").write_text("audio content")
    (downloads_dir / "clip.mp4").write_text("video content")
    (downloads_dir / "project.tar.gz").write_text("tarball content")
    (downloads_dir / "tool.deb").write_text("deb content")
    (downloads_dir / "main.py").write_text("code content")
    (downloads_dir / "seed.torrent").write_text("torrent content")
    (downloads_dir / "mystery.bin").write_text("binary content")
    (downloads_dir / "custom.xyz").write_text("other content")

    # Files that should be ignored
    (downloads_dir / "inprogress.mp4.crdownload").write_text("incomplete")
    (downloads_dir / ".hidden_file").write_text("hidden")
    sub_dir = downloads_dir / "ExistingSubdir"
    sub_dir.mkdir()
    (sub_dir / "nested.txt").write_text("nested")

    # Run sort
    count = sorted_mod.run_once(home_dir=home_dir, downloads_dir=downloads_dir, dry_run=False)
    assert count == 10

    # Assert Home categories
    assert (home_dir / "Documents" / "doc.pdf").read_text() == "pdf content"
    assert (home_dir / "Pictures" / "image.png").read_text() == "image content"
    assert (home_dir / "Music" / "track.mp3").read_text() == "audio content"
    assert (home_dir / "Movies" / "clip.mp4").read_text() == "video content"

    # Assert Downloads fallback categories
    assert (downloads_dir / "Archives" / "project.tar.gz").read_text() == "tarball content"
    assert (downloads_dir / "Software" / "tool.deb").read_text() == "deb content"
    assert (downloads_dir / "Software" / "mystery.bin").read_text() == "binary content"
    assert (downloads_dir / "Code" / "main.py").read_text() == "code content"
    assert (downloads_dir / "Torrents" / "seed.torrent").read_text() == "torrent content"
    assert (downloads_dir / "Other" / "custom.xyz").read_text() == "other content"

    # Assert ignored items are untouched
    assert (downloads_dir / "inprogress.mp4.crdownload").exists()
    assert (downloads_dir / ".hidden_file").exists()
    assert sub_dir.is_dir()
    assert (sub_dir / "nested.txt").exists()


def test_collision_in_actual_sorting(tmp_path):
    home_dir = tmp_path / "home"
    downloads_dir = home_dir / "Downloads"
    downloads_dir.mkdir(parents=True)

    # Pre-existing file in Documents
    docs_dir = home_dir / "Documents"
    docs_dir.mkdir(parents=True)
    (docs_dir / "report.pdf").write_text("existing report")

    # New file with identical name in Downloads
    (downloads_dir / "report.pdf").write_text("new report")

    count = sorted_mod.run_once(home_dir=home_dir, downloads_dir=downloads_dir)
    assert count == 1

    assert (docs_dir / "report.pdf").read_text() == "existing report"
    assert (docs_dir / "report(1).pdf").read_text() == "new report"
    assert not (downloads_dir / "report.pdf").exists()


def test_parse_args():
    args = sorted_mod.parse_args(["--once", "--verbose", "-n"])
    assert args.once is True
    assert args.watch is False
    assert args.verbose is True
    assert args.dry_run is True

    args_watch = sorted_mod.parse_args(["--watch", "--interval", "5.5"])
    assert args_watch.watch is True
    assert args_watch.interval == 5.5
