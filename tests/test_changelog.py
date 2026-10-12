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

"""Run changelog.py on throwaway repositories and check what it writes and
what it refuses.

"""

import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOP = Path(__file__).resolve().parents[1]
URL = "https://github.com/greened/example"
# 2026-03-04T23:30:00Z, late enough that a zone east of UTC is a day on.
EPOCH = "1772667000"
DATE = "2026-03-04"

HEADER = f"""\
ChangeLog
=========
`Unreleased`_
-------------

`0.1.0`_ - 2026-01-01
---------------------
Fixed
.....
- An old fix.

.. _Unreleased: {URL}/compare/v0.1.0...HEAD
.. _0.1.0: {URL}/compare/v0.0.9...v0.1.0
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repository with changelog.py, a changelog, changelog.d with only
    its README and a v0.1.0 tag.

    git reads no global or system config, no config or template named by
    the caller's environment and no repository it names, so neither a user
    hook nor the repository running the tests reaches it.

    """
    for name in list(os.environ):
        if name in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_COMMON_DIR",
            "GIT_CONFIG_PARAMETERS",
            "GIT_CONFIG_COUNT",
            "GIT_TEMPLATE_DIR",
        ) or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Fixture")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "fixture@example.invalid")
        monkeypatch.setenv(f"GIT_{role}_DATE", "2026-01-01T12:00:00Z")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", EPOCH)

    path = tmp_path / "repo"
    git(tmp_path, "init", "-q", "-b", "master", str(path))
    shutil.copy2(TOP / "changelog.py", path)
    (path / "docs").mkdir()
    (path / "docs" / "changelog.rst").write_text(HEADER)
    (path / "changelog.d").mkdir()
    (path / "changelog.d" / "README.rst").write_text("Not an entry.\n")
    land(path, "first")
    git(path, "tag", "v0.1.0")
    return path


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def land(repo, message="a change"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def fragment(repo, name, text, landed=True):
    (repo / "changelog.d" / name).write_text(text)
    if landed:
        land(repo, f"add {name}")


def run(repo, *args):
    return subprocess.run(
        [sys.executable, "changelog.py", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def changelog(repo):
    return (repo / "docs" / "changelog.rst").read_text()


def state(repo):
    status = git(
        repo, "status", "--porcelain", "--untracked-files=all", "--ignored"
    )
    path = repo / "docs" / "changelog.rst"
    return path.read_text() if path.exists() else None, status


def refuses(repo, why, *args):
    before = state(repo)
    result = run(repo, *args)
    assert result.returncode != 0, result.stdout
    assert why in result.stderr
    assert state(repo) == before
    return result.stderr


def release_heading(version, date):
    title = f"`{version}`_ - {date}"
    return f"{title}\n{'-' * len(title)}\n"


def edit_changelog(repo, old, new):
    text = changelog(repo)
    assert old in text
    (repo / "docs" / "changelog.rst").write_text(text.replace(old, new))
    land(repo, "edit the changelog")


def test_writes_section_and_targets(repo):
    fragment(repo, "speed.security.rst", "A security fix.\n")
    fragment(repo, "thing.added.rst", "A new thing.\n")
    fragment(repo, "crash.fixed.rst", "A fix.\n")
    result = run(repo, "--version", "0.2.0")
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "changelog.py: wrote 0.2.0 with 3 entries to docs/changelog.rst "
        "and removed their fragments\n"
    )
    # The empty subsections are left out.
    assert changelog(repo) == (
        "ChangeLog\n"
        "=========\n"
        "`Unreleased`_\n"
        "-------------\n"
        "\n" + release_heading("0.2.0", DATE) + "Added\n"
        ".....\n"
        "- A new thing.\n"
        "\n"
        "Fixed\n"
        ".....\n"
        "- A fix.\n"
        "\n"
        "Security\n"
        "........\n"
        "- A security fix.\n"
        "\n"
        "`0.1.0`_ - 2026-01-01\n"
        "---------------------\n"
        "Fixed\n"
        ".....\n"
        "- An old fix.\n"
        "\n"
        f".. _Unreleased: {URL}/compare/v0.2.0...HEAD\n"
        f".. _0.2.0: {URL}/compare/v0.1.0...v0.2.0\n"
        f".. _0.1.0: {URL}/compare/v0.0.9...v0.1.0\n"
    )


def test_counts_one_entry(repo):
    fragment(repo, "x.added.rst", "A.\n")
    result = run(repo, "--version", "0.2.0")
    assert result.returncode == 0, result.stderr
    assert " with 1 entry to " in result.stdout


def test_stages_fragment_removal(repo):
    fragment(repo, "a.added.rst", "A.\n")
    fragment(repo, "b.fixed.rst", "B.\n")
    assert run(repo, "--version", "0.2.0").returncode == 0
    staged = git(repo, "diff", "--cached", "--name-status")
    assert staged == "D\tchangelog.d/a.added.rst\nD\tchangelog.d/b.fixed.rst\n"
    unstaged = git(repo, "diff", "--name-only")
    assert unstaged == "docs/changelog.rst\n"
    assert [p.name for p in (repo / "changelog.d").iterdir()] == ["README.rst"]


def test_orders_every_category(repo):
    for name in ("security", "fixed", "removed", "deprecated", "changed"):
        fragment(repo, f"x.{name}.rst", f"{name}\n")
    fragment(repo, "x.added.rst", "added\n")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    titles = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
    assert result.stdout == release_heading("0.2.0", DATE) + "\n".join(
        f"{t}\n{'.' * len(t)}\n- {t.lower()}\n" for t in titles
    )


def test_sorts_by_slug(repo):
    fragment(repo, "b.fixed.rst", "B.\n")
    fragment(repo, "a-10.fixed.rst", "A ten.\n")
    fragment(repo, "a-2.fixed.rst", "A two.\n")
    fragment(repo, "a.fixed.rst", "A.\n")
    fragment(repo, "0-first.fixed.rst", "Zero.\n")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith(
        "Fixed\n.....\n- Zero.\n- A.\n- A two.\n- A ten.\n- B.\n"
    )


def test_reindents_and_keeps_paragraphs(repo):
    fragment(
        repo,
        "x.changed.rst",
        "\n\n    The first line of a long entry that the author wrapped by"
        " hand well past the usual width,\n"
        "    and its second line.  \n"
        "\n"
        "      An indented line.\n"
        "\n"
        "    A second paragraph.\n\n\n",
    )
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith(
        "Changed\n.......\n"
        "- The first line of a long entry that the author wrapped by hand"
        " well past the usual width,\n"
        "  and its second line.\n"
        "\n"
        "    An indented line.\n"
        "\n"
        "  A second paragraph.\n"
    )


def test_multi_paragraph_entries_parse(repo):
    docutils = pytest.importorskip("docutils.core")
    fragment(repo, "a.added.rst", "One.\n\nTwo.\n")
    fragment(repo, "b.added.rst", "Three.\n")
    assert run(repo, "--version", "0.2.0").returncode == 0
    tree = docutils.publish_doctree(
        changelog(repo), settings_overrides={"report_level": 5}
    )
    items = [
        [p.astext() for p in item.children]
        for item in tree.findall(lambda n: n.tagname == "list_item")
    ]
    assert items[:2] == [["One.", "Two."], ["Three."]]


def test_strips_byte_order_mark(repo):
    (repo / "changelog.d" / "x.added.rst").write_bytes(b"\xef\xbb\xbfA.\n")
    land(repo)
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith("Added\n.....\n- A.\n")


def test_reuses_underline_characters(repo):
    edit_changelog(repo, "`Unreleased`_\n-------------\n", "")
    edit_changelog(
        repo,
        "`0.1.0`_ - 2026-01-01\n---------------------\nFixed\n.....\n",
        "`Unreleased`_\n~~~~~~~~~~~~~\n\n"
        "`0.1.0`_ - 2026-01-01\n~~~~~~~~~~~~~~~~~~~~~\nFixed\n^^^^^\n",
    )
    fragment(repo, "x.added.rst", "A.\n")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    title = f"`0.2.0`_ - {DATE}"
    assert (
        result.stdout == f"{title}\n{'~' * len(title)}\nAdded\n^^^^^\n- A.\n"
    )


def test_keeps_mode(repo):
    os.chmod(repo / "docs" / "changelog.rst", 0o640)
    fragment(repo, "x.added.rst", "A.\n")
    assert run(repo, "--version", "0.2.0").returncode == 0
    mode = (repo / "docs" / "changelog.rst").stat().st_mode & 0o777
    assert mode == 0o640


def test_stdout_changes_nothing(repo):
    fragment(repo, "x.added.rst", "A.\n")
    before = state(repo)
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        release_heading("0.2.0", DATE) + "Added\n.....\n- A.\n"
    )
    assert state(repo) == before


def test_stdout_skips_clean_check(repo):
    fragment(repo, "x.added.rst", "A.\n", landed=False)
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert "- A.\n" in result.stdout


def test_stdout_without_file(repo):
    fragment(repo, "x.added.rst", "A.\n")
    git(repo, "rm", "-q", "docs/changelog.rst")
    land(repo, "remove the changelog")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        release_heading("0.2.0", DATE) + "Added\n.....\n- A.\n"
    )


def test_warns_without_docutils(repo, tmp_path, monkeypatch):
    fake = tmp_path / "fake" / "docutils"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text('raise ImportError("hidden")\n')
    monkeypatch.setenv("PYTHONPATH", str(fake.parent))
    fragment(repo, "x.added.rst", "Accepts *args.\n")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert "docutils is not importable" in result.stderr
    assert "- Accepts *args.\n" in result.stdout


def test_readme_is_not_a_fragment(repo):
    (repo / "changelog.d" / "README.rst").write_text("Changed here.\n")
    fragment(repo, "x.added.rst", "A.\n", landed=False)
    land(repo)
    assert run(repo, "--version", "0.2.0").returncode == 0
    assert "Changed here" not in changelog(repo)
    assert (repo / "changelog.d" / "README.rst").exists()


def test_refuses_without_fragments(repo):
    refuses(repo, "changelog.d holds no fragment", "--version", "0.2.0")


def test_refuses_without_directory(repo):
    git(repo, "rm", "-q", "-r", "changelog.d")
    land(repo, "remove changelog.d")
    refuses(repo, "changelog.d holds no fragment", "--version", "0.2.0")


@pytest.mark.parametrize(
    "name",
    [
        "Upper.added.rst",
        "-lead.added.rst",
        "under_score.added.rst",
        "x.added.txt",
        "x.rst",
        "x.added.rst~",
        ".gitkeep",
    ],
)
def test_refuses_bad_name(repo, name):
    fragment(repo, "good.added.rst", "A.\n")
    fragment(repo, name, "A.\n")
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert f"changelog.d/{name}: the name is not" in err
    assert "good.added.rst" not in err


@pytest.mark.parametrize("category", ["Added", "new", "fix"])
def test_refuses_unknown_category(repo, category):
    fragment(repo, f"x.{category}.rst", "A.\n")
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert f"changelog.d/x.{category}.rst: {category} is not one of" in err


def test_refuses_symlink(repo):
    (repo / "entry.txt").write_text("A.\n")
    (repo / "changelog.d" / "x.added.rst").symlink_to("../entry.txt")
    land(repo)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is not a regular file" in err


@pytest.mark.parametrize("text", ["- A.\n", "\n  * A.\n  * B.\n", "+ A.\n"])
def test_refuses_leading_bullet(repo, text):
    fragment(repo, "x.added.rst", text)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it starts with a bullet" in err


def test_refuses_directory(repo):
    (repo / "changelog.d" / "x.added.rst").mkdir()
    (repo / "changelog.d" / "x.added.rst" / "y").write_text("A.\n")
    land(repo)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is not a regular file" in err


@pytest.mark.parametrize("text", ["", "\n  \n\n"])
def test_refuses_empty_fragment(repo, text):
    fragment(repo, "x.added.rst", text)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is empty" in err


def test_refuses_non_utf8(repo):
    (repo / "changelog.d" / "x.added.rst").write_bytes(b"caf\xe9\n")
    land(repo)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is not UTF-8" in err


def test_refuses_untracked_fragment(repo):
    fragment(repo, "x.added.rst", "A.\n", landed=False)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is untracked" in err


def test_refuses_ignored_fragment(repo):
    (repo / ".gitignore").write_text("/changelog.d/x.added.rst\n")
    land(repo)
    fragment(repo, "x.added.rst", "A.\n", landed=False)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is untracked" in err


def test_refuses_changed_fragment(repo):
    fragment(repo, "x.added.rst", "A.\n")
    fragment(repo, "x.added.rst", "B.\n", landed=False)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it has uncommitted changes" in err


def test_refuses_staged_fragment(repo):
    fragment(repo, "x.added.rst", "A.\n", landed=False)
    git(repo, "add", "changelog.d/x.added.rst")
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it has uncommitted changes" in err


def test_refuses_deleted_fragment(repo):
    fragment(repo, "x.added.rst", "A.\n")
    fragment(repo, "y.added.rst", "B.\n")
    (repo / "changelog.d" / "y.added.rst").unlink()
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/y.added.rst: it has uncommitted changes" in err


def test_refusal_lists_every_file(repo):
    fragment(repo, "a.added.rst", "")
    fragment(repo, "b.bogus.rst", "B.\n")
    fragment(repo, "c.fixed.rst", "C.\n", landed=False)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/a.added.rst: it is empty" in err
    assert "changelog.d/b.bogus.rst: bogus is not one of" in err
    assert "changelog.d/c.fixed.rst: it is untracked" in err


def test_refuses_invalid_rst(repo):
    pytest.importorskip("docutils")
    fragment(repo, "x.added.rst", "Accepts *args and the --x_ flag.\n")
    fragment(repo, "y.added.rst", "Fine.\n")
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is not valid RST" in err
    assert "y.added.rst" not in err


def test_refuses_section_title(repo):
    pytest.importorskip("docutils")
    fragment(repo, "x.added.rst", "A title\n=======\n\nText.\n")
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.added.rst: it is not valid RST" in err


def test_keeps_rst_markup(repo):
    pytest.importorskip("docutils")
    fragment(repo, "x.added.rst", "Accepts ``*args`` and ``--x_``.\n")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "- Accepts ``*args`` and ``--x_``.\n" in result.stdout


@pytest.mark.parametrize(
    "text",
    [
        "The crash in :issue:`12` is gone.\n",
        "See `nowhere`_ for more.\n",
    ],
)
def test_refuses_sphinx_roles_and_unknown_targets(repo, text):
    pytest.importorskip("docutils")
    fragment(repo, "x.fixed.rst", text)
    err = refuses(repo, "need fixing first", "--version", "0.2.0")
    assert "changelog.d/x.fixed.rst: it is not valid RST" in err


def test_accepts_anonymous_links_with_the_same_text(repo):
    # Named inline links with the same text clash under older docutils,
    # and the whole file is checked, so the guide asks for this form.
    pytest.importorskip("docutils")
    for name, host in (("a", "a.invalid"), ("b", "b.invalid")):
        fragment(
            repo,
            f"{name}.fixed.rst",
            f"See `the issue <https://{host}/12>`__ for more.\n",
        )
    result = run(repo, "--version", "0.2.0")
    assert result.returncode == 0, result.stderr


def test_refuses_entries_that_clash(repo):
    pytest.importorskip("docutils")
    for name, host in (("a", "a.invalid"), ("b", "b.invalid")):
        fragment(
            repo,
            f"{name}.fixed.rst",
            f"See `docs`_.\n\n.. _docs: https://{host}\n",
        )
    stderr = refuses(repo, "does not parse cleanly", "--version", "0.2.0")
    assert 'Duplicate explicit target name: "docs"' in stderr


def test_date_follows_source_date_epoch_in_utc(repo, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    fragment(repo, "x.added.rst", "A.\n")
    result = run(repo, "--version", "0.2.0", "--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(release_heading("0.2.0", DATE))


def test_date_is_today_without_source_date_epoch(repo, monkeypatch):
    monkeypatch.delenv("SOURCE_DATE_EPOCH")
    fragment(repo, "x.added.rst", "A.\n")
    # The run may cross midnight.
    before = time.strftime("%Y-%m-%d")
    result = run(repo, "--version", "0.2.0", "--stdout")
    after = time.strftime("%Y-%m-%d")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(
        (release_heading("0.2.0", before), release_heading("0.2.0", after))
    )


@pytest.mark.parametrize(
    "epoch", ["", "soon", "1.5", "+5", "-5", " 12", "1_000", "١٢"]
)
def test_refuses_bad_source_date_epoch(repo, monkeypatch, epoch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", epoch)
    fragment(repo, "x.added.rst", "A.\n")
    refuses(repo, "SOURCE_DATE_EPOCH is not a time", "--version", "0.2.0")


@pytest.mark.parametrize(
    "version",
    ["1.2", "1..2", "v1.2.3", "1.2.3.4", "1.2.3rc1", "00.1.0", "1.02.3"],
)
def test_refuses_bad_version(repo, version):
    fragment(repo, "x.added.rst", "A.\n")
    refuses(repo, "not a version", "--version", version)


def test_refuses_existing_tag(repo):
    fragment(repo, "x.added.rst", "A.\n")
    refuses(repo, "already exists", "--version", "0.1.0")


def test_refuses_version_not_greater(repo):
    fragment(repo, "x.added.rst", "A.\n")
    refuses(repo, "not greater than v0.1.0", "--version", "0.0.9")


def test_picks_highest_tag(repo):
    git(repo, "tag", "v0.0.5")
    fragment(repo, "x.added.rst", "A.\n")
    git(repo, "tag", "v0.0.7")
    refuses(repo, "not greater than v0.1.0", "--version", "0.0.8")
    assert run(repo, "--version", "0.1.1", "--stdout").returncode == 0


def test_ignores_unmerged_tag(repo):
    git(repo, "checkout", "-q", "-b", "side")
    fragment(repo, "side.added.rst", "Side.\n")
    git(repo, "tag", "v0.5.0")
    git(repo, "checkout", "-q", "master")
    fragment(repo, "x.added.rst", "A.\n")
    assert run(repo, "--version", "0.2.0", "--stdout").returncode == 0


def test_skips_pre_release_tags(repo):
    fragment(repo, "x.added.rst", "A.\n")
    git(repo, "tag", "v0.2.0rc1")
    git(repo, "tag", "v0.3.0-rc2")
    assert run(repo, "--version", "0.2.0", "--stdout").returncode == 0


def test_runs_without_tag(repo):
    git(repo, "tag", "-d", "v0.1.0")
    fragment(repo, "x.added.rst", "A.\n")
    assert run(repo, "--version", "0.0.1").returncode == 0
    assert f".. _0.0.1: {URL}/compare/v0.1.0...v0.0.1\n" in changelog(repo)


def test_refuses_missing_file(repo):
    fragment(repo, "x.added.rst", "A.\n")
    git(repo, "rm", "-q", "docs/changelog.rst")
    land(repo, "remove the changelog")
    refuses(repo, "does not exist", "--version", "0.2.0")


def test_refuses_untracked_file(repo):
    fragment(repo, "x.added.rst", "A.\n")
    git(repo, "rm", "-q", "--cached", "docs/changelog.rst")
    git(repo, "commit", "-q", "-m", "untrack")
    refuses(repo, "is untracked", "--version", "0.2.0")


def test_refuses_uncommitted_file(repo):
    fragment(repo, "x.added.rst", "A.\n")
    with open(repo / "docs" / "changelog.rst", "a") as f:
        f.write("\n")
    refuses(repo, "uncommitted changes", "--version", "0.2.0")


def test_refuses_filled_unreleased(repo):
    fragment(repo, "x.added.rst", "A.\n")
    edit_changelog(
        repo,
        "-------------\n\n",
        "-------------\nAdded\n.....\n- By hand.\n\n",
    )
    refuses(repo, "entries of its own", "--version", "0.2.0")


def test_refuses_existing_link_target(repo):
    fragment(repo, "x.added.rst", "A.\n")
    edit_changelog(
        repo,
        f".. _0.1.0: {URL}",
        f".. _0.2.0: {URL}/compare/v0.1.0...v0.2.0\n.. _0.1.0: {URL}",
    )
    refuses(repo, "already has a 0.2.0 link target", "--version", "0.2.0")


TARGET = f".. _Unreleased: {URL}/compare/v0.1.0...HEAD\n"


@pytest.mark.parametrize(
    "edits",
    [
        [("ChangeLog\n", f".. _x: {URL}\n\nChangeLog\n")],
        [("-------------\n\n", f"-------------\n\n.. _x: {URL}\n\n")],
        [(TARGET, ""), ("ChangeLog\n", f"{TARGET}\nChangeLog\n")],
    ],
    ids=["above", "inside", "unreleased-above"],
)
def test_refuses_link_target_before_releases(repo, edits):
    fragment(repo, "x.added.rst", "A.\n")
    for old, new in edits:
        edit_changelog(repo, old, new)
    why = "link target before the end of Unreleased"
    refuses(repo, why, "--version", "0.2.0")


def test_reports_recovery_when_rm_fails(repo, monkeypatch, capsys):
    fragment(repo, "a.added.rst", "A.\n")
    fragment(repo, "b.fixed.rst", "B.\n")
    spec = importlib.util.spec_from_file_location(
        "changelog", repo / "changelog.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write = module.write

    # A lock taken once the checks pass makes only git rm fail.
    def write_then_lock(path, text):
        write(path, text)
        (repo / ".git" / "index.lock").touch()

    monkeypatch.setattr(module, "write", write_then_lock)
    monkeypatch.setattr(sys, "argv", ["changelog.py", "--version", "0.2.0"])
    assert module.main() == 1
    err = capsys.readouterr().err
    assert "wrote docs/changelog.rst, but git rm failed" in err
    assert err.endswith(
        "Finish the release with:\n"
        "  git rm -q -- changelog.d/a.added.rst changelog.d/b.fixed.rst\n"
        "or undo it with:\n"
        "  git checkout -- docs/changelog.rst\n"
    )
    (repo / ".git" / "index.lock").unlink()
    git(
        repo,
        "rm",
        "-q",
        "--",
        "changelog.d/a.added.rst",
        "changelog.d/b.fixed.rst",
    )
    assert "`0.2.0`_" in changelog(repo)


@pytest.mark.parametrize(
    "old, new, why",
    [
        ("`Unreleased`_\n-------------\n\n", "", "no `Unreleased`_ heading"),
        (
            "`Unreleased`_\n-------------\n\n",
            "`Unreleased`_\n-------------\n\n" * 2,
            "more than one `Unreleased`_ heading",
        ),
        (
            f".. _Unreleased: {URL}/compare/v0.1.0...HEAD\n",
            "",
            "no `.. _Unreleased:` compare target",
        ),
        (
            f".. _Unreleased: {URL}/compare/v0.1.0...HEAD\n",
            f".. _Unreleased: {URL}/compare/v0.1.0...HEAD\n" * 2,
            "more than one `.. _Unreleased:` target",
        ),
    ],
)
def test_refuses_bad_unreleased(repo, old, new, why):
    fragment(repo, "x.added.rst", "A.\n")
    edit_changelog(repo, old, new)
    refuses(repo, why, "--version", "0.2.0")
