#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2020-present David A. Greene <dag@obbligato.org>

# SPDX-License-Identifier: AGPL-3.0-or-later

# Copyright 2024 David A. Greene

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

import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import common
import git_project
import pygit2
import pytest
from git_project.test_support.common import create_commit

from git_project_core_plugins import Worktree, WorktreePlugin
from git_project_core_plugins.worktree import (
    _status_paths,
    get_hidden_gitdir_name,
    get_umbrella_dir,
)


def test_worktree_add_arguments(
    reset_directory, git, gitproject, project, parser_manager, plugin_manager
):
    plugin = WorktreePlugin()

    plugin.add_arguments(
        git, gitproject, project, parser_manager, plugin_manager
    )

    worktree_add_parser = parser_manager.find_parser("worktree-add")

    worktree_add_args = [
        "path",
        "committish",
        "-b",
    ]

    common.check_args(worktree_add_parser, worktree_add_args)

    assert (
        worktree_add_parser.get_default("func").__name__
        == "command_worktree_add"
    )

    worktree_rm_parser = parser_manager.find_parser("worktree-rm")

    worktree_rm_args = [
        "name",
        "-f",
        "--keep-branch",
        "--keep-remote-branch",
    ]

    common.check_args(worktree_rm_parser, worktree_rm_args)

    assert (
        worktree_rm_parser.get_default("func").__name__
        == "command_worktree_rm"
    )


def test_worktree_modify_clone_arguments(
    reset_directory,
    git,
    gitproject,
    project,
    clone_parser_manager,
    plugin_manager,
):
    plugin = WorktreePlugin()

    plugin.modify_arguments(
        git, gitproject, project, clone_parser_manager, plugin_manager
    )

    clone_parser = clone_parser_manager.find_parser("clone")

    assert (
        clone_parser.get_default("func").__name__ == "worktree_command_clone"
    )


def test_worktree_modify_init_arguments(
    reset_directory,
    git,
    gitproject,
    project,
    init_parser_manager,
    plugin_manager,
):
    plugin = WorktreePlugin()

    plugin.modify_arguments(
        git, gitproject, project, init_parser_manager, plugin_manager
    )

    init_parser = init_parser_manager.find_parser("init")

    assert init_parser.get_default("func").__name__ == "worktree_command_init"


def test_worktree_get(
    reset_directory, git, gitproject, project, parser_manager
):
    project.builddir = "/path/to/build"

    worktree = Worktree.get(
        git, project, "test", path="/path/to/test", committish="master"
    )

    assert worktree._section == "project.worktree.test"
    assert worktree.path == "/path/to/test"
    assert worktree._pathsection.worktree == "test"
    assert worktree.committish == "master"

    assert not hasattr(worktree, "builddir")
    assert not hasattr(worktree, "prefix")


def test_worktree_get_by_path(
    reset_directory, git, gitproject, project, parser_manager
):
    worktree = Worktree.get(
        git,
        project,
        "test",
        builddir="/path/to/test",
        path="/path/to/test",
        committish="master",
    )

    assert worktree._section == "project.worktree.test"
    assert worktree.path == "/path/to/test"
    assert worktree._pathsection.worktree == "test"
    assert worktree.committish == "master"
    assert worktree.builddir == "/path/to/test"

    path_worktree = Worktree.get_by_path(git, project, worktree.path)

    assert path_worktree._section == worktree._section
    assert path_worktree._ident == worktree._ident
    assert path_worktree.path == worktree.path
    assert path_worktree.committish == worktree.committish
    assert path_worktree.builddir == worktree.builddir


def test_worktree_scope(
    reset_directory, git, gitproject, project, parser_manager
):
    project.builddir = "/path/to/build"

    worktree = Worktree.get(
        git,
        project,
        "test",
        builddir="/path/to/test",
        path="/path/to/test",
        committish="master",
    )

    assert worktree._section == "project.worktree.test"
    assert worktree.path == "/path/to/test"
    assert worktree._pathsection.worktree == "test"
    assert worktree.committish == "master"
    assert worktree.builddir == "/path/to/test"

    assert not hasattr(worktree, "prefix")

    assert project._section == "project"
    assert project.path == "/path/to/test"
    assert project.committish == "master"
    assert project.builddir == "/path/to/test"


def check_umbrella_gitdir(umbrella, hidden):
    """Assert the umbrella points at the hidden clone with a .git file.

    It has to be a file. A directory or a symlink named .git is what
    breaks a go build run from the umbrella, which is the whole reason
    the clone is hidden in the first place.
    """
    gitfile = Path(umbrella) / ".git"
    assert gitfile.is_file()
    assert gitfile.read_text() == f"gitdir: {hidden}\n"


def test_worktree_clone(git_project_runner, remote_repository):
    repo_path = Path(f".{Path(remote_repository.path).name}.git")

    git_project_runner.run(
        ".*", "", "clone", "--worktree", remote_repository.path
    )

    assert os.path.exists(repo_path)
    assert os.path.exists("master")

    check_umbrella_gitdir(Path.cwd(), repo_path.name)


def test_worktree_clone_bare(git_project_runner, remote_repository):
    git_project_runner.run(
        ".*", "", "clone", "--bare", "--worktree", remote_repository.path
    )

    repo_path = Path(f".{Path(remote_repository.path).name}.git")

    assert os.path.exists(repo_path)
    assert os.path.exists("master")

    check_umbrella_gitdir(Path.cwd(), repo_path.name)


def test_worktree_clone_path(git_project_runner, remote_repository):
    repo_path = Path.cwd() / "foo" / "bar"
    hidden = f".{Path(remote_repository.path).name}.git"

    git_project_runner.run(
        ".*", "", "clone", "--worktree", remote_repository.path, str(repo_path)
    )

    assert os.path.exists(str(repo_path / hidden))
    assert os.path.exists(repo_path / "master")

    check_umbrella_gitdir(repo_path, hidden)


def test_worktree_clone_umbrella_is_discoverable(
    git_project_runner, remote_repository
):
    """Standing in the umbrella has to answer, since that is the point."""
    git_project_runner.run(
        ".*", "", "clone", "--worktree", remote_repository.path
    )

    hidden = f".{Path(remote_repository.path).name}.git"
    umbrella = Path.cwd()

    # pygit2 reaches the clone through the pointer file.
    found = pygit2.discover_repository(str(umbrella))
    assert found is not None
    assert Path(found).resolve() == (umbrella / hidden).resolve()

    # So does git-project's own view, which is what consumers use.
    os.chdir(umbrella)
    git = git_project.Git()
    assert git.has_repo()
    assert git.is_bare_repository()


def test_worktree_init(git, git_project_runner, tmp_path_factory):
    path = tmp_path_factory.mktemp("clone-workdir")

    os.chdir(path)

    clone_path = git.clone("file://" + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    clone_url = git.get_remote_url("origin")
    workarea = git.get_working_copy_root()

    print(f"Workarea: {workarea}")

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "init", "--worktree")

    hidden = f".{Path(clone_url).parent.name}.git"

    assert os.path.exists(workarea / hidden)
    assert not os.path.exists(workarea / "MergedRemote.txt")
    assert os.path.exists(workarea / "master")

    check_umbrella_gitdir(workarea, hidden)


def _bare_clone(git, path):
    """Bare-clone the fixture to path, keeping only master, since init
    refuses a bare repository with other branches.

    """
    url = "file://" + git.get_gitdir()
    clone = git_project.Git()
    clone.clone(url, path=str(path), bare=True)
    repo = pygit2.Repository(str(path))
    for name in list(repo.branches.local):
        if name != "master":
            repo.branches.delete(name)
    return url


def test_worktree_init_bare(git, git_project_runner, tmp_path_factory):
    top = tmp_path_factory.mktemp("bare-top")
    url = _bare_clone(git, top / ".git")

    os.chdir(top)
    git_project_runner.chdir(top)

    git_project_runner.run(".*", "", "init", "--worktree")

    hidden = get_hidden_gitdir_name(url)

    assert (top / hidden).is_dir()
    assert os.path.exists(top / "master")

    check_umbrella_gitdir(top, hidden)

    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=top / "master",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert Path(common) == top / hidden


def test_worktree_init_bare_not_dot_git(
    git, git_project_runner, tmp_path_factory
):
    top = tmp_path_factory.mktemp("bare-top")
    store = top / "repo.git"
    _bare_clone(git, store)

    os.chdir(store)
    git_project_runner.chdir(store)
    git_project_runner.expect_fail = True

    git_project_runner.run(
        "git-project: Cannot initialize umbrella layout, .*repo.git is not "
        "named .git",
        "",
        "init",
        "--worktree",
    )

    assert sorted(os.listdir(top)) == ["repo.git"]


def test_worktree_init_bare_linked_worktree(
    git, git_project_runner, tmp_path_factory
):
    top = tmp_path_factory.mktemp("bare-top")
    _bare_clone(git, top / ".git")
    subprocess.run(
        ["git", "worktree", "add", "-q", "--detach", str(top / "linked")],
        cwd=top,
        check=True,
    )

    os.chdir(top)
    git_project_runner.chdir(top)
    git_project_runner.expect_fail = True

    git_project_runner.run(
        "git-project: Cannot initialize umbrella layout, .* has linked "
        "worktrees, use worktree migrate",
        "",
        "init",
        "--worktree",
    )

    assert (top / ".git").is_dir()
    assert sorted(os.listdir(top)) == [".git", "linked"]


def test_worktree_init_nonclean(git, git_project_runner):
    workarea = git.get_working_copy_root()

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    # Remove a file from the index to make it unclean.
    index = git._repo.index
    index.read()

    for entry in index:
        index.remove(entry.path)
        index.write()
        break

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.expect_fail = True

    git_project_runner.run(
        "git-project: Cannot initialize umbrella layout, working copy not clean",
        "",
        "init",
        "--worktree",
    )


def test_worktree_init_no_remote(git, git_project_runner):
    workarea = git.get_working_copy_root()
    git._repo.remotes.delete("origin")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.expect_fail = True

    git_project_runner.run(
        "git-project: Cannot initialize umbrella layout, no remote named origin",
        "",
        "init",
        "--worktree",
    )

    assert os.path.exists(workarea / "MergedRemote.txt")
    assert git_project.Git().config.get_item("core", "bare") != "true"


def test_worktree_init_main(git, git_project_runner, tmp_path_factory):
    path = tmp_path_factory.mktemp("clone-workdir")

    os.chdir(path)

    clone_path = git.clone("file://" + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    clone_url = git.get_remote_url("origin")
    workarea = git.get_working_copy_root()

    print(f"Workarea: {workarea}")

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git.create_branch("main", "master")
    git.checkout("main")
    git.delete_branch("master")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "init", "--worktree")

    assert os.path.exists(workarea / f".{Path(clone_url).parent.name}.git")
    check_umbrella_gitdir(workarea, f".{Path(clone_url).parent.name}.git")
    assert not os.path.exists(workarea / "MergedRemote.txt")
    assert os.path.exists(workarea / "main")


def test_worktree_init_main_master(git, git_project_runner, tmp_path_factory):
    path = tmp_path_factory.mktemp("clone-workdir")

    os.chdir(path)

    clone_path = git.clone("file://" + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    clone_url = git.get_remote_url("origin")
    workarea = git.get_working_copy_root()

    print(f"Workarea: {workarea}")

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git.create_branch("main", "master")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "init", "--worktree")

    assert os.path.exists(workarea / f".{Path(clone_url).parent.name}.git")
    check_umbrella_gitdir(workarea, f".{Path(clone_url).parent.name}.git")
    assert not os.path.exists(workarea / "MergedRemote.txt")
    # Prefer main over master.
    assert not os.path.exists(workarea / "master")
    assert os.path.exists(workarea / "main")


def test_worktree_init_nomain(git, git_project_runner, tmp_path_factory):
    path = tmp_path_factory.mktemp("clone-workdir")

    os.chdir(path)

    clone_path = git.clone("file://" + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    clone_url = git.get_remote_url("origin")
    workarea = git.get_working_copy_root()

    print(f"Workarea: {workarea}")

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git.create_branch("newmain", "master")
    git.checkout("newmain")
    git.delete_branch("master")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "init", "--worktree")

    assert os.path.exists(workarea / f".{Path(clone_url).parent.name}.git")
    check_umbrella_gitdir(workarea, f".{Path(clone_url).parent.name}.git")
    assert not os.path.exists(workarea / "MergedRemote.txt")
    assert not os.path.exists(workarea / "master")
    assert os.path.exists(workarea / "newmain")


def test_worktree_init_nomain_multi(git, git_project_runner, tmp_path_factory):
    path = tmp_path_factory.mktemp("clone-workdir")

    os.chdir(path)

    clone_path = git.clone("file://" + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    clone_url = git.get_remote_url("origin")
    workarea = git.get_working_copy_root()

    print(f"Workarea: {workarea}")

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git.create_branch("newmain", "master")
    git.checkout("newmain")
    git.delete_branch("master")
    git.create_branch("other", "newmain")
    git.create_branch("another", "newmain")
    git.create_branch("yetanother", "newmain")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "init", "--worktree", stdin=io.StringIO("newmain")
    )

    assert os.path.exists(workarea / f".{Path(clone_url).parent.name}.git")
    check_umbrella_gitdir(workarea, f".{Path(clone_url).parent.name}.git")
    assert not os.path.exists(workarea / "MergedRemote.txt")
    assert not os.path.exists(workarea / "master")
    assert os.path.exists(workarea / "newmain")
    assert not os.path.exists(workarea / "other")
    assert not os.path.exists(workarea / "another")
    assert not os.path.exists(workarea / "yetanother")


def test_worktree_add(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "worktree", "add", "../test", "master")

    assert os.path.exists(workarea.parent / "test")
    assert git.branch_name_to_refname("test") == "refs/heads/test"


def test_worktree_add_subdir(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test2", "master"
    )

    assert os.path.exists(workarea.parent / "user" / "test2")
    os.chdir(workarea.parent / "user" / "test2")
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == "user/test2"


def _umbrella(runner, remote_repository):
    runner.run(".*", "", "clone", "--worktree", remote_repository.path)
    top = Path.cwd().resolve()
    return SimpleNamespace(
        top=top,
        store=top / f".{Path(remote_repository.path).name}.git",
        master=top / "master",
    )


@pytest.mark.parametrize("cwd", ["", "master"])
def test_worktree_add_umbrella_relative_path(
    git_project_runner, remote_repository, cwd
):
    u = _umbrella(git_project_runner, remote_repository)
    git_project_runner.chdir(u.top / cwd)

    git_project_runner.run(".*", "", "worktree", "add", "topic")

    assert (u.top / "topic").is_dir()
    assert not (u.master / "topic").exists()


def test_worktree_add_umbrella_starts_at_project_branch(
    git_project_runner, remote_repository
):
    u = _umbrella(git_project_runner, remote_repository)
    repo = pygit2.Repository(str(u.store))
    assert repo.head_is_detached
    old = repo.head.target
    new = create_commit(repo, "refs/heads/master", [old], "Newer")

    git_project_runner.run(".*", "", "worktree", "add", "topic")

    assert repo.references["refs/heads/topic"].target == new


def test_worktree_add_umbrella_starts_at_configured_branch(
    git_project_runner, remote_repository
):
    # A project branch other than master, so the default branch fallback
    # cannot pass this test.
    u = _umbrella(git_project_runner, remote_repository)
    repo = pygit2.Repository(str(u.store))
    pushed = repo.references["refs/remotes/origin/pushed"].target
    assert pushed != repo.references["refs/heads/master"].target
    store = str(u.store)
    _out("--git-dir", store, "branch", "pushed", "origin/pushed")
    _out(
        "--git-dir",
        store,
        "config",
        "--replace-all",
        "project.branch",
        "pushed",
    )

    git_project_runner.run(".*", "", "worktree", "add", "topic")

    assert repo.references["refs/heads/topic"].target == pushed


def test_worktree_add_umbrella_absolute_path(
    git_project_runner, remote_repository, tmp_path_factory
):
    u = _umbrella(git_project_runner, remote_repository)
    target = tmp_path_factory.mktemp("elsewhere").resolve() / "topic"
    git_project_runner.chdir(u.master)

    git_project_runner.run(".*", "", "worktree", "add", str(target))

    assert target.is_dir()
    assert not (u.top / "topic").exists()
    assert not (u.master / "topic").exists()


def test_worktree_add_umbrella_committish_wins(
    git_project_runner, remote_repository
):
    u = _umbrella(git_project_runner, remote_repository)
    repo = pygit2.Repository(str(u.store))
    pushed = repo.references["refs/remotes/origin/pushed"].target
    assert pushed != repo.references["refs/heads/master"].target

    git_project_runner.run(
        ".*", "", "worktree", "add", "topic", "origin/pushed"
    )

    assert repo.references["refs/heads/topic"].target == pushed


@pytest.mark.parametrize("cwd", ["", "master"])
def test_get_umbrella_dir(git_project_runner, remote_repository, cwd):
    u = _umbrella(git_project_runner, remote_repository)
    os.chdir(u.top / cwd)

    assert get_umbrella_dir(git_project.Git()) == u.top


def test_get_umbrella_dir_outside_layout(git):
    assert get_umbrella_dir(git) is None


def test_get_umbrella_dir_bare_outside_layout(bare_git):
    assert get_umbrella_dir(bare_git) is None


def test_worktree_rm(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_rm", "master"
    )

    assert os.path.exists(workarea.parent / "user" / "test_rm")
    os.chdir(workarea.parent / "user" / "test_rm")
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == "user/test_rm"

    assert os.path.exists(workarea.parent / "user" / "test_rm")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "worktree", "rm", "test_rm")

    assert not os.path.exists(workarea.parent / "user" / "test_rm")

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert not git.committish_exists("user/test_rm")


def test_worktree_rm_unrecorded(git, git_project_runner, tmp_path_factory):
    # A worktree made by plain git has no git-project config. rm must refuse
    # it by name and must not write config for it.
    workarea = git.get_working_copy_root()
    path = workarea.parent / "user" / "test_rm_unrecorded"

    subprocess.run(
        [
            "git",
            "worktree",
            "add",
            "-q",
            "-b",
            "test_rm_unrecorded",
            str(path),
        ],
        cwd=workarea,
        check=True,
    )

    os.chdir(workarea)
    git_project_runner.chdir(workarea)
    git_project_runner.expect_fail = True

    git_project_runner.run(
        "git-project has no record of worktree test_rm_unrecorded",
        "",
        "worktree",
        "rm",
        "test_rm_unrecorded",
    )

    assert path.exists()
    config = subprocess.run(
        ["git", "config", "--list"],
        cwd=workarea,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "test_rm_unrecorded" not in config


def test_worktree_rm_unset_builddir(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()
    os.chdir(workarea)
    git = git_project.Git()  # Reinitialize in new workarea.
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_rm", "master"
    )

    # Give the worktree a prefix but no builddir. The unset builddir must not
    # stop rm before it reaches the prefix.
    prefix = tmp_path_factory.mktemp("prefix")
    section = re.sub(
        r"\.path$",
        "",
        subprocess.check_output(
            [
                "git",
                "config",
                "--name-only",
                "--get-regexp",
                r"\.worktree\.test_rm\.path$",
            ],
            text=True,
        ).strip(),
    )
    subprocess.check_call(["git", "config", f"{section}.prefix", str(prefix)])

    git_project_runner.run(".*", "", "worktree", "rm", "test_rm")

    assert not os.path.exists(workarea.parent / "user" / "test_rm")
    assert not os.path.exists(prefix)


def test_worktree_rm_keep_branch(
    git, git_project_runner, tmp_path_factory, monkeypatch
):
    # This test pushes, so it reaches a pre-push hook.  Ignore the user's git
    # configuration to keep it hermetic.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_keep_branch", "master"
    )

    assert os.path.exists(workarea.parent / "user" / "test_keep_branch")
    assert git.committish_exists("user/test_keep_branch")

    # --keep-branch keeps the branch on remotes too, so push it first or that
    # half of the promise holds no matter what rm does.  Name the destination
    # ref explicitly: the fixture remote is a mirror and also carries
    # refs/remotes/origin/*, so a bare branch name lands there instead of in
    # refs/heads, which is the only place remote_branch_exists looks.
    git_project.capture_command(
        "git push origin "
        "user/test_keep_branch:refs/heads/user/test_keep_branch"
    )

    assert git.remote_branch_exists("user/test_keep_branch", "origin")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "rm", "--keep-branch", "test_keep_branch"
    )

    assert not os.path.exists(workarea.parent / "user" / "test_keep_branch")

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert git.committish_exists("user/test_keep_branch")
    assert git.remote_branch_exists("user/test_keep_branch", "origin")


def test_worktree_rm_keep_branch_supersedes_keep_remote_branch(
    git, git_project_runner, tmp_path_factory, monkeypatch
):
    # keep_branch short-circuits the prune entirely, so keep_remote_branch
    # never gets consulted and both copies survive.  Passing both flags must
    # therefore behave exactly like --keep-branch alone, not like
    # --keep-remote-branch.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_keep_both", "master"
    )

    git_project.capture_command(
        "git push origin user/test_keep_both:refs/heads/user/test_keep_both"
    )

    assert git.remote_branch_exists("user/test_keep_both", "origin")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*",
        "",
        "worktree",
        "rm",
        "--keep-branch",
        "--keep-remote-branch",
        "test_keep_both",
    )

    assert not os.path.exists(workarea.parent / "user" / "test_keep_both")

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert git.committish_exists("user/test_keep_both")
    assert git.remote_branch_exists("user/test_keep_both", "origin")


def test_worktree_rm_unmerged_requires_force(
    git, git_project_runner, tmp_path_factory
):
    # Branch the worktree off the fixture's unmerged branch so the merge check
    # actually fires.  Every other rm test branches off master, which is
    # merged by construction.
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_rm_unmerged", "unmerged"
    )

    assert os.path.exists(workarea.parent / "user" / "test_rm_unmerged")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.expect_fail = True

    # A plain rm prunes the branch, so losing it would lose the commits.
    git_project_runner.run(
        "Worktree branch .*test_rm_unmerged is not merged, use -f to force",
        "",
        "worktree",
        "rm",
        "test_rm_unmerged",
    )

    # --keep-remote-branch keeps only the remote copy, and this branch was
    # never pushed, so the local branch is still the only copy.
    git_project_runner.run(
        "Worktree branch .*test_rm_unmerged is not merged, use -f to force",
        "",
        "worktree",
        "rm",
        "--keep-remote-branch",
        "test_rm_unmerged",
    )

    # The check runs before anything is destroyed.
    assert os.path.exists(workarea.parent / "user" / "test_rm_unmerged")

    git = git_project.Git()

    assert git.committish_exists("user/test_rm_unmerged")


def test_worktree_rm_keep_branch_unmerged(
    git, git_project_runner, tmp_path_factory
):
    # --keep-branch keeps the branch, so an unmerged branch costs nothing and
    # rm does not demand -f.
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_keep_unmerged", "unmerged"
    )

    assert os.path.exists(workarea.parent / "user" / "test_keep_unmerged")

    # Guard against a false pass.  If this branch were merged, the check under
    # test would be skipped for the wrong reason and rm would succeed anyway.
    assert not git.refname_is_merged("user/test_keep_unmerged", "master")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "rm", "--keep-branch", "test_keep_unmerged"
    )

    assert not os.path.exists(workarea.parent / "user" / "test_keep_unmerged")

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert git.committish_exists("user/test_keep_unmerged")


def test_worktree_rm_keep_remote_branch(
    git, git_project_runner, tmp_path_factory, monkeypatch
):
    # This is the only test that pushes, so it is the only one that reaches a
    # pre-push hook.  Ignore the user's git configuration to keep it hermetic.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_keep_remote", "master"
    )

    # prune_branch only deletes from a remote the branch is actually on, so
    # push it first or the assertion below holds no matter what rm does.  Name
    # the destination ref explicitly: the fixture remote is a mirror and also
    # carries refs/remotes/origin/*, so a bare branch name lands there instead
    # of in refs/heads, which is the only place remote_branch_exists looks.
    git_project.capture_command(
        "git push origin "
        "user/test_keep_remote:refs/heads/user/test_keep_remote"
    )

    assert git.remote_branch_exists("user/test_keep_remote", "origin")

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "rm", "--keep-remote-branch", "test_keep_remote"
    )

    assert not os.path.exists(workarea.parent / "user" / "test_keep_remote")

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert not git.committish_exists("user/test_keep_remote")
    assert git.remote_branch_exists("user/test_keep_remote", "origin")


def test_worktree_add_in_workarea(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "test_workarea", "master"
    )

    assert os.path.exists(workarea / "test_workarea")
    os.chdir(workarea / "test_workarea")
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == "test_workarea"


def test_worktree_rm_in_workarea(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / ".git")
    assert os.path.exists(workarea / "MergedRemote.txt")

    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "test_rm_workarea", "master"
    )

    assert os.path.exists(workarea / "test_rm_workarea")
    os.chdir(workarea / "test_rm_workarea")
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == "test_rm_workarea"

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run(".*", "", "worktree", "rm", "test_rm_workarea")

    assert not os.path.exists(workarea / "test_rm_workarea")


def test_worktree_rm_refused_artifact_removes_nothing(
    git, git_project_runner, tmp_path_factory
):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)
    git = git_project.Git()  # Reinitialize in new workarea.
    git_project_runner.chdir(workarea)

    git_project_runner.run(
        ".*", "", "worktree", "add", "../user/test_guard", "master"
    )

    worktree_path = workarea.parent / "user" / "test_guard"
    assert os.path.exists(worktree_path)

    # The main workarea is protected, so removing it is refused.
    git_project_runner.run(
        ".*", "", "artifact", "add", "worktree.test_guard", str(workarea)
    )

    git_project_runner.expect_fail = True
    git_project_runner.run(
        "Refusing to remove", "", "worktree", "rm", "test_guard"
    )
    git_project_runner.expect_fail = False

    # The refusal comes before anything is destroyed.
    git = git_project.Git()
    assert os.path.exists(worktree_path)
    assert git.committish_exists("user/test_guard")
    assert git_project.ConfigObject.exists(
        git, "project", "worktree", "test_guard"
    )
    assert os.path.exists(workarea / "MergedRemote.txt")


def test_worktree_add_requires_path(git, git_project_runner):
    workarea = git.get_working_copy_root()

    git_project_runner.chdir(workarea)

    # A usage error, not a traceback.
    git_project_runner.expect_fail = True
    git_project_runner.run(
        "", "the following arguments are required: path", "worktree", "add"
    )


def _migrate(script_runner, cwd, *args):
    return script_runner.run(
        ["git-project", "worktree", "migrate", *args], cwd=str(cwd)
    )


def _out(*args):
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def _snapshot(fc, internals=True):
    """Record the files under the fixture's base and the repository state.

    git-project rewrites the config with unchanged values on every run, so
    the config file's mtime is left out and its values are compared instead.
    With internals false, the git directory and each .git file are left out
    too. Those are git's own bookkeeping, and the rollback rewrites them.

    """
    gitdir = fc.top / ".git"
    files = []
    for dirpath, dirs, names in os.walk(fc.base):
        dirs.sort()
        root = Path(dirpath)
        if not internals and root.is_relative_to(gitdir):
            continue
        files.append((str(root.relative_to(fc.base)), "dir"))
        for name in sorted(names):
            path = root / name
            relpath = str(path.relative_to(fc.base))
            if path == gitdir / "config" or (not internals and name == ".git"):
                files.append((relpath, None))
            else:
                files.append((relpath, os.lstat(path).st_mtime_ns))
    top = str(fc.top)
    return (
        files,
        _out("-C", top, "for-each-ref"),
        _out("-C", top, "config", "--list", "--local"),
        _out("-C", top, "worktree", "list", "--porcelain"),
    )


def test_worktree_migrate_arguments(
    reset_directory, git, gitproject, project, parser_manager, plugin_manager
):
    plugin = WorktreePlugin()

    plugin.add_arguments(
        git, gitproject, project, parser_manager, plugin_manager
    )

    worktree_migrate_parser = parser_manager.find_parser("worktree-migrate")

    common.check_args(worktree_migrate_parser, ["--apply"])

    assert (
        worktree_migrate_parser.get_default("func").__name__
        == "command_worktree_migrate"
    )


def test_worktree_migrate_dry_run_changes_nothing(flat_clone, script_runner):
    fc = flat_clone
    # A literal old path in a project value is reported, by key.
    _out(
        "-C",
        str(fc.top),
        "config",
        "project.builddir",
        str(fc.topic / "build"),
    )
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top)

    assert result.success
    assert _snapshot(fc) == before
    top = fc.top
    assert f"worktree move {fc.topic} {top / 'topic'}" in result.stdout
    assert f"worktree move {fc.feature} {top / 'user-feature'}" in (
        result.stdout
    )
    assert f"rename {top / 'build'} -> {top / 'master' / 'build'}" in (
        result.stdout
    )
    assert f"rename {top / '.git'} -> {fc.store}" in result.stdout
    manifest = top / ".git" / "git-project-migrate.json"
    assert f"write {manifest}" in result.stdout
    assert f"copy {top / '.git' / 'logs' / 'HEAD'} -> " in result.stdout
    assert f"set project.worktree.master.path = {top / 'master'}" in (
        result.stdout
    )
    assert "set project.worktree.user-feature.committish = user/feature" in (
        result.stdout
    )
    assert f"warn: project.builddir holds the old path {fc.topic}" in (
        result.stdout
    )
    assert str(fc.topic / "build") not in result.stdout
    assert "Dry run, the migration changed nothing." in result.stdout


def test_worktree_migrate_warns_on_whole_paths_only(flat_clone, script_runner):
    fc = flat_clone
    for key, value in (
        ("project.unrelated", "/unrelated/build"),
        ("project.sibling", f"{fc.base}/proj-other/build"),
        ("project.backup", f"{fc.top}.bak"),
        ("project.nested", f"/mirror{fc.top}/build"),
        ("project.flags", f"--out={fc.feature} -v"),
        ("project.cflags", f"-I{fc.topic}/include"),
        # Not one migrate writes, but still a worktree path key.
        ("project.worktree.gone.path", str(fc.topic)),
    ):
        _out("-C", str(fc.top), "config", key, value)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    warnings = [
        line for line in result.stdout.splitlines() if line.startswith("warn:")
    ]
    assert warnings == [
        f"warn: project.flags holds the old path {fc.feature}",
        f"warn: project.cflags holds the old path {fc.topic}",
    ]


def test_worktree_migrate_dry_run_writes_no_config(flat_clone, script_runner):
    fc = flat_clone
    config = fc.top / ".git" / "config"
    _out("-C", str(fc.top), "config", "--remove-section", "project")
    config_before = config.read_bytes()
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert "Dry run, the migration changed nothing." in result.stdout
    assert config.read_bytes() == config_before
    files, refs, _, worktrees = _snapshot(fc)
    assert (files, refs, worktrees) == (before[0], before[1], before[3])


def _modify_main(fc):
    (fc.top / "Goodbyte.txt").write_text("changed\n")


def _stage_main(fc):
    (fc.top / "staged.txt").write_text("staged\n")
    _out("-C", str(fc.top), "add", "staged.txt")


def _untracked_main(fc):
    (fc.top / "untracked.txt").write_text("untracked\n")


def _dirty_linked(fc):
    (fc.topic / "Hello.txt").write_text("changed\n")


def _lock_linked(fc):
    _out("-C", str(fc.top), "worktree", "lock", str(fc.feature))


def _prune_linked(fc):
    shutil.rmtree(fc.feature)


def _in_progress(name, where):
    def setup(fc):
        gitdir = Path(
            _out(
                "-C", str(where(fc)), "rev-parse", "--absolute-git-dir"
            ).strip()
        )
        if name.startswith("rebase"):
            (gitdir / name).mkdir()
        else:
            (gitdir / name).write_text("0" * 40 + "\n")

    return setup


def _detach_linked(fc):
    _out("-C", str(fc.topic), "switch", "-q", "--detach")


def _main_off_main(fc):
    _out("-C", str(fc.top), "switch", "-q", "local-only")


def _skip_worktree_linked(fc):
    _out("-C", str(fc.topic), "update-index", "--skip-worktree", "Hello.txt")


def _assume_unchanged_main(fc):
    _out("-C", str(fc.top), "update-index", "--assume-unchanged", "Hello.txt")


def _worktree_config_bare(fc):
    _out("-C", str(fc.top), "config", "extensions.worktreeConfig", "true")
    _out("-C", str(fc.top), "config", "--worktree", "core.bare", "false")


def _relative_worktrees(fc):
    _out("-C", str(fc.top), "config", "core.repositoryformatversion", "1")
    _out("-C", str(fc.top), "config", "extensions.relativeWorktrees", "true")


def _use_relative_paths(fc):
    _out("-C", str(fc.top), "config", "worktree.useRelativePaths", "true")


def _core_worktree(fc):
    _out("-C", str(fc.top), "config", "core.worktree", str(fc.top))


def _core_worktree_linked(fc):
    _out("-C", str(fc.top), "config", "extensions.worktreeConfig", "true")
    _out(
        "-C",
        str(fc.topic),
        "config",
        "--worktree",
        "core.worktree",
        str(fc.topic),
    )


@pytest.mark.parametrize(
    "setup, reason",
    [
        (_modify_main, "{top} has uncommitted changes"),
        (_stage_main, "{top} has uncommitted changes"),
        (_untracked_main, "{top} has uncommitted changes"),
        (_dirty_linked, "{topic} has uncommitted changes"),
        (_lock_linked, "{feature} is locked"),
        (_prune_linked, "{feature} is prunable"),
        (
            _in_progress("MERGE_HEAD", lambda fc: fc.top),
            "{top} has MERGE_HEAD",
        ),
        (
            _in_progress("CHERRY_PICK_HEAD", lambda fc: fc.topic),
            "{topic} has CHERRY_PICK_HEAD",
        ),
        (
            _in_progress("rebase-merge", lambda fc: fc.top),
            "{top} has rebase-merge",
        ),
        (
            _in_progress("BISECT_LOG", lambda fc: fc.top),
            "{top} has BISECT_LOG",
        ),
        (_detach_linked, "{topic} has a detached HEAD"),
        (
            _main_off_main,
            "main clone has local-only checked out, not master",
        ),
        (
            _skip_worktree_linked,
            "{topic} has assume-unchanged or skip-worktree files",
        ),
        (
            _assume_unchanged_main,
            "{top} has assume-unchanged or skip-worktree files",
        ),
        (
            _worktree_config_bare,
            "{config_worktree} sets core.bare",
        ),
        (_core_worktree, "{config} sets core.worktree"),
        (_core_worktree_linked, "{topic_config} sets core.worktree"),
        (_relative_worktrees, "extensions.relativeWorktrees is true"),
        (_use_relative_paths, "worktree.useRelativePaths is true"),
    ],
)
def test_worktree_migrate_refuses(flat_clone, script_runner, setup, reason):
    fc = flat_clone
    setup(fc)
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    reason = reason.format(
        top=fc.top,
        topic=fc.topic,
        feature=fc.feature,
        config=fc.top / ".git" / "config",
        config_worktree=fc.top / ".git" / "config.worktree",
        topic_config=fc.top
        / ".git"
        / "worktrees"
        / fc.topic.name
        / "config.worktree",
    )
    assert f"refuse: {reason}" in result.stdout
    assert "worktree migrate refused" in result.stdout
    assert _snapshot(fc) == before


def test_worktree_migrate_refuses_git_config(
    flat_clone, script_runner, monkeypatch, tmp_path
):
    fc = flat_clone
    other = tmp_path / "other-config"
    before = _snapshot(fc)

    # Only for the run, since _snapshot runs git config too.
    with monkeypatch.context() as patch:
        patch.setenv("GIT_CONFIG", str(other))
        result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert "refuse: GIT_CONFIG is set" in result.stdout
    assert _snapshot(fc) == before
    assert not other.exists()


@pytest.mark.parametrize("target", ["topic", "store"])
def test_worktree_migrate_target_exists(flat_clone, script_runner, target):
    fc = flat_clone
    path = fc.top / "topic" if target == "topic" else fc.store
    # Ignored, so the only refusal is the one under test. The test id puts
    # brackets in the store name, which an exclude pattern reads as a glob.
    pattern = re.sub(r"([][*?])", r"\\\1", path.name)
    with open(fc.top / ".git" / "info" / "exclude", "a") as exclude:
        exclude.write(f"/{pattern}/\n")
    path.mkdir()
    (path / "file").write_text("in the way\n")
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert f"refuse: {path} already exists" in result.stdout
    assert result.stdout.count("refuse: ") == 1
    assert _snapshot(fc) == before


def test_worktree_migrate_reports_all_refusals(flat_clone, script_runner):
    fc = flat_clone
    _untracked_main(fc)
    _lock_linked(fc)
    _detach_linked(fc)
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert f"refuse: {fc.top} has uncommitted changes" in result.stdout
    assert f"refuse: {fc.feature} is locked" in result.stdout
    assert f"refuse: {fc.topic} has a detached HEAD" in result.stdout
    assert _snapshot(fc) == before


def _worktree_branches(store):
    records = {}
    for block in _out(
        "--git-dir", str(store), "worktree", "list", "--porcelain"
    ).split("\n\n"):
        fields = dict(
            line.partition(" ")[::2] for line in block.splitlines() if line
        )
        if fields:
            records[Path(fields["worktree"])] = fields.get("branch")
    return records


def test_worktree_migrate_apply(flat_clone, script_runner):
    fc = flat_clone
    top = fc.top
    refs = _out("-C", str(top), "for-each-ref")
    master_oid = _out("-C", str(top), "rev-parse", "master").strip()
    assert "refs/stash" in refs
    builddir = str(fc.topic / "build")
    _out("-C", str(top), "config", "project.builddir", builddir)

    result = _migrate(script_runner, top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert f"warn: project.builddir holds the old path {fc.topic}" in (
        result.stdout
    )
    assert builddir not in result.stdout
    check_umbrella_gitdir(top, fc.store.name)
    store = str(fc.store)
    assert _out("--git-dir", store, "config", "--bool", "core.bare") == (
        "true\n"
    )
    assert (fc.store / "HEAD").read_text().strip() == master_oid
    assert _out("--git-dir", store, "for-each-ref") == refs

    assert _worktree_branches(fc.store) == {
        fc.store: None,
        top / "master": "refs/heads/master",
        top / "topic": "refs/heads/topic",
        top / "user-feature": "refs/heads/user/feature",
    }
    for name in ("master", "topic", "user-feature"):
        assert _out("-C", str(top / name), "status", "--porcelain") == ""

    main = top / "master"
    assert (main / "build" / "out.o").read_text() == "object\n"
    assert (main / ".venv" / "marker").read_text() == "venv\n"
    _out("-C", str(main), "check-ignore", "-q", "build/out.o")
    assert (main / "Hello.txt").exists()
    assert not (top / "Hello.txt").exists()
    assert not fc.topic.exists()
    assert not fc.feature.exists()

    for name, branch in (
        ("master", "master"),
        ("topic", "topic"),
        ("user-feature", "user/feature"),
    ):
        path = top / name
        section = f"project.worktree.{name}"
        assert _out("--git-dir", store, "config", f"{section}.path") == (
            f"{path}\n"
        )
        assert _out("--git-dir", store, "config", f"{section}.committish") == (
            f"{branch}\n"
        )
        assert _out(
            "--git-dir",
            store,
            "config",
            f"project.worktreepath.{path}.worktree",
        ) == (f"{name}\n")

    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert manifest["complete"] is True
    assert manifest["steps_done"][-1] == "verify"


def test_worktree_migrate_apply_writes_defaults(flat_clone, script_runner):
    fc = flat_clone
    _out("-C", str(fc.top), "config", "--remove-section", "project")

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    store = str(fc.store)
    assert _out(
        "--git-dir", store, "config", "--get-all", "project.branch"
    ) == ("master\n")
    assert _out(
        "--git-dir", store, "config", "--get-all", "project.remote"
    ) == ("origin\n")


@pytest.mark.parametrize("cwd", ["", "master"])
def test_worktree_migrate_twice_refuses(flat_clone, script_runner, cwd):
    fc = flat_clone
    assert _migrate(script_runner, fc.top, "--apply").success
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top / cwd, "--apply")

    assert not result.success
    assert "already converted or not a main clone" in result.stdout
    assert _snapshot(fc) == before


def test_worktree_migrate_existing_worktree_config(flat_clone, script_runner):
    fc = flat_clone
    top = str(fc.top)
    old = f"project.worktreepath.{fc.feature}.worktree"
    _out("-C", top, "config", "project.worktree.feat.path", str(fc.feature))
    _out(
        "-C", top, "config", "project.worktree.feat.committish", "user/feature"
    )
    _out("-C", top, "config", "project.worktree.feat.builddir", "/b/feat")
    _out("-C", top, "config", old, "feat")

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert f"stale: {old} names an old path" in result.stdout
    new = fc.top / "user-feature"
    assert _out("-C", top, "config", "project.worktree.feat.path") == (
        f"{new}\n"
    )
    assert _out("-C", top, "config", "project.worktree.feat.builddir") == (
        "/b/feat\n"
    )
    assert _out(
        "-C", top, "config", f"project.worktreepath.{new}.worktree"
    ) == ("feat\n")
    # The stale entry is reported, not removed.
    assert _out("-C", top, "config", old) == "feat\n"
    assert "project.worktree.user-feature." not in _out(
        "-C", top, "config", "--list", "--local"
    )


def _unpushed(result):
    return [
        line
        for line in result.stdout.splitlines()
        if line.startswith("unpushed:")
    ]


def test_worktree_migrate_lists_unpushed(flat_clone, script_runner):
    fc = flat_clone
    top = str(fc.top)
    commit = ("-c", "user.name=Test", "-c", "user.email=test@example.com")
    _out(
        "-C", str(fc.topic), "branch", "-q", "--set-upstream-to=origin/pushed"
    )
    for n in range(2):
        _out(
            "-C",
            str(fc.topic),
            *commit,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            f"topic {n}",
        )
    # The same change as user/feature under another id, so git cherry marks
    # it "-" and the branch has nothing unpushed.
    repo = pygit2.Repository(top)
    feature = repo.revparse_single("refs/heads/user/feature")
    signature = pygit2.Signature("Other", "other@example.com")
    repo.create_commit(
        "refs/heads/picked",
        signature,
        signature,
        "Picked",
        feature.tree_id,
        [feature.parent_ids[0]],
    )
    _out("-C", top, "branch", "-q", "--set-upstream-to=user/feature", "picked")
    # A tag of the same name must not turn the branch into heads/topic.
    _out("-C", top, "tag", "topic", "master")
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert _snapshot(fc) == before
    # Without an upstream, a branch is compared with master.
    assert _unpushed(result) == [
        "unpushed: local-only has 1 commit not on master",
        "unpushed: topic has 2 commits not on origin/pushed",
        "unpushed: user/feature has 1 commit not on master",
    ]


def test_worktree_migrate_unpushed_gone_upstream(flat_clone, script_runner):
    fc = flat_clone
    top = str(fc.top)
    _out("-C", top, "config", "branch.local-only.remote", "origin")
    _out("-C", top, "config", "branch.local-only.merge", "refs/heads/gone")

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert "unpushed: local-only has 1 commit not on master" in (
        _unpushed(result)
    )


def test_worktree_migrate_unpushed_cannot_compare(
    flat_clone, script_runner, monkeypatch
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    real = worktree_module._git_or_none

    def failing_cherry(*args):
        if "cherry" in args:
            return None
        return real(*args)

    monkeypatch.setattr(worktree_module, "_git_or_none", failing_cherry)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert _unpushed(result) == [
        "unpushed: cannot compare local-only with master",
        "unpushed: cannot compare master with origin/master",
        "unpushed: cannot compare topic with master",
        "unpushed: cannot compare user/feature with master",
    ]


def test_worktree_migrate_no_main_branch_refuses_first(
    flat_clone, script_runner
):
    fc = flat_clone
    _drop_main_branch(fc.top, fc.top / ".git")
    _out("-C", str(fc.top), "config", "project.postmigrate", "'unbalanced")

    result = _migrate(script_runner, fc.top)

    assert not result.success
    assert "refuse: cannot determine the main branch" in result.stdout
    # The refusal stops the plan before the hook and the unpushed list.
    assert "postmigrate" not in result.stdout
    assert _unpushed(result) == []


def _post_script(base):
    """Write a script that records its directory and arguments."""
    script = base / "post.py"
    script.write_text(
        "import json, os, sys\n"
        "with open(sys.argv[1], 'w') as file:\n"
        "    json.dump([os.getcwd(), sys.argv[2:]], file)\n"
    )
    return script


def test_worktree_migrate_post_hook(flat_clone, script_runner):
    fc = flat_clone
    record = fc.base / "post.json"
    command = [sys.executable, str(_post_script(fc.base)), str(record)]
    hook = shlex.join([*command, "one", "two words"])
    _out("-C", str(fc.top), "config", "project.postmigrate", hook)

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert json.loads(record.read_text()) == [
        str(fc.top),
        ["one", "two words"],
    ]
    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert manifest["post"] == {"status": "ok"}


def test_worktree_migrate_dry_run_skips_post_hook(flat_clone, script_runner):
    fc = flat_clone
    record = fc.base / "post.json"
    hook = shlex.join(
        [sys.executable, str(_post_script(fc.base)), str(record)]
    )
    _out("-C", str(fc.top), "config", "project.postmigrate", hook)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    origin = f"file:{fc.top / '.git' / 'config'}"
    assert (
        f"run the command in project.postmigrate from {origin}, in {fc.top}"
        in result.stdout
    )
    assert hook not in result.stdout
    assert not record.exists()


@pytest.mark.parametrize(
    "command, error",
    [
        (
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            "failed with status 3",
        ),
        (["/nonexistent/post-hook"], "could not start"),
        (
            [sys.executable, "-c", "import os; os.kill(os.getpid(), 9)"],
            "was killed by signal 9",
        ),
    ],
    ids=["status", "missing", "signal"],
)
def test_worktree_migrate_post_hook_fails(
    flat_clone, script_runner, command, error
):
    fc = flat_clone
    _out(
        "-C",
        str(fc.top),
        "config",
        "project.postmigrate",
        shlex.join(command),
    )

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    output = result.stdout + result.stderr
    message = f"the command in project.postmigrate {error}"
    assert message in output
    assert output.index(f"Migrated {fc.top}.") < output.index(message)
    assert shlex.join(command) not in output
    # The migration stands.
    check_umbrella_gitdir(fc.top, fc.store.name)
    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert manifest["complete"] is True
    assert manifest["post"]["status"].startswith(error)


def _spawning_hook(base, ignore_term=False, child_cleans=False):
    """Return a hook that starts a child and then sleeps.

    The child writes "grandchild" after 3 seconds, so the file shows whether
    it outlived a kill. The hook writes "spawned" once the child exists.
    With ignore_term, both ignore SIGTERM. With child_cleans, the child
    writes "cleaned" half a second after a SIGTERM, then exits.

    """
    files = SimpleNamespace(
        marker=base / "grandchild",
        spawned=base / "spawned",
        cleaned=base / "cleaned",
    )
    child = base / "child.py"
    child.write_text(
        "import signal, sys, time\n"
        "def term(*args):\n"
        "    time.sleep(0.5)\n"
        f"    open({str(files.cleaned)!r}, 'w').close()\n"
        "    sys.exit(0)\n"
        + ("signal.signal(signal.SIGTERM, term)\n" if child_cleans else "")
        + "time.sleep(3)\n"
        f"open({str(files.marker)!r}, 'w').close()\n"
    )
    script = base / "spawn.py"
    script.write_text(
        "import signal, subprocess, sys, time\n"
        + (
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            if ignore_term
            else ""
        )
        + f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
        f"open({str(files.spawned)!r}, 'w').close()\n"
        "time.sleep(30)\n"
    )
    files.command = [sys.executable, str(script)]
    return files


def _wait_for(path):
    for _ in range(100):
        if path.exists():
            return
        time.sleep(0.1)


def _wait_out_grandchild():
    # Longer than the child's delay, so a survivor has written its file.
    time.sleep(4)


def _set_hook(fc, command, timeout=None):
    top = str(fc.top)
    _out("-C", top, "config", "project.postmigrate", shlex.join(command))
    if timeout is not None:
        _out("-C", top, "config", "project.postmigratetimeout", timeout)


def _post_status(fc):
    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert manifest["complete"] is True
    return manifest["post"]["status"]


def test_worktree_migrate_post_hook_timeout(flat_clone, script_runner):
    fc = flat_clone
    hook = _spawning_hook(fc.base)
    _set_hook(fc, hook.command, timeout="1")

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    reason = "timed out after 1 seconds"
    assert f"the command in project.postmigrate {reason}" in (
        result.stdout + result.stderr
    )
    assert _post_status(fc) == reason
    assert hook.spawned.exists()
    _wait_out_grandchild()
    assert not hook.marker.exists()


def test_worktree_migrate_post_hook_ignores_sigterm(
    flat_clone, script_runner, monkeypatch
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    monkeypatch.setattr(worktree_module, "_POST_KILL_GRACE", 0.5)
    hook = _spawning_hook(fc.base, ignore_term=True)
    _set_hook(fc, hook.command, timeout="1")

    began = time.monotonic()
    result = _migrate(script_runner, fc.top, "--apply")

    # Only SIGKILL stops the hook before its 30 second sleep ends.
    assert time.monotonic() - began < 15
    assert not result.success
    assert "the command in project.postmigrate timed out after 1 seconds" in (
        result.stdout + result.stderr
    )
    assert hook.spawned.exists()
    _wait_out_grandchild()
    assert not hook.marker.exists()


def test_worktree_migrate_post_hook_group_gets_grace(
    flat_clone, script_runner
):
    fc = flat_clone
    hook = _spawning_hook(fc.base, child_cleans=True)
    _set_hook(fc, hook.command, timeout="1")

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert hook.spawned.exists()
    # The hook dies on SIGTERM at once. Its child still gets time to clean
    # up before the SIGKILL.
    assert hook.cleaned.exists()
    assert not hook.marker.exists()


def _interrupting_popen(module, command, spawned, in_grace=False):
    """Return a Popen whose wait for the hook raises KeyboardInterrupt once
    the hook's child exists, standing in for a Ctrl-C. With in_grace, the
    wait in the SIGTERM grace raises too.

    """

    class InterruptedPopen(subprocess.Popen):
        interrupted = False

        def wait(self, timeout=None):
            if self.args == command:
                if not InterruptedPopen.interrupted:
                    InterruptedPopen.interrupted = True
                    _wait_for(spawned)
                    raise KeyboardInterrupt
                if in_grace and timeout == module._POST_KILL_GRACE:
                    raise KeyboardInterrupt
            return super().wait(timeout)

    return InterruptedPopen


@pytest.mark.parametrize("in_grace", [False, True], ids=["once", "twice"])
def test_worktree_migrate_post_hook_interrupted(
    flat_clone, script_runner, monkeypatch, in_grace
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    # Ignoring SIGTERM, so a second Ctrl-C leaves only the SIGKILL to stop
    # it.
    hook = _spawning_hook(fc.base, ignore_term=in_grace)
    _set_hook(fc, hook.command)
    monkeypatch.setattr(
        worktree_module.subprocess,
        "Popen",
        _interrupting_popen(
            worktree_module, hook.command, hook.spawned, in_grace
        ),
    )

    began = time.monotonic()
    try:
        result = _migrate(script_runner, fc.top, "--apply")
    except KeyboardInterrupt:
        # Fail the test, not the whole session.
        pytest.fail("a Ctrl-C escaped migrate")

    assert time.monotonic() - began < 15
    assert not result.success
    assert "the command in project.postmigrate was interrupted" in (
        result.stdout + result.stderr
    )
    assert _post_status(fc) == "was interrupted"
    assert hook.spawned.exists()
    _wait_out_grandchild()
    assert not hook.marker.exists()


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "1.5", "soon", "", "86401", "1" + "0" * 400],
    ids=["zero", "negative", "fraction", "word", "empty", "day+1", "huge"],
)
def test_worktree_migrate_refuses_bad_post_timeout(
    flat_clone, script_runner, value
):
    fc = flat_clone
    _out("-C", str(fc.top), "config", "project.postmigratetimeout", value)
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert (
        "refuse: project.postmigratetimeout is not a whole number of seconds "
        "from 1 to 86400" in result.stdout
    )
    assert _snapshot(fc) == before


def test_worktree_migrate_post_hook_largest_timeout(flat_clone, script_runner):
    fc = flat_clone
    _set_hook(fc, [sys.executable, "-c", "pass"], timeout="86400")

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert _post_status(fc) == "ok"


def test_worktree_migrate_post_hook_bad_manifest(
    flat_clone, script_runner, monkeypatch
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    _set_hook(fc, [sys.executable, "-c", "pass"])
    manifest_path = fc.store / "git-project-migrate.json"
    run_hook = worktree_module._run_post_hook

    # Something rewrote the manifest as a list while the hook ran.
    def replace_manifest(plan):
        manifest_path.write_text("[]\n")
        return run_hook(plan)

    monkeypatch.setattr(worktree_module, "_run_post_hook", replace_manifest)

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert f"warn: cannot record the hook result in {manifest_path}" in (
        result.stdout
    )


def test_worktree_migrate_post_hook_without_origin(
    flat_clone, script_runner, monkeypatch
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    _set_hook(fc, [sys.executable, "-c", "pass"])
    real = worktree_module._git_or_none

    def no_origin(*args):
        if "--show-origin" in args:
            return None
        return real(*args)

    monkeypatch.setattr(worktree_module, "_git_or_none", no_origin)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert (
        f"run the command in project.postmigrate, in {fc.top}" in result.stdout
    )


@pytest.mark.parametrize(
    "value, reason",
    [("'unbalanced", "is not a valid command"), ("", "is empty")],
)
def test_worktree_migrate_refuses_bad_post_hook(
    flat_clone, script_runner, value, reason
):
    fc = flat_clone
    _out("-C", str(fc.top), "config", "project.postmigrate", value)
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert f"refuse: project.postmigrate {reason}" in result.stdout
    assert _snapshot(fc) == before


def _rollback(manifest):
    """Follow the manual rollback in the worktree help."""
    done = set(manifest["steps_done"])
    # A hard stop leaves no failed_step.
    pending = manifest.get("failed_step") or manifest["current_step"]
    top = Path(manifest["top"])
    gitdir = manifest["store_old"]
    store_new = Path(manifest["store_new"])
    main = Path(manifest["main"]["new"])
    linked = manifest["linked"]

    def undo(step, is_done=True):
        return step in done or (step == pending and is_done)

    if undo("write_pointer", (top / ".git").is_file()):
        os.unlink(top / ".git")
    if undo("rename_store", store_new.exists()):
        os.rename(store_new, gitdir)
        _out("-C", str(top), "worktree", "repair", *[w["new"] for w in linked])
    if undo("detach_head"):
        _out("--git-dir", gitdir, "symbolic-ref", "HEAD", manifest["head_ref"])
    bare = subprocess.run(
        ["git", "--git-dir", gitdir, "config", "core.bare"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    if undo("set_bare", bare.strip() == "true"):
        if manifest["core_bare"] is None:
            _out("--git-dir", gitdir, "config", "--unset", "core.bare")
        else:
            _out(
                "--git-dir",
                gitdir,
                "config",
                "core.bare",
                manifest["core_bare"],
            )
    for entry in manifest["main_entries"]:
        if undo(f"move_entry {entry}", os.path.lexists(main / entry)):
            os.rename(main / entry, top / entry)
    if undo("add_main", main.exists()):
        Path(main / ".git").unlink(missing_ok=True)
        os.rmdir(main)
        _out("-C", str(top), "worktree", "prune")
    moved = [
        w
        for w in linked
        if undo(f"move_linked {Path(w['new']).name}", Path(w["new"]).exists())
    ]
    for w in moved:
        _out("-C", str(top), "worktree", "repair", w["new"])
        _out("-C", str(top), "worktree", "move", w["new"], w["old"])
    if moved:
        _out("-C", str(top), "worktree", "repair", *[w["old"] for w in moved])
    if undo("write_config"):
        for write in manifest["config_writes"]:
            if write["prior"] is None:
                # A key the failed step did not reach is already unset.
                subprocess.run(
                    ["git", "-C", str(top), "config", "--unset", write["key"]],
                    check=False,
                    capture_output=True,
                )
            else:
                _out("-C", str(top), "config", write["key"], write["prior"])
    for name in ("git-project-migrate.json", "git-project-migrate.json.tmp"):
        Path(top / ".git" / name).unlink(missing_ok=True)


def _fail_git(*tokens, nth=1):
    """Fail the nth _git call whose arguments hold every token."""

    def inject(monkeypatch, module):
        real_git = module._git
        calls = []

        def failing_git(*args):
            if all(token in args for token in tokens):
                calls.append(args)
                if len(calls) == nth:
                    raise Exception("injected git failure")
            return real_git(*args)

        monkeypatch.setattr(module, "_git", failing_git)

    return inject


def _fail_rename(name):
    """Fail the os.rename of a path with this name."""

    def inject(monkeypatch, module):
        real_rename = os.rename

        def failing_rename(src, dst, *args, **kwargs):
            if Path(src).name == name:
                raise OSError("injected rename failure")
            return real_rename(src, dst, *args, **kwargs)

        monkeypatch.setattr(module.os, "rename", failing_rename)

    return inject


def _half_move(nth):
    """Stop the nth worktree move after the directory moves but before git
    records the new path, as a hard stop inside git worktree move would.

    """

    def inject(monkeypatch, module):
        real_git = module._git
        calls = []

        def half_moving_git(*args):
            if "worktree" in args and "move" in args:
                calls.append(args)
                if len(calls) == nth:
                    os.rename(args[-2], args[-1])
                    raise Exception("injected stop inside worktree move")
            return real_git(*args)

        monkeypatch.setattr(module, "_git", half_moving_git)

    return inject


def _fail_copy(monkeypatch, module):
    def failing_copy(*args, **kwargs):
        raise OSError("injected copy failure")

    monkeypatch.setattr(module.shutil, "copy2", failing_copy)


def _fail_write_pointer(monkeypatch, module):
    def failing_write(*args):
        raise OSError("injected write_pointer failure")

    monkeypatch.setattr(module, "write_umbrella_gitdir", failing_write)


def _fail_journal(step):
    """Fail every manifest write once step is done, as a hard stop between
    the step and its journal entry would.

    """

    def inject(monkeypatch, module):
        real_write = module._write_manifest

        def failing_write(path, manifest):
            if manifest["steps_done"][-1:] == [step]:
                raise OSError("injected journal failure")
            return real_write(path, manifest)

        monkeypatch.setattr(module, "_write_manifest", failing_write)

    return inject


def _fail_repair(monkeypatch, module):
    real_git = module._git

    def failing_git(*args):
        if "repair" in args:
            raise Exception("injected repair failure")
        return real_git(*args)

    monkeypatch.setattr(module, "_git", failing_git)


def _fail_write_config(monkeypatch, module):
    # Fail on the second worktree, so the first one's keys are already set.
    real_get = module.Worktree.get
    calls = []

    def failing_get(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise Exception("injected write_config failure")
        return real_get(*args, **kwargs)

    monkeypatch.setattr(module.Worktree, "get", failing_get)


def _fail_verify(monkeypatch, module):
    def failing_verify(*args):
        raise Exception("injected verify failure")

    monkeypatch.setattr(module, "_verify", failing_verify)


@pytest.mark.parametrize(
    "inject, failed, last_done, caught",
    [
        (
            _fail_git("worktree", "move", nth=2),
            "move_linked topic",
            "move_linked user-feature",
            True,
        ),
        (
            _half_move(nth=2),
            "move_linked topic",
            "move_linked user-feature",
            True,
        ),
        (_fail_git("--no-checkout"), "add_main", "move_linked topic", True),
        (_fail_copy, "copy_main_state", "add_main", True),
        (
            _fail_rename("Goodbyte.txt"),
            "move_entry Goodbyte.txt",
            "move_entry .venv",
            True,
        ),
        (_fail_git("reset"), "reset_index", "move_entry build", True),
        (_fail_git("core.bare", "true"), "set_bare", "reset_index", True),
        (_fail_git("update-ref"), "detach_head", "set_bare", True),
        (_fail_rename(".git"), "rename_store", "detach_head", True),
        (_fail_write_pointer, "write_pointer", "rename_store", True),
        (_fail_repair, "repair", "write_pointer", True),
        (_fail_write_config, "write_config", "repair", True),
        (_fail_verify, "verify", "write_config", True),
        # The step is done but its journal entry is not.
        (
            _fail_journal("move_entry Hello.txt"),
            "move_entry Hello.txt",
            "move_entry Goodbyte.txt",
            False,
        ),
        (_fail_journal("rename_store"), "rename_store", "detach_head", False),
    ],
)
def test_worktree_migrate_stops_on_failure(
    flat_clone, script_runner, monkeypatch, inject, failed, last_done, caught
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    top = fc.top
    before = _snapshot(fc, internals=False)

    with monkeypatch.context() as patch:
        inject(patch, worktree_module)
        result = _migrate(script_runner, top, "--apply")

    assert not result.success
    store = fc.store if fc.store.is_dir() else top / ".git"
    manifest_path = store / "git-project-migrate.json"
    assert f"failed at step {failed}" in result.stdout
    assert str(manifest_path) in result.stdout
    assert "Manual rollback" in result.stdout
    manifest = json.loads(manifest_path.read_text())
    assert manifest["current_step"] == failed
    assert manifest.get("failed_step") == (failed if caught else None)
    assert manifest["steps_done"][-1] == last_done
    assert manifest["complete"] is False

    _rollback(manifest)

    assert _snapshot(fc, internals=False) == before
    assert _out("-C", str(top), "status", "--porcelain") == ""
    assert not os.path.lexists(fc.store)


@pytest.mark.parametrize(
    "status, paths",
    [
        ("?? a\0", ["a"]),
        ("R  new\0old\0", ["new"]),
        (" R new\0old\0", ["new"]),
        ("C  new\0old\0", ["new"]),
        ("R  new\0Rold\0?? a\0", ["new", "a"]),
    ],
)
def test_worktree_status_paths(status, paths):
    assert _status_paths(status) == paths


def test_worktree_migrate_verify_names_dirty_paths(
    flat_clone, script_runner, monkeypatch
):
    from git_project_core_plugins import worktree as worktree_module

    fc = flat_clone
    real_verify = worktree_module._verify
    names = [f"stray{i:02}" for i in range(12)]

    # Dirty main after the precheck, as a stray editor file would.
    def dirtying_verify(plan, worktrees):
        for name in names:
            (worktrees[0].new / name).write_text("stray\n")
        return real_verify(plan, worktrees)

    with monkeypatch.context() as patch:
        patch.setattr(worktree_module, "_verify", dirtying_verify)
        result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert "failed at step verify: verify failed: " in result.stdout
    assert "is not clean: stray00, stray01" in result.stdout
    assert "stray09 and 2 more" in result.stdout
    assert "stray10" not in result.stdout
    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert "stray00" in manifest["error"]


def test_worktree_migrate_bare_at_root_dry_run(
    bare_at_root_clone, script_runner
):
    fc = bare_at_root_clone
    gitdir = fc.top / ".git"
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert _snapshot(fc) == before
    assert f"write {fc.commondir}: ../.." in result.stdout
    assert f"rename {gitdir} -> {fc.store}" in result.stdout
    assert f"write {gitdir}: gitdir: {fc.store.name}" in result.stdout
    assert f"worktree repair {fc.master} {fc.topic}" in result.stdout
    # Already relative, so left alone.
    assert "worktrees/master/commondir" not in result.stdout
    assert "Dry run, the migration changed nothing." in result.stdout


def test_worktree_migrate_bare_at_root_dry_run_unpushed_and_hook(
    bare_at_root_clone, script_runner
):
    fc = bare_at_root_clone
    record = fc.base / "post.json"
    hook = shlex.join(
        [sys.executable, str(_post_script(fc.base)), str(record)]
    )
    _out("-C", str(fc.top), "config", "project.postmigrate", hook)

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    assert "unpushed: topic has 1 commit not on master" in _unpushed(result)
    origin = f"file:{fc.top / '.git' / 'config'}"
    assert (
        f"run the command in project.postmigrate from {origin}, in {fc.top}"
        in result.stdout
    )
    assert hook not in result.stdout
    assert not record.exists()


def test_worktree_migrate_bare_at_root_post_hook(
    bare_at_root_clone, script_runner
):
    fc = bare_at_root_clone
    record = fc.base / "post.json"
    command = [sys.executable, str(_post_script(fc.base)), str(record), "x"]
    _out(
        "-C", str(fc.top), "config", "project.postmigrate", shlex.join(command)
    )

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert json.loads(record.read_text()) == [str(fc.top), ["x"]]
    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert manifest["form"] == "bare_at_root"
    assert manifest["complete"] is True
    assert manifest["post"] == {"status": "ok"}


def _drop_main_branch(top, gitdir):
    """Rename master and unset project.branch, so no main branch exists
    among two or more branches.

    """
    _out("-C", str(top), "branch", "-m", "master", "trunk")
    _out("--git-dir", str(gitdir), "config", "--unset-all", "project.branch")


def test_worktree_migrate_bare_at_root_no_main_branch(
    bare_at_root_clone, script_runner
):
    fc = bare_at_root_clone
    gitdir = fc.top / ".git"
    _drop_main_branch(fc.master, gitdir)
    _out("-C", str(fc.topic), "branch", "-q", "--set-upstream-to=pushed")
    _out(
        "-C",
        str(fc.topic),
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "topic",
    )

    result = _migrate(script_runner, fc.top)

    assert result.success, result.stdout + result.stderr
    # Branches with no upstream have no main branch to compare with.
    assert _unpushed(result) == ["unpushed: topic has 1 commit not on pushed"]
    assert f"rename {gitdir} -> {fc.store}" in result.stdout


@pytest.mark.parametrize("cwd", ["", "topic"])
def test_worktree_migrate_bare_at_root_apply(
    bare_at_root_clone, script_runner, cwd
):
    fc = bare_at_root_clone
    top = fc.top
    refs = _out("-C", str(top), "for-each-ref")
    config = _out("-C", str(top), "config", "--list", "--local")

    result = _migrate(script_runner, top / cwd, "--apply")

    assert result.success, result.stdout + result.stderr
    check_umbrella_gitdir(top, fc.store.name)
    store = str(fc.store)
    assert _out("--git-dir", store, "config", "--bool", "core.bare") == (
        "true\n"
    )
    assert _out("--git-dir", store, "for-each-ref") == refs
    assert _worktree_branches(fc.store) == {
        fc.store: None,
        fc.master: "refs/heads/master",
        fc.topic: "refs/heads/topic",
    }
    for path in (fc.master, fc.topic):
        assert _out("-C", str(path), "status", "--porcelain") == ""
        assert (
            _out("-C", str(path), "rev-parse", "--git-common-dir").strip()
            == store
        )
    admin = fc.store / "worktrees"
    for name in ("master", "topic"):
        assert (admin / name / "commondir").read_text() == "../..\n"
    # No worktree moved, so the config is as it was.
    assert _out("-C", str(top), "config", "--list", "--local") == config

    manifest = json.loads((fc.store / "git-project-migrate.json").read_text())
    assert manifest["form"] == "bare_at_root"
    assert manifest["complete"] is True
    assert manifest["steps_done"][-1] == "verify"


def test_worktree_migrate_bare_at_root_twice_refuses(
    bare_at_root_clone, script_runner
):
    fc = bare_at_root_clone
    assert _migrate(script_runner, fc.top, "--apply").success
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert "already converted or not a main clone" in result.stdout
    assert _snapshot(fc) == before


def _bare_outside(fc):
    path = fc.base / "outside"
    _out("--git-dir", str(fc.top / ".git"), "worktree", "add", "-q", str(path))
    return f"{path} is outside {fc.top}"


def _bare_dirty(fc):
    (fc.topic / "Goodbyte.txt").write_text("changed\n")
    return f"{fc.topic} has uncommitted changes"


def _bare_foreign_commondir(fc):
    # A working copy, so only the commondir check refuses it.
    other = fc.base / "other.git"
    shutil.copytree(fc.top / ".git", other, symlinks=True)
    fc.commondir.write_text(f"{other}\n")
    return f"{fc.commondir} names another repository"


def _bare_no_worktrees(fc):
    for path in (fc.master, fc.topic):
        _out(
            "--git-dir", str(fc.top / ".git"), "worktree", "remove", str(path)
        )
    return f"{fc.top / '.git'} has no worktrees"


def _bare_inside_store(fc):
    path = fc.top / ".git" / "inner"
    gitdir = str(fc.top / ".git")
    _out("--git-dir", gitdir, "worktree", "add", "-q", "-b", "b1", str(path))
    return f"{path} is inside {fc.top / '.git'}"


def _bare_store_exists(fc):
    fc.store.mkdir()
    return f"{fc.store} already exists"


def _bare_detached(fc):
    _out("-C", str(fc.topic), "checkout", "-q", "--detach")
    return f"{fc.topic} has a detached HEAD"


def _bare_stray_entry(fc):
    (fc.top / "README").write_text("stray\n")
    return f"{fc.top / 'README'} is not a worktree"


def _bare_nested_stray(fc):
    path = fc.top / "x" / "b1"
    gitdir = str(fc.top / ".git")
    _out("--git-dir", gitdir, "worktree", "add", "-q", "-b", "b1", str(path))
    (fc.top / "x" / "junk").write_text("stray\n")
    return f"{fc.top / 'x' / 'junk'} is not a worktree"


def _bare_nested_missing(fc):
    path = fc.top / "x" / "b1"
    gitdir = str(fc.top / ".git")
    _out("--git-dir", gitdir, "worktree", "add", "-q", "-b", "b1", str(path))
    shutil.rmtree(fc.top / "x")
    return f"cannot read {fc.top / 'x'}"


@pytest.mark.parametrize(
    "setup",
    [
        _bare_nested_missing,
        _bare_nested_stray,
        _bare_outside,
        _bare_dirty,
        _bare_foreign_commondir,
        _bare_no_worktrees,
        _bare_inside_store,
        _bare_store_exists,
        _bare_detached,
        _bare_stray_entry,
    ],
)
def test_worktree_migrate_bare_at_root_refuses(
    bare_at_root_clone, script_runner, setup
):
    fc = bare_at_root_clone
    reason = setup(fc)
    before = _snapshot(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert not result.success
    assert f"refuse: {reason}" in result.stdout
    assert _snapshot(fc) == before


def _fail_replace(name):
    """Fail the os.replace onto a path with this name."""

    def inject(monkeypatch, module):
        real_replace = os.replace

        def failing_replace(src, dst, *args, **kwargs):
            if Path(dst).name == name:
                raise OSError("injected replace failure")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(module.os, "replace", failing_replace)

    return inject


def _rollback_bare(manifest):
    """Follow the bare-at-root manual rollback in the worktree help."""
    done = set(manifest["steps_done"])
    pending = manifest.get("failed_step") or manifest["current_step"]
    top = Path(manifest["top"])
    gitdir = manifest["store_old"]
    store_new = Path(manifest["store_new"])

    def undo(step, is_done=True):
        return step in done or (step == pending and is_done)

    if undo("write_pointer", (top / ".git").is_file()):
        os.unlink(top / ".git")
    if undo("rename_store", store_new.exists()):
        os.rename(store_new, gitdir)
        _out(
            "--git-dir",
            gitdir,
            "worktree",
            "repair",
            *[w["new"] for w in manifest["linked"]],
        )
    for name in ("git-project-migrate.json", "git-project-migrate.json.tmp"):
        Path(top / ".git" / name).unlink(missing_ok=True)


@pytest.mark.parametrize(
    "inject, failed, last_done",
    [
        (_fail_replace("commondir"), "rewrite_commondir topic", None),
        (_fail_rename(".git"), "rename_store", "rewrite_commondir topic"),
        (_fail_write_pointer, "write_pointer", "rename_store"),
        (_fail_repair, "repair", "write_pointer"),
        (_fail_verify, "verify", "repair"),
    ],
)
def test_worktree_migrate_bare_at_root_stops_on_failure(
    bare_at_root_clone, script_runner, monkeypatch, inject, failed, last_done
):
    from git_project_core_plugins import worktree as worktree_module

    fc = bare_at_root_clone
    top = fc.top
    before = _snapshot(fc, internals=False)

    with monkeypatch.context() as patch:
        inject(patch, worktree_module)
        result = _migrate(script_runner, top, "--apply")

    assert not result.success
    store = fc.store if fc.store.is_dir() else top / ".git"
    manifest_path = store / "git-project-migrate.json"
    assert f"failed at step {failed}" in result.stdout
    assert str(manifest_path) in result.stdout
    manifest = json.loads(manifest_path.read_text())
    assert manifest["failed_step"] == failed
    assert manifest["steps_done"][-1:] == ([last_done] if last_done else [])

    _rollback_bare(manifest)

    assert _snapshot(fc, internals=False) == before
    for path in (fc.master, fc.topic):
        assert _out("-C", str(path), "status", "--porcelain") == ""
    assert not os.path.lexists(fc.store)
    assert not (fc.commondir.parent / "commondir.tmp").exists()


def test_worktree_migrate_bare_at_root_admin_name_differs(
    bare_at_root_clone, script_runner
):
    fc = bare_at_root_clone
    gitdir = str(fc.top / ".git")
    old, new = fc.top / "other", fc.top / "renamed"
    _out("--git-dir", gitdir, "worktree", "add", "-q", "-b", "b1", str(old))
    _out("--git-dir", gitdir, "worktree", "move", str(old), str(new))
    assert (fc.top / ".git" / "worktrees" / "other").is_dir()

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    assert _out("-C", str(new), "status", "--porcelain") == ""
    assert _worktree_branches(fc.store)[new] == "refs/heads/b1"


def test_worktree_migrate_refuses_bare_flag_on_a_checkout(
    remote_repository, script_runner, tmp_path, monkeypatch
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    base = tmp_path.resolve()
    top = base / "proj"
    _out("clone", "-q", "file://" + remote_repository.path, str(top))
    _out("-C", str(top), "worktree", "add", "-q", str(top / "topic"), "pushed")
    _out("-C", str(top), "config", "core.bare", "true")
    _out("--git-dir", str(top / ".git"), "config", "project.branch", "master")
    _out("--git-dir", str(top / ".git"), "config", "project.remote", "origin")
    fc = SimpleNamespace(base=base, top=top)
    before = _snapshot(fc)

    result = _migrate(script_runner, top)

    assert not result.success
    assert f"refuse: {top / '.git'} has an index" in result.stdout
    assert f"refuse: {top / 'Hello.txt'} is not a worktree" in result.stdout
    assert _snapshot(fc) == before


def _bare_sparse(fc):
    _out("-C", str(fc.topic), "sparse-checkout", "set", "nothing")
    return [fc.topic]


def _bare_skip_worktree(fc):
    _out("-C", str(fc.topic), "update-index", "--skip-worktree", "Hello.txt")
    return [fc.topic]


def _bare_dotfile(fc):
    (fc.top / ".envrc").write_text("export X=1\n")
    return []


def _bare_nested(fc):
    path = fc.top / "x" / "b1"
    gitdir = str(fc.top / ".git")
    _out("--git-dir", gitdir, "worktree", "add", "-q", "-b", "b1", str(path))
    return [path]


@pytest.mark.parametrize(
    "setup", [_bare_sparse, _bare_skip_worktree, _bare_dotfile, _bare_nested]
)
def test_worktree_migrate_bare_at_root_allows(
    bare_at_root_clone, script_runner, setup
):
    fc = bare_at_root_clone
    extra = setup(fc)

    result = _migrate(script_runner, fc.top, "--apply")

    assert result.success, result.stdout + result.stderr
    for path in {fc.master, fc.topic, *extra}:
        assert _out("-C", str(path), "status", "--porcelain") == ""
        assert _out(
            "-C", str(path), "rev-parse", "--git-common-dir"
        ).strip() == str(fc.store)
