#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026-present David A. Greene <dag@obbligato.org>

# SPDX-License-Identifier: AGPL-3.0-or-later

# Copyright 2026 David A. Greene

# This file is part of git-project

# git-project is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

"""Write the docs/changelog.rst section for a release from the fragments
in changelog.d.

Usage: ./changelog.py --version X.Y.Z [--stdout]

Each fragment is one entry, in a file named ``<slug>.<category>.rst``.
The slug is lower case letters, digits and hyphens, starting with a
letter or digit. The category is ``added``, ``changed``, ``deprecated``,
``removed``, ``fixed`` or ``security``, and README.rst is not a
fragment. Each entry becomes one bullet. Its line breaks are kept, its
lines are indented under the bullet, and blank lines before and after it
are dropped.

A fragment is plain docutils RST, with no Sphinx roles, because
git-project's newest section becomes its PyPI description, which plain
docutils renders. A link takes the anonymous inline form ```text <URL>`__``.

The section goes below the empty ``Unreleased`` section, headed
```X.Y.Z`_ - DATE``. DATE is today, or the UTC date of
``SOURCE_DATE_EPOCH`` when that is set. Its subsections follow Keep a
Changelog order, and an empty one is left out. Within each, the bullets
are sorted by slug, comparing the numbers in a slug as numbers. The
``X.Y.Z`` link target goes below the ``Unreleased`` one, which then
compares from ``vX.Y.Z``. Existing entries are not touched. It then runs
``git rm`` on the fragments, so the changelog and their removal form one
change to review. Edit the result, land the change on the main branch
and tag that commit ``vX.Y.Z``.

When docutils is importable, it parses each bullet as a document of its
own, so an unknown role or a reference to a target the bullet does not
define is refused. It warns when docutils is not importable, so the
bullets go unchecked. It refuses, and changes nothing, when:

- the version is not ``X.Y.Z`` with no leading zeros, or its tag
  ``vX.Y.Z`` exists
- ``SOURCE_DATE_EPOCH`` is set and is not only digits
- a ``vN.N.N`` tag is merged into HEAD and the version is not greater
  than the highest one. Pre-release tags such as ``v1.2.0rc1`` do not
  count.
- changelog.d holds no fragment
- a file in changelog.d other than README.rst is not a regular file,
  does not match the name, or has an unknown category
- a fragment is empty or is not UTF-8, or its first line starts with a
  ``-``, ``*`` or ``+`` bullet, which would nest a list
- docutils reports a warning or an error in a bullet
- a fragment is untracked or has uncommitted changes. ``git rm`` would
  lose it, or the entry would not be what landed.
- the file does not exist, is untracked or has uncommitted changes
- the file has no ``Unreleased`` heading or more than one, or no
  ``.. _Unreleased:`` compare target or more than one
- ``Unreleased`` has entries of its own. They would be lost or
  duplicated.
- a link target comes before the end of the ``Unreleased`` section
- the file already has an ``X.Y.Z`` link target
- docutils reports a warning or an error in the updated file, as when
  two entries define the same target name

A refusal about fragments lists every file at fault. With ``--stdout``
it prints the section, removes nothing, and skips the check that the
fragments are tracked and clean, and the checks on the file, the last
six above. The others still apply.

When ``git rm`` fails after the file is written, it prints the commands
that finish the release or undo it.
"""

# The file has no per-repository constants, so git-project and
# git-project-core-plugins carry the same copy. The URL comes from the
# file's own Unreleased link target.

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILE = Path("docs") / "changelog.rst"
FRAGMENTS = "changelog.d"
README = "README.rst"
# Keep a Changelog order, by the name a fragment's file uses.
CATEGORIES = {
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "removed": "Removed",
    "fixed": "Fixed",
    "security": "Security",
}

FRAGMENT = re.compile(r"([a-z0-9][a-z0-9-]*)\.([^.]+)\.rst")
PART = "(0|[1-9][0-9]*)"
VERSION = re.compile(rf"{PART}\.{PART}\.{PART}")
TAG = re.compile(r"v([0-9]+)\.([0-9]+)\.([0-9]+)")
RELEASE = re.compile(r"^`[0-9]+\.[0-9]+\.[0-9]+`_ - ", re.MULTILINE)
UNRELEASED = re.compile(r"^`Unreleased`_\n([^\w\s])\1*\n", re.MULTILINE)
UNRELEASED_TARGET = re.compile(
    r"^\.\. _Unreleased: (\S+)/compare/(\S+)\.\.\.HEAD\n", re.MULTILINE
)
ANY_UNRELEASED_TARGET = re.compile(r"^\.\. _Unreleased:", re.MULTILINE)
LINK_TARGET = re.compile(r"^\.\. _", re.MULTILINE)
SUBSECTION = re.compile(
    r"^(?:Added|Changed|Deprecated|Removed|Fixed|Security)\n([^\w\s])\1*$",
    re.MULTILINE,
)


class RefusalError(Exception):
    def __init__(self, message: str, listing: str = "") -> None:
        super().__init__(message)
        self.listing = listing


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RefusalError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def succeeds(*args: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, check=False
    )
    return result.returncode == 0


def warn(message: str) -> None:
    print(f"changelog.py: warning: {message}", file=sys.stderr)


def numbers(match: re.Match[str]) -> tuple[int, ...]:
    return tuple(int(n) for n in match.groups())


def newest_tag() -> re.Match[str] | None:
    matches = [
        TAG.fullmatch(t) for t in git("tag", "--merged", "HEAD").split()
    ]
    tags = [m for m in matches if m is not None]
    if not tags:
        return None
    return max(tags, key=numbers)


def rst_checker() -> Callable[[str], list[str]] | None:
    """Return a function that lists what docutils reports in an entry,
    or None when docutils is not importable.

    """
    try:
        from docutils import frontend
        from docutils.parsers.rst import Parser
        from docutils.readers.standalone import Reader
        from docutils.utils import new_document
    except ImportError:
        return None

    if hasattr(frontend, "get_default_settings"):
        settings = frontend.get_default_settings(Parser, Reader)
    else:
        # Older docutils, as a distribution's python3 may carry.
        option_parser = frontend.OptionParser(components=(Parser, Reader))
        settings = option_parser.get_default_values()
    # Collect the messages through the observer, not on stderr.
    settings.report_level = 5
    settings.halt_level = 5

    def problems(text: str) -> list[str]:
        document = new_document("<entry>", settings)
        messages: list = []
        document.reporter.attach_observer(messages.append)
        parser = Parser()
        parser.parse(text, document)
        # The transforms report an unknown target, which the entry must
        # define itself because the PyPI description is rendered alone.
        document.transformer.populate_from_components(
            (Reader(parser=parser), parser)
        )
        document.transformer.apply_transforms()
        return [
            (
                f"line {m['line']}: {m.children[0].astext()}"
                if m.get("line")
                else m.children[0].astext()
            )
            for m in messages
            if m["level"] >= 2
        ]

    return problems


def bullet(text: str) -> str:
    """Return TEXT as one bullet, or "" when it has no text."""
    lines = [line.rstrip() for line in textwrap.dedent(text).splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return ""
    rest = [f"  {line}" if line else "" for line in lines[1:]]
    return "\n".join([f"- {lines[0]}", *rest])


def unclean() -> list[str]:
    """Return a problem for each fragment that git does not have as it
    is on disk, deleted ones included.

    """
    output = git(
        "status",
        "--porcelain",
        "-z",
        "--no-renames",
        "--untracked-files=all",
        "--ignored",
        "--",
        FRAGMENTS,
    )
    problems = []
    for record in output.split("\0"):
        code, path = record[:2], record[3:]
        if not record or path == f"{FRAGMENTS}/{README}":
            continue
        if code in ("??", "!!"):
            problems.append(f"{path}: it is untracked")
        else:
            problems.append(f"{path}: it has uncommitted changes")
    return problems


def natural(path: Path) -> tuple[list[str | int], str]:
    """Return a sort key for PATH's slug that compares its numbers as
    numbers.

    """
    parts = re.split(r"([0-9]+)", path.name.split(".")[0])
    return [int(p) if p.isdigit() else p for p in parts], path.name


def fragments(
    clean: bool, check: Callable[[str], list[str]] | None
) -> tuple[dict[str, list[str]], list[str]]:
    """Return the bullets by subsection and the fragments' paths. CHECK
    lists an entry's RST problems, and None skips it. With CLEAN, also
    refuse a fragment that is untracked or changed.

    """
    directory = ROOT / FRAGMENTS
    found: dict[str, list[str]] = {c: [] for c in CATEGORIES.values()}
    paths: list[str] = []
    problems: list[str] = []
    # Within a subsection the files share a suffix, so the slug orders
    # them, and "x-2" sorts before "x-10".
    entries = sorted(
        directory.iterdir() if directory.is_dir() else [], key=natural
    )
    for entry in entries:
        if entry.name == README:
            continue
        path = f"{FRAGMENTS}/{entry.name}"
        match = FRAGMENT.fullmatch(entry.name)
        if match is None:
            problems.append(f"{path}: the name is not <slug>.<category>.rst")
            continue
        name = CATEGORIES.get(match.group(2))
        if name is None:
            problems.append(
                f"{path}: {match.group(2)} is not one of "
                f"{', '.join(CATEGORIES)}"
            )
            continue
        if entry.is_symlink() or not entry.is_file():
            problems.append(f"{path}: it is not a regular file")
            continue
        try:
            # An editor's byte order mark would land mid-file.
            item = bullet(entry.read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError:
            problems.append(f"{path}: it is not UTF-8")
            continue
        if not item:
            problems.append(f"{path}: it is empty")
            continue
        if item.startswith(("- - ", "- * ", "- + ")):
            problems.append(f"{path}: it starts with a bullet of its own")
            continue
        rst = check(item) if check else []
        if rst:
            problems.append(f"{path}: it is not valid RST: {' '.join(rst)}")
        found[name].append(item)
        paths.append(path)
    if clean:
        problems += unclean()
    if problems:
        raise RefusalError(
            f"the files above in {FRAGMENTS} need fixing first",
            "".join(f"  {p}\n" for p in problems),
        )
    if not paths:
        raise RefusalError(f"{FRAGMENTS} holds no fragment")
    return found, paths


def release_date() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        return time.strftime("%Y-%m-%d")
    try:
        # int() would also take a sign, spaces and underscores.
        if not re.fullmatch("[0-9]+", epoch):
            raise ValueError
        return time.strftime("%Y-%m-%d", time.gmtime(int(epoch)))
    except (ValueError, OverflowError, OSError):
        raise RefusalError(
            f"SOURCE_DATE_EPOCH is not a time in seconds: {epoch}"
        ) from None


def section(
    version: str,
    found: dict[str, list[str]],
    date: str,
    heading: str,
    sub: str,
) -> str:
    title = f"`{version}`_ - {date}"
    parts = []
    for name in CATEGORIES.values():
        if found[name]:
            bullets = "".join(b + "\n" for b in found[name])
            parts.append(f"{name}\n{sub * len(name)}\n{bullets}")
    return f"{title}\n{heading * len(title)}\n" + "\n".join(parts)


def underlines(text: str) -> tuple[str, str]:
    heading = UNRELEASED.search(text)
    sub = SUBSECTION.search(text)
    return heading.group(1) if heading else "-", sub.group(1) if sub else "."


def insert(text: str, version: str, new: str) -> str:
    headings = list(UNRELEASED.finditer(text))
    if not headings:
        raise RefusalError(f"{FILE} has no `Unreleased`_ heading")
    if len(headings) > 1:
        raise RefusalError(f"{FILE} has more than one `Unreleased`_ heading")
    if len(ANY_UNRELEASED_TARGET.findall(text)) > 1:
        raise RefusalError(
            f"{FILE} has more than one `.. _Unreleased:` target"
        )
    target = UNRELEASED_TARGET.search(text)
    if target is None:
        raise RefusalError(f"{FILE} has no `.. _Unreleased:` compare target")

    start = headings[0].end()
    rest = RELEASE.search(text, start)
    if rest is not None:
        end = rest.start()
    else:
        after = LINK_TARGET.search(text, start)
        end = after.start() if after else len(text)
    first = LINK_TARGET.search(text)
    if first is not None and first.start() < end:
        # The splices below assume every target follows the section.
        raise RefusalError(
            f"{FILE} has a link target before the end of Unreleased, so "
            "move it below the releases first"
        )
    if text[start:end].strip():
        raise RefusalError(
            f"Unreleased has entries of its own, so move them into "
            f"{FRAGMENTS} first"
        )
    if re.search(rf"^\.\. _{re.escape(version)}:", text, re.MULTILINE):
        raise RefusalError(f"{FILE} already has a {version} link target")

    url, previous = target.groups()
    links = (
        f".. _Unreleased: {url}/compare/v{version}...HEAD\n"
        f".. _{version}: {url}/compare/{previous}...v{version}\n"
    )
    text = text[: target.start()] + links + text[target.end() :]
    # The link targets follow the section, so its offsets still hold.
    return text[:start] + "\n" + new + "\n" + text[end:]


def write(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    # Next to the file, so the rename is atomic on its file system.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
            out.write(text)
        # mkstemp makes the file private, and the changelog is not.
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def run(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(
        prog="changelog.py",
        description="Write the changelog section for a release.",
    )
    parser.add_argument(
        "--version",
        required=True,
        metavar="X.Y.Z",
        help="the version being released, whose tag must not exist yet",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the new section and change nothing",
    )
    args = parser.parse_args(argv)
    version = args.version

    wanted = VERSION.fullmatch(version)
    if wanted is None:
        raise RefusalError(f"not a version X.Y.Z: {version}")
    if succeeds("rev-parse", "--verify", "--quiet", f"refs/tags/v{version}"):
        raise RefusalError(f"tag v{version} already exists")
    date = release_date()
    tag = newest_tag()
    if tag is not None and numbers(wanted) <= numbers(tag):
        raise RefusalError(f"{version} is not greater than {tag.group(0)}")

    path = ROOT / FILE
    if not args.stdout:
        if not path.exists():
            raise RefusalError(f"{FILE} does not exist")
        if not succeeds("ls-files", "--error-unmatch", "--", str(FILE)):
            raise RefusalError(f"{FILE} is untracked, so commit it first")
        if not succeeds("diff", "--quiet", "HEAD", "--", str(FILE)):
            raise RefusalError(
                f"{FILE} has uncommitted changes, so commit or drop them "
                "first"
            )

    check = rst_checker()
    if check is None:
        warn("docutils is not importable, so the entries are not checked")
    found, paths = fragments(not args.stdout, check)

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    heading, sub = underlines(text)
    new = section(version, found, date, heading, sub)
    if args.stdout:
        return new
    updated = insert(text, version, new)
    # Each entry parses alone, but two entries can still clash, as two
    # that define the same target name do.
    clashes = check(updated) if check is not None else []
    if clashes:
        raise RefusalError(
            f"the updated {FILE} does not parse cleanly:\n  "
            + "\n  ".join(clashes)
        )
    write(path, updated)
    try:
        git("rm", "-q", "--", *paths)
    except RefusalError as error:
        raise RefusalError(
            f"wrote {FILE}, but {error}\n"
            f"Finish the release with:\n"
            f"  git rm -q -- {' '.join(paths)}\n"
            f"or undo it with:\n"
            f"  git checkout -- {FILE}"
        ) from None
    entries = "entry" if len(paths) == 1 else "entries"
    return (
        f"changelog.py: wrote {version} with {len(paths)} {entries} to "
        f"{FILE} and removed their fragments\n"
    )


def main() -> int:
    try:
        sys.stdout.write(run(sys.argv[1:]))
    except RefusalError as refusal:
        sys.stderr.write(refusal.listing)
        print(f"changelog.py: {refusal}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
