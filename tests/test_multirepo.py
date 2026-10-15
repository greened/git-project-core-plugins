#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2020-present David A. Greene <dag@obbligato.org>

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

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import common
import git_project
import pygit2
import pytest

import git_project_core_plugins.multirepo as multirepo

# The installed program, so the tests run what a user runs.
EXE = str(Path(sys.executable).parent / "git-project")

# Author times for each remote's commits on master, oldest first.
TIMES = {"alpha": (1000, 2000, 3000), "beta": (1500, 2500, 3500)}


def _git(*args, **kwargs):
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    ).stdout


def _make_remote(path, name, times):
    repo = pygit2.init_repository(str(path), bare=True)
    parents = []
    oids = []
    for i, when in enumerate(times):
        signature = pygit2.Signature("Alice Author", "alice@authors.tld", when)
        builder = repo.TreeBuilder()
        builder.insert(
            f"{name}{i}.txt",
            repo.create_blob(f"{name} {i}\n"),
            pygit2.GIT_FILEMODE_BLOB,
        )
        oid = repo.create_commit(
            "refs/heads/master",
            signature,
            signature,
            f"{name} {i}",
            builder.write(),
            parents,
        )
        parents = [oid]
        oids.append(str(oid))
    return oids


@pytest.fixture
def mr(monkeypatch, tmp_path):
    """Two remotes, a set file that a temporary global config names, a home
    directory to hold the members' roots and a cwd outside any repository.

    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    setfile = tmp_path / "sets"
    setfile.touch()
    global_config = tmp_path / "global.gitconfig"
    _git(
        "config",
        "--file",
        str(global_config),
        "project.set.file",
        str(setfile),
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))

    remotes = tmp_path / "remotes"
    commits = {}
    urls = {}
    for name, times in TIMES.items():
        urls[name] = str(remotes / f"{name}.git")
        commits[name] = _make_remote(remotes / f"{name}.git", name, times)

    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    def write_sets(text):
        setfile.write_text(text)

    def define(*names, set_name="tools"):
        text = ""
        for name in names:
            text += (
                f'[project "repo.{name}"]\n'
                f"\turl = {urls[name]}\n"
                f"\troot = ~/{name}\n"
            )
        text += f'[project "set.{set_name}"]\n'
        for name in names:
            text += f"\trepo = {name}\n"
        write_sets(text)

    def umbrella(name):
        """Make the umbrella layout for a member, as clone --worktree does."""
        root = home / name
        store = root / f".{name}.git"
        _git("clone", "-q", "--bare", urls[name], str(store))
        (root / ".git").write_text(f"gitdir: .{name}.git\n")
        _git("--git-dir", str(store), "config", "project.branch", "master")
        _git("--git-dir", str(store), "config", "project.remote", "origin")
        return SimpleNamespace(root=root, store=store)

    def run(*args, **kwargs):
        kwargs.setdefault("cwd", cwd)
        return subprocess.run(
            [EXE, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=120,
            check=False,
            **kwargs,
        )

    return SimpleNamespace(
        home=home,
        cwd=cwd,
        setfile=setfile,
        global_config=global_config,
        urls=urls,
        commits=commits,
        write_sets=write_sets,
        define=define,
        umbrella=umbrella,
        run=run,
    )


def _project():
    git = git_project.Git()
    return git, git_project.Project.get(git, "project", set_defaults=False)


def _multirepo(*cmd, set_name="tools", **kwargs):
    clargs = {
        "set": set_name,
        "cmd": list(cmd),
        "jobs": None,
        "skip_missing": False,
        "commit": None,
        "worktree_add_parser": None,
    }
    clargs.update(kwargs)
    git, project = _project()
    return multirepo.command_multirepo(
        git, None, project, common.AttrDict(clargs)
    )


def _state(store, name="topic"):
    """Return the branch, record, git worktree and path state for name."""
    repo = pygit2.Repository(str(store))
    config = pygit2.Config(str(store / "config"))
    prefix = f"project.worktree.{name}."
    return SimpleNamespace(
        branch=repo.branches.local.get(name),
        record={
            entry.name[len(prefix) :]: entry.value
            for entry in config
            if entry.name.startswith(prefix)
        },
        worktree=name in repo.list_worktrees(),
        path=(store.parent / name).exists(),
    )


def _assert_untouched(store, name="topic"):
    state = _state(store, name)
    assert state.branch is None
    assert state.record == {}
    assert not state.worktree
    assert not state.path


# Validation


def _valid(mr):
    return (
        f'[project "repo.alpha"]\n\turl = {mr.urls["alpha"]}\n'
        f"\troot = ~/alpha\n"
        f'[project "set.tools"]\n\trepo = alpha\n'
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[other]\n\tkey = 1\n", "unknown key other.key"),
        ('[project "repo.alpha"]\n\tcolour = red\n', "unknown key"),
        ('[project "set.tools"]\n\tfoo = x\n', "unknown key"),
        (
            '[project "repo.bad.name"]\n\turl = /x\n\troot = ~/x\n',
            "valid name",
        ),
        ('[project "repo.-x"]\n\turl = /x\n\troot = ~/x\n', "valid name"),
        ('[project "repo.a"]\n\troot = ~/a\n', "exactly one url"),
        ('[project "repo.a"]\n\turl = /a\n', "exactly one root"),
        (
            '[project "repo.a"]\n\turl = /a\n\turl = /b\n\troot = ~/a\n',
            "exactly one url",
        ),
        (
            '[project "repo.a"]\n\turl = /a\n\troot = ~/a\n\troot = ~/b\n',
            "exactly one root",
        ),
        (
            (
                '[project "repo.a"]\n\turl = /a\n\troot = ~/x\n'
                '[project "repo.b"]\n\turl = /b\n\troot = ~/y/../x\n'
            ),
            "the same root",
        ),
        ('[project "repo.a"]\n\turl = /a\n\troot = /abs/a\n', "start with ~/"),
        ('[project "repo.a"]\n\turl = /a\n\troot = ~/../a\n', "start with ~/"),
        ('[project "repo.a"]\n\turl = /a\n\troot = ~/\n', "home directory"),
        ('[project "repo.a"]\n\turl = /a\n\troot = ~/.\n', "home directory"),
        (
            '[project "repo.a"]\n\turl = /a\n\troot = ~/a/../../x\n',
            "start with ~/",
        ),
        ('[project "repo.a"]\n\turl = ../a.git\n\troot = ~/a\n', "relative"),
        ('[project "repo.a"]\n\turl = a.git\n\troot = ~/a\n', "relative"),
        ('[project "set.tools"]\n\trepo = ghost\n', "undefined member ghost"),
        (
            (
                '[project "repo.a"]\n\turl = /a\n\troot = ~/a\n'
                '[project "set.tools"]\n\trepo = a\n\trepo = a\n'
            ),
            "lists a twice",
        ),
        ("[include]\n\tpath = /dev/null\n", "unknown key include.path"),
    ],
)
def test_set_file_refusals(mr, text, message):
    mr.write_sets(text)

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert message in error.value.message


def test_set_file_symlinked_root_refused(mr):
    (mr.home / "x").mkdir()
    (mr.home / "y").symlink_to(mr.home / "x")
    mr.write_sets(
        '[project "repo.a"]\n\turl = /a\n\troot = ~/x\n'
        '[project "repo.b"]\n\turl = /b\n\troot = ~/y\n'
    )

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert "the same root" in error.value.message


@pytest.mark.parametrize(
    "url",
    [
        "/abs/path.git",
        "file:///abs/path.git",
        "https://example.com/a.git",
        "git@github.com:greened/git-project.git",
        "host:path",
    ],
)
def test_set_file_accepts_url(mr, url):
    mr.write_sets(f'[project "repo.a"]\n\turl = {url}\n\troot = ~/a\n')

    assert multirepo._load("project").members["a"].url == url


def test_set_file_keeps_set_order(mr):
    mr.write_sets(
        '[project "repo.b"]\n\turl = /b\n\troot = ~/b\n'
        '[project "repo.a"]\n\turl = /a\n\troot = ~/a\n'
        '[project "set.tools"]\n\trepo = b\n\trepo = a\n'
    )

    assert multirepo._load("project").sets["tools"] == ["b", "a"]


def test_set_file_locator_unset(mr):
    mr.global_config.write_text("")

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert "project.set.file is not set" in error.value.message


def test_set_file_locator_multiple(mr):
    _git(
        "config",
        "--file",
        str(mr.global_config),
        "--add",
        "project.set.file",
        str(mr.setfile),
    )

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert "has 2 values" in error.value.message


def test_set_file_locator_relative(mr):
    _git("config", "--file", str(mr.global_config), "project.set.file", "sets")

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert "not an absolute path" in error.value.message


@pytest.mark.parametrize("text", ['[project "set"]\n\tfile\n', ""])
def test_set_file_locator_without_a_value(mr, text):
    if text:
        mr.global_config.write_text(text)
    else:
        _git("config", "--file", str(mr.global_config), "project.set.file", "")

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert "project.set.file has no value" in error.value.message


_LOCATE = """
import git_project_core_plugins.multirepo as multirepo

print(multirepo._locate("project")[0])
"""


@pytest.mark.parametrize("where", ["home", "xdg"])
def test_set_file_locator_without_git_config_global(mr, where):
    xdg = mr.home / "xdg"
    if where == "home":
        config = mr.home / ".gitconfig"
    else:
        config = xdg / "git" / "config"
    config.parent.mkdir(parents=True, exist_ok=True)
    _git("config", "--file", str(config), "project.set.file", str(mr.setfile))
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "GIT_CONFIG_GLOBAL"
    }
    env["XDG_CONFIG_HOME"] = str(xdg)

    # libgit2 reads HOME once per process, so ask a new one.
    result = subprocess.run(
        [sys.executable, "-c", _LOCATE],
        cwd=mr.cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == str(mr.setfile)


def test_set_file_missing(mr):
    mr.setfile.unlink()

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo._load("project")

    assert "does not exist" in error.value.message


def test_set_file_locator_expands_home(mr):
    target = mr.home / "dotfiles" / "sets"
    target.parent.mkdir()
    target.write_text(_valid(mr))
    _git(
        "config",
        "--file",
        str(mr.global_config),
        "project.set.file",
        "~/dotfiles/sets",
    )

    assert multirepo._load("project").sets == {"tools": ["alpha"]}


# Member resolution


def test_resolve_missing_member_refused(mr, monkeypatch):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha", "beta")
    alpha = mr.umbrella("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("branch", "status")

    assert "beta" in error.value.message
    assert "does not exist" in error.value.message
    _assert_untouched(alpha.store)


def test_resolve_wrong_url_refused(mr, monkeypatch):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    alpha = mr.umbrella("alpha")
    _git("--git-dir", str(alpha.store), "remote", "set-url", "origin", "/x")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("branch", "status", skip_missing=True)

    assert "origin url other than member alpha's" in error.value.message


@pytest.mark.parametrize("kind", ["empty", "plain clone", "no .git file"])
def test_resolve_not_an_umbrella_refused(mr, monkeypatch, kind):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    root = mr.home / "alpha"
    if kind == "empty":
        root.mkdir()
    elif kind == "plain clone":
        _git("clone", "-q", mr.urls["alpha"], str(root))
    else:
        mr.umbrella("alpha")
        (root / ".git").unlink()

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("branch", "status", skip_missing=True)

    assert "alpha" in error.value.message


def test_resolve_url_ignores_trailing_git_and_slash(mr):
    mr.define("alpha")
    alpha = mr.umbrella("alpha")
    url = mr.urls["alpha"]
    _git(
        "--git-dir", str(alpha.store), "remote", "set-url", "origin", url[:-4]
    )
    member = multirepo._load("project").members["alpha"]

    assert multirepo._resolve(member).state == "ok"

    member.url = url + "/"
    assert multirepo._resolve(member).state == "ok"


# Refusals before any child runs


@pytest.mark.parametrize(
    "cmd",
    [
        ["worktree", "migrate"],
        ["worktree", "migrate", "--apply"],
        ["init"],
        ["clone", "url"],
        ["artifact", "rm", "x"],
        ["help"],
        ["worktree"],
        ["build", "all"],
        [],
    ],
)
def test_multirepo_allowlist_refusal(mr, monkeypatch, cmd):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    mr.umbrella("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo(*cmd)

    assert "multirepo cannot run" in error.value.message
    assert "before the set name" not in error.value.message


def test_multirepo_option_after_the_set_name(mr, monkeypatch):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    mr.umbrella("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("-j", "2", "worktree", "add", "topic")

    assert "multirepo's options go before the set name" in error.value.message


@pytest.mark.parametrize("command", ["add", "rm"])
@pytest.mark.parametrize(
    "args",
    [
        ["--check"],
        ["--multirepo", "other"],
        ["--multirepo=other"],
        ["--check=yes"],
        ["--multi", "other"],
        ["--ch"],
        ["topic", "--", "--check"],
        ["topic", "--", "--multirepo=x"],
    ],
)
def test_multirepo_injected_option_refusal(mr, monkeypatch, command, args):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    alpha = mr.umbrella("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("worktree", command, *args)

    assert "passes" in error.value.message
    _assert_untouched(alpha.store)


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG"])
def test_multirepo_redirect_variable_refusal(mr, monkeypatch, var):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    alpha = mr.umbrella("alpha")
    monkeypatch.setenv(var, str(alpha.store))

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("worktree", "add", "topic")

    assert var in error.value.message
    _assert_untouched(alpha.store)


def test_set_clone_redirect_variable_refusal(mr, monkeypatch):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    monkeypatch.setenv("GIT_DIR", "/nowhere")
    git, project = _project()

    with pytest.raises(git_project.GitProjectError) as error:
        multirepo.command_set_clone(
            git, None, project, common.AttrDict({"set": "tools"})
        )

    assert "GIT_DIR" in error.value.message
    assert not (mr.home / "alpha").exists()


@pytest.mark.parametrize(
    ("cmd", "message"),
    [
        (["run", "probe"], "-j cannot be used with run"),
        (["branch", "prune", "topic"], "-j needs --no-ask"),
        (["branch", "prune", "--", "--no-ask"], "-j needs --no-ask"),
    ],
)
def test_multirepo_jobs_refusal(mr, monkeypatch, cmd, message):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")
    mr.umbrella("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo(*cmd, jobs=2)

    assert message in error.value.message


@pytest.mark.parametrize("value", ["0", "17", "x", "-1"])
def test_multirepo_jobs_range(value):
    with pytest.raises(argparse.ArgumentTypeError):
        multirepo._jobs(value)


def test_multirepo_commit_needs_worktree_add(mr, monkeypatch):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("worktree", "rm", "topic", commit=["alpha", "abcd"])

    assert "only with worktree add" in error.value.message


def test_multirepo_unknown_set(mr, monkeypatch):
    monkeypatch.setattr(sys, "argv", [EXE])
    mr.define("alpha")

    with pytest.raises(git_project.GitProjectError) as error:
        _multirepo("branch", "status", set_name="nope")

    assert "No set named nope" in error.value.message


def test_child_executable_keeps_the_name(monkeypatch, tmp_path):
    # A symlink named for another project must keep that name.
    link = tmp_path / "git-dev"
    link.symlink_to(EXE)
    monkeypatch.setattr(sys, "argv", [str(link)])

    assert multirepo._child_executable() == str(link)

    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(sys, "argv", ["git-dev"])
    assert multirepo._child_executable() == str(link)


def test_child_executable_must_be_executable(monkeypatch, tmp_path):
    script = tmp_path / "git-dev"
    script.write_text("")
    monkeypatch.setattr(sys, "argv", [str(script)])

    with pytest.raises(git_project.GitProjectError):
        multirepo._child_executable()


# set add and set rm


def _set_clargs(set_name, member, url=None, root=None):
    return common.AttrDict(
        {"set": set_name, "member": member, "url": url, "root": root}
    )


def _set_add(*args, **kwargs):
    git, project = _project()
    multirepo.command_set_add(git, None, project, _set_clargs(*args, **kwargs))


def _set_rm(*args):
    git, project = _project()
    multirepo.command_set_rm(git, None, project, _set_clargs(*args))


def test_set_add_defines_and_appends(mr):
    _set_add("tools", "alpha", url=mr.urls["alpha"], root="~/alpha")
    _set_add("tools", "beta", url=mr.urls["beta"], root="~/beta")
    _set_add("other", "alpha")

    setfile = multirepo._load("project")
    assert setfile.sets == {"tools": ["alpha", "beta"], "other": ["alpha"]}
    assert setfile.members["beta"].url == mr.urls["beta"]
    assert setfile.members["beta"].root == "~/beta"


def test_set_add_through_a_symlink_keeps_the_link(mr):
    target = mr.home / "dotfiles" / "sets"
    target.parent.mkdir()
    target.touch()
    mr.setfile.unlink()
    mr.setfile.symlink_to(target)

    _set_add("tools", "alpha", url=mr.urls["alpha"], root="~/alpha")

    assert mr.setfile.is_symlink()
    assert "repo = alpha" in target.read_text()
    assert (target.parent / "sets.multirepo-lock").exists()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"url": "/other.git", "root": "~/alpha"}, "another url or root"),
        ({"url": None, "root": "~/elsewhere"}, "go together"),
    ],
)
def test_set_add_conflicting_redefinition_refused(mr, kwargs, message):
    mr.write_sets(_valid(mr))
    before = mr.setfile.read_text()

    with pytest.raises(git_project.GitProjectError) as error:
        _set_add("other", "alpha", **kwargs)

    assert message in error.value.message
    assert mr.setfile.read_text() == before


def test_set_add_same_definition_accepted(mr):
    mr.write_sets(_valid(mr))

    _set_add("other", "alpha", url=mr.urls["alpha"], root="~/alpha")

    assert multirepo._load("project").sets["other"] == ["alpha"]


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        (("tools", "alpha"), {}, "already lists alpha"),
        (("tools", "gamma"), {}, "not defined"),
        (("tools", "gamma"), {"url": "../g.git", "root": "~/g"}, "relative"),
        (("tools", "gamma"), {"url": "/g.git", "root": "/g"}, "start with ~/"),
        (
            ("tools", "gamma"),
            {"url": "/g.git", "root": "~/alpha"},
            "same root",
        ),
        (("bad.set", "gamma"), {"url": "/g", "root": "~/g"}, "valid set"),
        (("tools", "-g"), {"url": "/g", "root": "~/g"}, "valid member"),
    ],
)
def test_set_add_refusals_leave_the_file(mr, args, kwargs, message):
    mr.write_sets(_valid(mr))
    before = mr.setfile.read_text()

    with pytest.raises(git_project.GitProjectError) as error:
        _set_add(*args, **kwargs)

    assert message in error.value.message
    assert mr.setfile.read_text() == before
    assert not [p for p in os.listdir(mr.setfile.parent) if p.endswith(".tmp")]


def test_set_write_interrupted_before_replace(mr, monkeypatch):
    mr.write_sets(_valid(mr))
    before = mr.setfile.read_text()

    def fail(src, dst):
        raise OSError("interrupted")

    monkeypatch.setattr(multirepo.os, "replace", fail)

    with pytest.raises(OSError):
        _set_add("tools", "beta", url=mr.urls["beta"], root="~/beta")

    monkeypatch.undo()
    assert mr.setfile.read_text() == before
    leftovers = [
        name for name in os.listdir(mr.setfile.parent) if name.endswith(".tmp")
    ]
    assert leftovers == []


def test_set_rm_keeps_the_definition(mr):
    mr.define("alpha", "beta")

    _set_rm("tools", "alpha")

    setfile = multirepo._load("project")
    assert setfile.sets == {"tools": ["beta"]}
    assert "alpha" in setfile.members


def test_set_rm_last_member_removes_the_set(mr):
    mr.define("alpha")
    mr.setfile.write_text(
        mr.setfile.read_text() + '[project "set.other"]\n\trepo = alpha\n'
    )

    _set_rm("tools", "alpha")

    text = mr.setfile.read_text()
    assert "set.tools" not in text
    setfile = multirepo._load("project")
    assert setfile.sets == {"other": ["alpha"]}
    assert "alpha" in setfile.members


def test_set_rm_refusals(mr):
    mr.define("alpha")
    before = mr.setfile.read_text()

    with pytest.raises(git_project.GitProjectError):
        _set_rm("tools", "beta")
    with pytest.raises(git_project.GitProjectError):
        _set_rm("nope", "alpha")

    assert mr.setfile.read_text() == before


# Each writer pauses after it reads the set file, so without the lock every
# writer copies the file before any of them replaces it.
_SLOW_WRITER = """
import sys
import time
from types import SimpleNamespace

import git_project
import git_project_core_plugins.multirepo as multirepo

parse = multirepo._parse


def slow_parse(*args, **kwargs):
    result = parse(*args, **kwargs)
    time.sleep(0.5)
    return result


multirepo._parse = slow_parse
name = sys.argv[1]
git = git_project.Git()
project = git_project.Project.get(git, "project", set_defaults=False)
multirepo.command_set_add(
    git,
    None,
    project,
    SimpleNamespace(
        set="tools", member=name, url=f"/remotes/{name}.git", root=f"~/{name}"
    ),
)
"""


def test_set_add_concurrent_writers_all_land(mr):
    names = [f"m{i}" for i in range(3)]
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _SLOW_WRITER, name],
            cwd=mr.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for name in names
    ]
    outputs = [proc.communicate(timeout=120)[0] for proc in procs]

    assert all(proc.returncode == 0 for proc in procs), outputs
    setfile = multirepo._load("project")
    assert sorted(setfile.sets["tools"]) == names
    assert sorted(setfile.members) == names


# The installed program, run from a directory outside any repository


def _members(mr, *names):
    mr.define(*names)
    return {name: mr.umbrella(name) for name in names}


def _add_run(store, name, command):
    _git("--git-dir", str(store), "config", "--add", "project.run", name)
    _git(
        "--git-dir",
        str(store),
        "config",
        f"project.run.{name}.command",
        command,
    )


def test_multirepo_add_and_rm(mr):
    members = _members(mr, "alpha", "beta")

    result = mr.run("multirepo", "tools", "worktree", "add", "topic")

    assert result.returncode == 0, result.stdout + result.stderr
    for name, member in members.items():
        state = _state(member.store)
        assert state.branch is not None
        assert str(state.branch.target) == mr.commits[name][-1]
        assert state.record["multirepo"] == "tools"
        assert state.record["branchcreated"] == "true"
        assert state.worktree
        assert state.path
    assert result.stdout.count("undo: worktree rm topic") == 2

    result = mr.run("mr", "tools", "worktree", "rm", "topic")

    assert result.returncode == 0, result.stdout + result.stderr
    for member in members.values():
        _assert_untouched(member.store)


def test_multirepo_add_after_double_dash_records_the_set(mr):
    members = _members(mr, "alpha", "beta")

    result = mr.run("multirepo", "tools", "worktree", "add", "--", "topic")

    assert result.returncode == 0, result.stdout + result.stderr
    for member in members.values():
        state = _state(member.store)
        assert state.worktree
        assert state.record["multirepo"] == "tools"


def _without_project_defaults(store):
    for key in ("project.branch", "project.remote"):
        _git("--git-dir", str(store), "config", "--unset", key)


@pytest.mark.parametrize(
    "case", ["add", "rm", "rm without path record", "rm with global artifact"]
)
def test_worktree_check_writes_nothing(mr, case):
    alpha = _members(mr, "alpha")["alpha"]
    if case == "add":
        args = ["add", "--check", "topic"]
    else:
        result = mr.run("worktree", "add", "topic", cwd=alpha.root)
        assert result.returncode == 0, result.stdout + result.stderr
        # No project branch, so nothing counts as merged.
        args = ["rm", "--check", "-f", "topic"]
    if case == "rm without path record":
        path = (alpha.root / "topic").resolve()
        _git(
            "--git-dir",
            str(alpha.store),
            "config",
            "--remove-section",
            f"project.worktreepath.{path}",
        )
    if case == "rm with global artifact":
        # libgit2 reads HOME, not GIT_CONFIG_GLOBAL.
        with open(mr.home / ".gitconfig", "a") as gitconfig:
            gitconfig.write(
                '[project "artifact.worktree.topic"]\n'
                "\tglobalpath = /nowhere\n"
            )
    _without_project_defaults(alpha.store)
    config = alpha.store / "config"
    before = config.read_bytes()

    result = mr.run("worktree", *args, cwd=alpha.root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Would" in result.stdout
    assert config.read_bytes() == before


def test_worktree_rm_expands_path_artifacts_with_the_worktree_keys(mr):
    alpha = _members(mr, "alpha")["alpha"]
    result = mr.run("worktree", "add", "topic", cwd=alpha.root)
    assert result.returncode == 0, result.stdout + result.stderr
    store = str(alpha.store)
    worktree_build = mr.home / "wt-build"
    project_build = mr.home / "project-build"
    _git(
        "--git-dir",
        store,
        "config",
        "project.worktree.topic.builddir",
        str(worktree_build),
    )
    _git("--git-dir", store, "config", "project.builddir", str(project_build))
    # The general artifact for every path record.
    _git(
        "--git-dir",
        store,
        "config",
        "project.artifact.worktreepath.itempath",
        "{builddir}-extra",
    )
    for build in (worktree_build, project_build):
        Path(f"{build}-extra").mkdir()

    result = mr.run("worktree", "rm", "-f", "topic", cwd=alpha.root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not Path(f"{worktree_build}-extra").exists()
    assert Path(f"{project_build}-extra").exists()


def test_multirepo_parallel_add(mr):
    members = _members(mr, "alpha", "beta")

    result = mr.run("multi", "-j", "2", "tools", "worktree", "add", "topic")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "== alpha" in result.stdout
    assert "== beta" in result.stdout
    for member in members.values():
        assert _state(member.store).worktree


def test_multirepo_preflight_refusal_changes_nothing(mr):
    members = _members(mr, "alpha", "beta")
    (members["beta"].root / "topic").mkdir()

    result = mr.run("multirepo", "tools", "worktree", "add", "topic")

    assert result.returncode != 0
    assert "== beta" in result.stdout
    assert "already exists" in result.stdout
    assert "Preflight failed in 1 of 2 members" in result.stdout
    _assert_untouched(members["alpha"].store)
    state = _state(members["beta"].store)
    assert state.branch is None
    assert state.record == {}
    assert not state.worktree


@pytest.mark.parametrize("path", ["../topic", "absolute"])
def test_multirepo_add_refuses_one_path_for_two_members(mr, path):
    members = _members(mr, "alpha", "beta")
    if path == "absolute":
        path = str(mr.home / "topic")

    result = mr.run("multirepo", "tools", "worktree", "add", path)

    assert result.returncode != 0
    assert (
        f"Members alpha and beta would both add a worktree at "
        f"{(mr.home / 'topic').resolve()}" in result.stdout
    )
    for member in members.values():
        _assert_untouched(member.store)
    assert not (mr.home / "topic").exists()


def test_multirepo_runs_past_a_failure(mr, tmp_path):
    members = _members(mr, "alpha", "beta")
    marker = tmp_path / "beta-ran"
    _add_run(members["alpha"].store, "probe", "exit 3")
    _add_run(members["beta"].store, "probe", f"touch {marker}")

    result = mr.run("multirepo", "tools", "run", "probe")

    assert result.returncode == 1, result.stdout + result.stderr
    assert marker.exists()
    lines = result.stdout.splitlines()
    assert any(line.split()[:2] == ["alpha", "failed"] for line in lines)
    assert any(line.split()[:2] == ["beta", "ok"] for line in lines)


def test_multirepo_serial_prints_each_member_first(mr):
    members = _members(mr, "alpha", "beta")
    for name, member in members.items():
        _add_run(member.store, "probe", f"echo ran-{name}")

    result = mr.run("multirepo", "tools", "run", "probe")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines.index("== alpha") < lines.index("ran-alpha")
    assert lines.index("ran-alpha") < lines.index("== beta")
    assert lines.index("== beta") < lines.index("ran-beta")


def test_multirepo_rm_refuses_a_worktree_of_another_origin(mr):
    members = _members(mr, "alpha", "beta")
    result = mr.run("multirepo", "tools", "worktree", "add", "topic")
    assert result.returncode == 0, result.stdout + result.stderr
    # In beta, topic is now a worktree that no set made.
    beta = str(members["beta"].store)
    _git(
        "--git-dir",
        beta,
        "config",
        "--unset",
        "project.worktree.topic.multirepo",
    )

    result = mr.run("multirepo", "tools", "worktree", "rm", "topic")

    assert result.returncode != 0
    assert "not added for multirepo set tools" in result.stdout
    for member in members.values():
        state = _state(member.store)
        assert state.branch is not None
        assert state.record
        assert state.worktree
        assert state.path


def test_multirepo_rm_ignores_a_global_multirepo_key(mr):
    members = _members(mr, "alpha", "beta")
    result = mr.run("multirepo", "tools", "worktree", "add", "topic")
    assert result.returncode == 0, result.stdout + result.stderr
    _git(
        "--git-dir",
        str(members["beta"].store),
        "config",
        "--unset",
        "project.worktree.topic.multirepo",
    )
    # libgit2 reads HOME, not GIT_CONFIG_GLOBAL.
    with open(mr.home / ".gitconfig", "a") as gitconfig:
        gitconfig.write('[project "worktree.topic"]\n\tmultirepo = tools\n')

    result = mr.run("multirepo", "tools", "worktree", "rm", "topic")

    assert result.returncode != 0
    assert "== beta" in result.stdout
    assert "not added for multirepo set tools" in result.stdout
    for member in members.values():
        assert _state(member.store).worktree


def test_multirepo_rm_keeps_only_branches_that_add_created(mr):
    members = _members(mr, "alpha", "beta")
    beta = str(members["beta"].store)
    _git("--git-dir", beta, "branch", "topic", "master")

    result = mr.run("multirepo", "tools", "worktree", "add", "topic")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "undo: worktree rm topic" in result.stdout
    assert "undo: worktree rm --keep-branch topic" in result.stdout
    assert "branchcreated" not in _state(members["beta"].store).record

    result = mr.run("multirepo", "tools", "worktree", "rm", "topic")

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_untouched(members["alpha"].store)
    state = _state(members["beta"].store)
    assert state.branch is not None
    assert str(state.branch.target) == mr.commits["beta"][-1]
    assert state.record == {}
    assert not state.worktree
    assert not state.path


def test_multirepo_rm_refuses_branchcreated_false(mr):
    members = _members(mr, "alpha", "beta")
    result = mr.run("multirepo", "tools", "worktree", "add", "topic")
    assert result.returncode == 0, result.stdout + result.stderr
    alpha = str(members["alpha"].store)
    _git(
        "--git-dir",
        alpha,
        "config",
        "project.worktree.topic.branchcreated",
        "false",
    )

    result = mr.run("multirepo", "tools", "worktree", "rm", "topic")

    assert result.returncode != 0
    assert "branchcreated set to false" in result.stdout
    for member in members.values():
        assert _state(member.store).worktree


def test_multirepo_skip_missing(mr):
    mr.define("alpha", "beta")
    alpha = mr.umbrella("alpha")

    result = mr.run(
        "multirepo", "--skip-missing", "tools", "worktree", "add", "topic"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Skipping beta" in result.stdout
    assert any(
        line.split()[:2] == ["beta", "skipped"]
        for line in result.stdout.splitlines()
    )
    assert _state(alpha.store).worktree
    assert not (mr.home / "beta").exists()


def test_multirepo_commit_maps_by_author_date(mr):
    members = _members(mr, "alpha", "beta")
    sha = mr.commits["alpha"][1]

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        sha[:12],
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    # beta's commits are at 1500, 2500 and 3500, and alpha's sha is at 2000.
    expected = {"alpha": sha, "beta": mr.commits["beta"][0]}
    for name, member in members.items():
        assert f"{name}: branch point {expected[name]}" in result.stdout
        state = _state(member.store)
        assert str(state.branch.target) == expected[name]
        assert state.record["branchcreated"] == "true"
        assert state.record["multirepo"] == "tools"


def test_multirepo_commit_takes_the_first_in_walk_order(mr, tmp_path):
    # Back from gamma's tip, the first parents reach 1500 before 1900, which
    # is newer and still before alpha's 2000.
    mr.urls["gamma"] = str(tmp_path / "remotes" / "gamma.git")
    gamma = _make_remote(
        Path(mr.urls["gamma"]), "gamma", (1000, 1900, 2500, 1500, 4000)
    )
    members = _members(mr, "alpha", "gamma")

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        mr.commits["alpha"][1],
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"gamma: branch point {gamma[3]}" in result.stdout
    assert str(_state(members["gamma"].store).branch.target) == gamma[3]


def test_multirepo_commit_without_a_candidate_refused(mr):
    members = _members(mr, "alpha", "beta")

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        mr.commits["alpha"][0],
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode != 0
    assert "No commit at or before" in result.stdout
    assert "beta" in result.stdout
    for member in members.values():
        _assert_untouched(member.store)


def test_multirepo_commit_branch_at_another_commit_refused(mr):
    members = _members(mr, "alpha", "beta")
    beta = str(members["beta"].store)
    _git("--git-dir", beta, "branch", "topic", mr.commits["beta"][2])

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        mr.commits["alpha"][1],
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode != 0
    assert "Branch topic exists at" in result.stdout
    _assert_untouched(members["alpha"].store)
    state = _state(members["beta"].store)
    assert str(state.branch.target) == mr.commits["beta"][2]
    assert state.record == {}
    assert not state.worktree


@pytest.mark.parametrize("with_branch", [False, True])
def test_multirepo_commit_ignores_a_tag_named_like_the_branch(mr, with_branch):
    members = _members(mr, "alpha", "beta")
    beta = members["beta"]
    _git("--git-dir", str(beta.store), "tag", "topic", mr.commits["beta"][2])
    if with_branch:
        _git(
            "--git-dir",
            str(beta.store),
            "branch",
            "topic",
            mr.commits["beta"][0],
        )

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        mr.commits["alpha"][1],
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    state = _state(beta.store)
    assert str(state.branch.target) == mr.commits["beta"][0]
    assert state.worktree
    head = pygit2.Repository(str(beta.root / "topic")).head
    assert head.name == "refs/heads/topic"
    assert ("branchcreated" in state.record) == (not with_branch)


def test_multirepo_commit_without_a_branch_point_refused(mr):
    members = _members(mr, "alpha", "beta")
    beta = str(members["beta"].store)
    # Neither the project branch nor HEAD names a branch that exists.
    _git("--git-dir", beta, "branch", "-m", "master", "trunk")
    _git("--git-dir", beta, "symbolic-ref", "HEAD", "refs/heads/gone")

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        mr.commits["alpha"][2],
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stdout + result.stderr
    assert (
        "Cannot find the commit worktree add would start from in beta"
        in result.stdout
    )
    _assert_untouched(members["alpha"].store)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--commit", "gamma", "abcd"], "gamma is not a member of set tools"),
        (["--commit", "alpha", "xyz!"], "is not a commit id"),
        (["--commit", "alpha", "abcdef0"], "is not a commit in alpha"),
    ],
)
def test_multirepo_commit_member_refusals(mr, args, message):
    members = _members(mr, "alpha", "beta")

    result = mr.run("multirepo", *args, "tools", "worktree", "add", "topic")

    assert result.returncode != 0
    assert message in result.stdout
    for member in members.values():
        _assert_untouched(member.store)


def test_multirepo_commit_with_committish_refused(mr):
    members = _members(mr, "alpha", "beta")

    result = mr.run(
        "multirepo",
        "--commit",
        "alpha",
        mr.commits["alpha"][1],
        "tools",
        "worktree",
        "add",
        "topic",
        "master",
    )

    assert result.returncode != 0
    assert "committish" in result.stdout
    for member in members.values():
        _assert_untouched(member.store)


def test_multirepo_commit_skipped_member_refused(mr):
    mr.define("alpha", "beta")
    beta = mr.umbrella("beta")

    result = mr.run(
        "multirepo",
        "--skip-missing",
        "--commit",
        "alpha",
        "abcd",
        "tools",
        "worktree",
        "add",
        "topic",
    )

    assert result.returncode != 0
    assert "--commit member alpha was skipped" in result.stdout
    _assert_untouched(beta.store)


# set clone and set list


def test_set_clone_missing_members(mr):
    mr.define("alpha", "beta")

    result = mr.run("set", "clone", "tools")

    assert result.returncode == 0, result.stdout + result.stderr
    setfile = multirepo._load("project")
    for name in ("alpha", "beta"):
        assert multirepo._resolve(setfile.members[name]).state == "ok"
        assert (mr.home / name / "master").is_dir()

    result = mr.run("set", "list", "tools")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.split() == [
        "tools",
        "alpha",
        "~/alpha",
        "ok",
        "beta",
        "~/beta",
        "ok",
    ]


def test_set_clone_skips_a_resolved_member(mr):
    mr.define("alpha", "beta")
    alpha = mr.umbrella("alpha")
    (alpha.store / "marker").write_text("kept\n")

    result = mr.run("set", "clone", "tools")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "already cloned" in result.stdout
    assert (alpha.store / "marker").exists()
    assert (mr.home / "beta" / "master").is_dir()


def test_set_clone_refuses_a_half_finished_root(mr):
    mr.define("alpha", "beta")
    (mr.home / "beta").mkdir()

    result = mr.run("set", "clone", "tools")

    assert result.returncode != 0
    assert "beta" in result.stdout
    assert "not a git repository" in result.stdout
    assert not (mr.home / "alpha").exists()
    assert os.listdir(mr.home / "beta") == []


def test_set_list_reports_states(mr):
    mr.define("alpha", "beta")
    mr.umbrella("alpha")
    (mr.home / "beta").mkdir()

    result = mr.run("set", "list")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "tools"
    assert lines[1].split() == ["alpha", "~/alpha", "ok"]
    assert lines[2].split()[:3] == ["beta", "~/beta", "invalid:"]


# Signals


def _wait_for(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out")
        time.sleep(0.05)


def _gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    # A zombie still answers until its parent reaps it.
    with contextlib.suppress(OSError):
        return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"
    return True


def _kill(pids):
    # A pid already gone may have been reused.
    for pid in pids:
        if _gone(pid):
            continue
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def _start(mr, tmp_path, *args, env=None):
    # Its own session, so a signal to its group acts as a terminal's would
    # and reaches no test process.
    with open(tmp_path / "out", "w") as out:
        return subprocess.Popen(
            [EXE, *args],
            cwd=mr.cwd,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )


def _sleeper(store, markers, name):
    # The shell writes its own pid and its parent's, the member's
    # git-project, then becomes the sleep.
    _add_run(
        store,
        "probe",
        f"echo $$ $PPID > {markers}/{name}.tmp && "
        f"mv {markers}/{name}.tmp {markers}/{name} && exec sleep 60",
    )


def _pids(markers, name):
    return [int(pid) for pid in (markers / name).read_text().split()]


def test_multirepo_serial_sigint_starts_no_later_member(mr, tmp_path):
    members = _members(mr, "alpha", "beta")
    markers = tmp_path / "markers"
    markers.mkdir()
    for name, member in members.items():
        _sleeper(member.store, markers, name)

    parent = _start(mr, tmp_path, "multirepo", "tools", "run", "probe")
    try:
        _wait_for((markers / "alpha").exists)
        # A Ctrl-C reaches the whole foreground group.
        os.killpg(parent.pid, signal.SIGINT)
        rc = parent.wait(timeout=60)

        # Before the cleanup below, which would kill them anyway.
        out = (tmp_path / "out").read_text()
        assert rc == 128 + signal.SIGINT, out
        assert not (markers / "beta").exists()
        assert any(
            line.split() == ["beta", "not", "run"] for line in out.splitlines()
        )
        for pid in _pids(markers, "alpha"):
            _wait_for(lambda pid=pid: _gone(pid), timeout=10)
    finally:
        parent.kill()
        for name in members:
            if (markers / name).exists():
                _kill(_pids(markers, name))


def test_multirepo_serial_sigterm_stops_the_member(mr, tmp_path):
    members = _members(mr, "alpha", "beta")
    markers = tmp_path / "markers"
    markers.mkdir()
    for name, member in members.items():
        _sleeper(member.store, markers, name)

    parent = _start(mr, tmp_path, "multirepo", "tools", "run", "probe")
    try:
        _wait_for((markers / "alpha").exists)
        # SIGTERM by pid reaches the parent alone.
        os.kill(parent.pid, signal.SIGTERM)
        rc = parent.wait(timeout=60)
    finally:
        parent.kill()
        if (markers / "alpha").exists():
            shell, member = _pids(markers, "alpha")
            # The shell became the sleep, and only the member was signalled.
            _kill([shell])

    out = (tmp_path / "out").read_text()
    assert rc == 128 + signal.SIGTERM, out
    assert not (markers / "beta").exists()
    _wait_for(lambda: _gone(member), timeout=10)
    assert any(
        line.split()[:2] == ["alpha", "killed"] for line in out.splitlines()
    )
    assert any(
        line.split() == ["beta", "not", "run"] for line in out.splitlines()
    )


def test_cancel_treats_sighup_as_sigterm():
    with multirepo._Cancel() as cancel:
        os.kill(os.getpid(), signal.SIGHUP)

    assert cancel.cancelled
    assert cancel.terminated
    assert cancel.exit_status() == 128 + signal.SIGHUP


def test_summary_gives_why_a_member_failed_to_start(tmp_path, capsys):
    task = multirepo._Task("alpha", [str(tmp_path / "missing")], str(tmp_path))

    with multirepo._Cancel() as cancel:
        multirepo._run([task], None, cancel, capture=False)
    multirepo._print_summary([task])

    row = capsys.readouterr().out.splitlines()[-1]
    assert row.startswith("alpha")
    assert "failed to start" in row
    assert "No such file or directory" in row


class _TermOnceStarted:
    """A cancel that records SIGTERM once the marker file appears."""

    def __init__(self, marker):
        self._marker = marker

    @property
    def cancelled(self):
        return self._marker.exists()

    terminated = cancelled


def test_run_serial_kills_a_member_that_ignores_sigterm(monkeypatch, tmp_path):
    monkeypatch.setattr(multirepo, "_KILL_GRACE", 0.5)
    started = tmp_path / "started"
    later = tmp_path / "later"
    script = (
        f"trap '' TERM && echo $$ > {started}.tmp && "
        f"mv {started}.tmp {started} && exec sleep 60"
    )
    stubborn = multirepo._Task("alpha", ["sh", "-c", script], str(tmp_path))
    after = multirepo._Task("beta", ["touch", str(later)], str(tmp_path))

    try:
        multirepo._run_serial(
            [stubborn, after], _TermOnceStarted(started), capture=True
        )
    finally:
        multirepo._close_outputs([stubborn, after])
        if started.exists():
            _kill([int(started.read_text())])

    assert stubborn.rc == -signal.SIGKILL
    assert _gone(int(started.read_text()))
    assert after.rc is None
    assert not later.exists()


def test_run_parallel_kills_a_group_that_outlives_its_leader(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(multirepo, "_KILL_GRACE", 0.5)
    started = tmp_path / "started"
    # The leader dies on SIGTERM, and the member it left in its group
    # ignores it.
    inner = (
        f"trap '' TERM && echo \\$\\$ > {started}.tmp && "
        f"mv {started}.tmp {started} && exec sleep 30"
    )
    script = f'sh -c "{inner}" & wait'
    task = multirepo._Task("alpha", ["sh", "-c", script], str(tmp_path))

    try:
        multirepo._run_parallel(
            [task], 1, _TermOnceStarted(started), on_done=None
        )
        # Before the cleanup below, which would kill it anyway. SIGKILL
        # lands a moment after it is sent.
        member = int(started.read_text())
        _wait_for(lambda: _gone(member), timeout=5)
    finally:
        multirepo._close_outputs([task])
        if started.exists():
            _kill([int(started.read_text())])

    assert task.rc == -signal.SIGTERM


def _finished(markers):
    return [path for path in markers.iterdir() if path.suffix != ".tmp"]


def test_multirepo_parallel_sigint_stops_every_member(mr, tmp_path):
    members = _members(mr, "alpha", "beta")
    markers = tmp_path / "markers"
    markers.mkdir()
    # worktree add runs git from the umbrella, and this git never returns.
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "git").write_text(
        "#!/bin/sh\n"
        f'echo $$ > "{markers}/$$.tmp" && mv "{markers}/$$.tmp" "{markers}/$$"\n'
        "exec sleep 60\n"
    )
    (shim / "git").chmod(0o755)
    env = dict(os.environ, PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")

    parent = _start(
        mr,
        tmp_path,
        "multirepo",
        "-j",
        "2",
        "tools",
        "worktree",
        "add",
        "topic",
        env=env,
    )
    pids = []
    try:
        # A .tmp file is a marker still being written.
        _wait_for(lambda: len(_finished(markers)) == 2)
        pids = [int(path.name) for path in _finished(markers)]
        # The members are in sessions of their own, so a Ctrl-C reaches
        # only the parent.
        os.killpg(parent.pid, signal.SIGINT)
        rc = parent.wait(timeout=60)

        # Before the cleanup below, which would kill them anyway.
        out = (tmp_path / "out").read_text()
        assert rc == 128 + signal.SIGINT, out
        for pid in pids:
            _wait_for(lambda pid=pid: _gone(pid), timeout=10)
    finally:
        parent.kill()
        _kill(pids)

    for member in members.values():
        _assert_untouched(member.store)
    lines = out.splitlines()
    for name in members:
        assert any(line.split()[:2] == [name, "killed"] for line in lines), out
