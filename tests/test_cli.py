import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

import certshelf.cli as cli
from certshelf.credly import CredlyError, parse_badges
from certshelf.model import Entry
from certshelf.readme import END, START, build_block, replace_block

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "credly-teodor.json").read_text())
EXTRA = """- name: CC Exam
  issuer: ISC2
  date: 2025-11-18
  status: Exam passed
  note: Certification/badge fee not paid
  link: certs/cc-exam-passed.png
"""
README = f"# Hi\n\n## Certifications\n{START}\nold\n{END}\n\nbye\n"


def one(key, link):
    return Entry(key, "A & B", "", None, link, "Active", "active", "", None, date(2026, 1, 1))


def test_block_card_and_retro():
    entries = [one("ab", "https://x.org/1"), one("cd", None)]
    assert build_block(entries, "certshelf", "card") == (
        '<p align="center">\n'
        '  <a href="https://x.org/1"><picture><source media="(prefers-color-scheme: dark)" '
        'srcset="certshelf/ab-dark.svg"><img src="certshelf/ab-light.svg" width="168" alt="A &amp; B"></picture></a>\n'
        '  <picture><source media="(prefers-color-scheme: dark)" srcset="certshelf/cd-dark.svg">'
        '<img src="certshelf/cd-light.svg" width="168" alt="A &amp; B"></picture>\n'
        "</p>")
    assert build_block(entries, "certshelf", "retro") == (
        '<p align="center">\n'
        '  <a href="https://x.org/1"><img src="certshelf/ab.svg" width="168" alt="A &amp; B"></a>\n'
        '  <img src="certshelf/cd.svg" width="168" alt="A &amp; B">\n'
        "</p>")


def test_replace_block():
    new = replace_block(README, "NEW")
    assert new == f"# Hi\n\n## Certifications\n{START}\nNEW\n{END}\n\nbye\n"
    assert replace_block(new, "NEW") == new
    assert replace_block("# no markers\n", "NEW") is None


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text(README)
    monkeypatch.setattr(cli.credly, "fetch_badges", lambda user, today: parse_badges([FIXTURE], today))
    monkeypatch.setattr(cli.images, "load_image", lambda ref, root: None)
    return tmp_path


def run(root, *extra_args, extra=EXTRA, credly="teodor-amzuloiu"):
    return cli.main(["run", "--credly", credly, "--extra", extra, "--root", str(root), "--commit", "false",
                     "--date", "2026-11-11", *extra_args])


def test_run_writes_tiles_and_readme(repo):
    assert run(repo) == 0
    files = sorted(p.name for p in (repo / "certshelf").iterdir())
    assert len(files) == 8 and all(f.endswith(("-dark.svg", "-light.svg")) for f in files)
    text = (repo / "README.md").read_text()
    names = [n for n in ("GIAC Advisory Board", "GIAC Penetration Tester (GPEN)", "CC Exam", "ISC2 Candidate")]
    positions = [text.index(f'alt="{n}"') for n in names]
    assert positions == sorted(positions)
    assert 'href="certs/cc-exam-passed.png"' in text
    assert text.startswith("# Hi\n\n## Certifications\n") and text.endswith("\n\nbye\n")


def test_retro_style(repo):
    assert run(repo, "--style", "retro") == 0
    assert len(list((repo / "certshelf").iterdir())) == 4


def test_stale_tiles_removed(repo):
    folder = repo / "certshelf"
    folder.mkdir()
    (folder / "old-dark.svg").write_text("<svg/>")
    (folder / "keep.txt").write_text("mine")
    run(repo)
    assert not (folder / "old-dark.svg").exists()
    assert (folder / "keep.txt").exists()


def test_missing_markers_warn(repo, capsys):
    (repo / "README.md").write_text("# no markers\n")
    assert run(repo) == 0
    assert (repo / "README.md").read_text() == "# no markers\n"
    assert len(list((repo / "certshelf").iterdir())) == 8
    assert "::warning::certshelf:" in capsys.readouterr().out


def test_bad_extras_warn_and_skip(repo, capsys):
    assert run(repo, extra="- issuer: nobody\n") == 0
    assert len(list((repo / "certshelf").iterdir())) == 6
    assert "line 1" in capsys.readouterr().out


def test_run_credly_failure_keeps_files(repo, monkeypatch, capsys):
    def fail(user, today):
        raise CredlyError("Credly answered HTTP 404")

    monkeypatch.setattr(cli.credly, "fetch_badges", fail)
    assert run(repo) == 0
    assert (repo / "README.md").read_text() == README
    assert not (repo / "certshelf").exists()
    assert "HTTP 404" in capsys.readouterr().out


def test_unknown_style_falls_back_to_card(repo, capsys):
    assert run(repo, "--style", "neon") == 0
    assert len(list((repo / "certshelf").iterdir())) == 8
    assert "::warning::" in capsys.readouterr().out


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_commit_only_when_changed(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.name", "t")
    git(work, "config", "user.email", "t@example.org")
    (work / "README.md").write_text(README)
    git(work, "add", "README.md")
    git(work, "commit", "-qm", "start")
    git(work, "push", "-q", "origin", "HEAD:main")
    monkeypatch.setattr(cli.credly, "fetch_badges", lambda user, today: parse_badges([FIXTURE], today))
    monkeypatch.setattr(cli.images, "load_image", lambda ref, root: None)
    args = ["run", "--credly", "u", "--extra", EXTRA, "--root", str(work), "--commit", "true", "--date", "2026-11-11"]
    assert cli.main(args) == 0
    assert cli.main(args) == 0
    log = git(remote, "log", "--format=%s|%b", "main").splitlines()
    assert log == ["Update certifications|", "start|"]
