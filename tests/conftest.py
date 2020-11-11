#!/usr/bin/env python3
#
# Copyright 2020 David A. Greene
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <https://www.gnu.org/licenses/>.
#

import pytest

from git_project import ConfigObject, ConfigObjectItem

from git_project.test_support import ParserManagerMock
from git_project.test_support import PluginMock
from git_project.test_support import orig_repository
from git_project.test_support import remote_repository
from git_project.test_support import local_repository
from git_project.test_support import reset_directory
from git_project.test_support import parser_manager
from git_project.test_support import plugin_manager
from git_project.test_support import git
from git_project.test_support import gitproject
from git_project.test_support import project

from git_project_core_plugins import ClonePlugin
from git_project_core_plugins import WorktreePlugin

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
def clone_parser_manager(request, git, gitproject, project, parser_manager):
    plugin = ClonePlugin()
    plugin.add_arguments(git, gitproject, project, parser_manager)
    return parser_manager

@pytest.fixture(scope="function")
def build_git(request, git, project):
    git.config.set_item(f'{project.section}.build.test', 'command', 'make test')
    git.config.set_item(f'{project.section}.build.test', 'description', 'Run tests')
    return git

@pytest.fixture(scope="function")
def configure_git(request, git, project):
    git.config.set_item(f'{project.section}.configure.debug', 'command', 'cmake debug')
    git.config.set_item(f'{project.section}.configure.debug', 'description', 'Configure debug build')
    return git

@pytest.fixture(scope="function")
def install_git(request, git, project):
    git.config.set_item(f'{project.section}.install.test', 'command', 'make install')
    git.config.set_item(f'{project.section}.install.test', 'description', 'Install build')
    return git
