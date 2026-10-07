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

import subprocess
from types import SimpleNamespace

import pygit2
import pytest
from git_project.test_support.common import create_commit

from git_project_core_plugins import ClonePlugin, InitPlugin, WorktreePlugin
from git_project_core_plugins.worktree import get_hidden_gitdir_name

# Registering the module as a plugin provides its fixtures. Importing them by
# name instead makes each fixture parameter shadow the import.
pytest_plugins = ["git_project.test_support"]


@pytest.fixture(autouse=True)
def no_user_git_config(monkeypatch):
    # A remote delete runs git push, which would run the user's global
    # pre-push hook.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture(scope="function")
def worktree_parser_manager(request, git, gitproject, project, parser_manager):
    plugin = WorktreePlugin()
    plugin.add_arguments(git, gitproject, project, parser_manager)
    return parser_manager


@pytest.fixture(scope="function")
def worktree_plugin_manager(request, git, gitproject, project, plugin_manager):
    plugin_manager.plugins.append(WorktreePlugin())
    return plugin_manager


@pytest.fixture(scope="function")
def clone_parser_manager(
    request, git, gitproject, project, parser_manager, plugin_manager
):
    plugin = ClonePlugin()
    plugin.add_arguments(
        git, gitproject, project, parser_manager, plugin_manager
    )
    return parser_manager


@pytest.fixture(scope="function")
def init_parser_manager(
    request, git, gitproject, project, parser_manager, plugin_manager
):
    plugin = InitPlugin()
    plugin.add_arguments(
        git, gitproject, project, parser_manager, plugin_manager
    )
    return parser_manager


@pytest.fixture(scope="function")
def run_git(request, git, project):
    git.config.set_item(
        f"{project.get_section()}.run.test", "command", "make test"
    )
    git.config.set_item(
        f"{project.get_section()}.run.test", "description", "Run tests"
    )
    return git


@pytest.fixture(scope="function")
def flat_clone(request, monkeypatch, remote_repository, tmp_path_factory):
    """A flat clone with two linked worktrees beside and away from it, local
    branches with unpushed commits, ignored files and a stash.

    """
    # Ignore the user's git configuration to keep the test hermetic.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(*args):
        subprocess.run(["git", *args], check=True, capture_output=True)

    base = tmp_path_factory.mktemp("flat").resolve()
    top = base / "proj"
    url = "file://" + remote_repository.path
    git("clone", "-q", url, str(top))

    repo = pygit2.Repository(str(top))
    master = repo.revparse_single("refs/heads/master").id
    repo.branches.create("topic", repo.revparse_single("origin/pushed"))
    for branch, text in (("user/feature", "Feature"), ("local-only", "Local")):
        repo.branches.create(branch, repo.get(master))
        create_commit(repo, f"refs/heads/{branch}", [master], text)

    topic = base / "proj-topic"
    feature = base / "elsewhere" / "feat"
    git("-C", str(top), "worktree", "add", "-q", "../proj-topic", "topic")
    git("-C", str(top), "worktree", "add", "-q", str(feature), "user/feature")

    with open(top / ".git" / "info" / "exclude", "a") as exclude:
        exclude.write("build/\n.venv/\n")
    (top / "build").mkdir()
    (top / "build" / "out.o").write_text("object\n")
    (top / ".venv").mkdir()
    (top / ".venv" / "marker").write_text("venv\n")

    (top / "Hello.txt").write_text("stashed\n")
    git(
        "-C",
        str(top),
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "stash",
        "push",
        "-q",
        "-m",
        "flat clone stash",
    )

    # git-project sets these on its first run. Set them now, so a run that
    # must change nothing leaves the config as it found it.
    git("-C", str(top), "config", "project.branch", "master")
    git("-C", str(top), "config", "project.remote", "origin")

    return SimpleNamespace(
        base=base,
        top=top,
        topic=topic,
        feature=feature,
        store=top / get_hidden_gitdir_name(url),
    )


@pytest.fixture(scope="function")
def bare_at_root_clone(monkeypatch, remote_repository, tmp_path_factory):
    """A store bare at <top>/.git with two worktrees in <top>. One
    worktree's commondir is absolute.

    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(*args):
        subprocess.run(["git", *args], check=True, capture_output=True)

    base = tmp_path_factory.mktemp("bare").resolve()
    top = base / "proj"
    gitdir = top / ".git"
    url = "file://" + remote_repository.path
    git("clone", "-q", "--bare", url, str(gitdir))
    git("--git-dir", str(gitdir), "branch", "topic", "pushed")

    master = top / "master"
    topic = top / "topic"
    git(
        "--git-dir",
        str(gitdir),
        "worktree",
        "add",
        "-q",
        str(master),
        "master",
    )
    git("--git-dir", str(gitdir), "worktree", "add", "-q", str(topic), "topic")
    commondir = gitdir / "worktrees" / "topic" / "commondir"
    commondir.write_text(f"{gitdir}\n")

    git("--git-dir", str(gitdir), "config", "project.branch", "master")
    git("--git-dir", str(gitdir), "config", "project.remote", "origin")

    return SimpleNamespace(
        base=base,
        top=top,
        master=master,
        topic=topic,
        commondir=commondir,
        store=top / get_hidden_gitdir_name(url),
    )
