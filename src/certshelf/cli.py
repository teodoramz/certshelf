"""`python3 -m certshelf run …`: what the Action runs. It never fails the workflow; problems become warnings."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import __version__, credly, images
from .model import ExtrasError, order, parse_extras
from .readme import build_block, replace_block
from .tiles import render_tile, tile_files

STYLES = ("card", "retro")
COMMIT_MESSAGE = "Update certifications"
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")


def warn(message: str) -> None:
    print(f"::warning::certshelf: {message}", flush=True)


def _write_tiles(entries, folder: Path, root: Path, style: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    keep = set()
    for entry in entries:
        image = images.load_image(entry.image, root)
        if entry.image and not image:
            warn(f"could not load the image for {entry.name!r}; showing its initials instead")
        names = tile_files(entry, style)
        themes = ("dark", "light") if style == "card" else ("dark",)
        for name, theme in zip(names, themes):
            svg = render_tile(entry, image, style, theme)
            path = folder / name
            if not path.exists() or path.read_text(encoding="utf-8") != svg:
                path.write_text(svg, encoding="utf-8")
            keep.add(name)
    for old in folder.glob("*.svg"):
        if old.name not in keep:
            old.unlink()


def _commit(root: Path, paths: list[str]) -> None:
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout

    try:
        git("add", "--all", "--", *paths)
        if not git("status", "--porcelain", "--", *paths).strip():
            print("certshelf: nothing changed, no commit")
            return
        git("-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}", "commit", "-q", "-m", COMMIT_MESSAGE, "--", *paths)
        ref = os.environ.get("GITHUB_REF", "")
        git("push", "-q", "origin", f"HEAD:{ref}") if ref.startswith("refs/heads/") else git("push", "-q")
        print("certshelf: committed and pushed the updated certifications")
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        warn(f"could not commit the update ({detail.strip()}); does the workflow have `permissions: contents: write`?")


def _run(args) -> int:
    today = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    root = Path(args.root).resolve()
    style = args.style if args.style in STYLES else "card"
    if style != args.style:
        warn(f"unknown style {args.style!r}; use card or retro. Using card.")
    entries = []
    if args.credly:
        try:
            entries += credly.fetch_badges(args.credly, today)
        except credly.CredlyError as exc:
            warn(f"{exc}; leaving the current tiles as they are")
            return 0
    try:
        entries += parse_extras(args.extra or "", today)
    except ExtrasError as exc:
        warn(f"skipping the extra entries: {exc}")
    if not entries:
        warn("nothing to show; set `credly` or `extra`")
        return 0
    entries = order(entries)
    folder = args.folder.strip("/") or "certshelf"
    _write_tiles(entries, root / folder, root, style)
    readme = root / args.readme
    changed = [folder]
    if not readme.is_file():
        warn(f"{args.readme} not found; tiles were written to {folder}/")
    else:
        text = readme.read_text(encoding="utf-8")
        new = replace_block(text, build_block(entries, folder, style))
        if new is None:
            warn(f"add `<!-- certshelf:start -->` and `<!-- certshelf:end -->` to {args.readme} where the tiles go")
        else:
            if new != text:
                readme.write_text(new, encoding="utf-8")
            changed.append(args.readme)
    print(f"certshelf: {len(entries)} certifications drawn in {style} style")
    if args.commit.lower() == "true":
        _commit(root, changed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="certshelf", description="Certification tiles for a GitHub README.")
    parser.add_argument("--version", action="version", version=f"certshelf {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="fetch, draw, update the README and commit (what the Action runs)")
    run.add_argument("--credly", default="", help="Credly username (credly.com/users/<username>)")
    run.add_argument("--style", default="card", help="card or retro")
    run.add_argument("--extra", default="", help="extra entries, a small YAML-like list")
    run.add_argument("--readme", default="README.md")
    run.add_argument("--folder", default="certshelf")
    run.add_argument("--commit", default="false", help="true to commit and push changes")
    run.add_argument("--date", help="today as YYYY-MM-DD (default: today, UTC)")
    run.add_argument("--root", default=".", help="repository folder")
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:  # noqa: BLE001 - the Action must never break the workflow
        warn(f"unexpected error: {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
