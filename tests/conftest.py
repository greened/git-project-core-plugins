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

import pytest

from git_project_core_plugins import ClonePlugin, InitPlugin, WorktreePlugin

# Registering the module as a plugin provides its fixtures. Importing them by
# name instead makes each fixture parameter shadow the import.
pytest_plugins = ["git_project.test_support"]


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
