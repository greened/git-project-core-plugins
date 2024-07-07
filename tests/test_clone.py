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
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

import os
from pathlib import Path

from git_project_core_plugins import ClonePlugin
import common

def test_add_arguments(reset_directory,
                       git,
                       gitproject,
                       project,
                       parser_manager,
                       plugin_manager):
    plugin = ClonePlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    clone_parser = parser_manager.find_parser('clone')

    clone_args = [
        'url',
        'path',
        '--bare',
    ]

    common.check_args(clone_parser, clone_args)

    assert clone_parser.get_default('func').__name__ == 'command_clone'

def test_clone(reset_directory,
               git,
               gitproject,
               project,
               parser_manager,
               plugin_manager,
               remote_repository):
    plugin = ClonePlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    clone_parser = parser_manager.find_parser('clone')

    command_clone = clone_parser.get_default('func')

    clargs = {
        'url': remote_repository.path,
        'bare': False
    }

    gitdir = command_clone(git, gitproject, project, common.AttrDict(clargs))

    assert os.path.exists(gitdir)
    assert os.path.exists(Path(gitdir) / '.git')

def test_clone_bare(reset_directory,
                    git,
                    gitproject,
                    project,
                    parser_manager,
                    plugin_manager,
                    remote_repository):
    plugin = ClonePlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    clone_parser = parser_manager.find_parser('clone')

    command_clone = clone_parser.get_default('func')

    clargs = {
        'url': remote_repository.path,
        'bare': True
    }

    gitdir = command_clone(git, gitproject, project, common.AttrDict(clargs))

    assert os.path.exists(gitdir)
    assert not os.path.exists(Path(gitdir) / '.git')

def test_clone_path(reset_directory,
                    git,
                    gitproject,
                    project,
                    parser_manager,
                    plugin_manager,
                    remote_repository):
    plugin = ClonePlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    clone_parser = parser_manager.find_parser('clone')

    command_clone = clone_parser.get_default('func')

    clone_path = Path.cwd() / 'foo' / 'bar'/ 'test-clone'

    clargs = {
        'url': remote_repository.path,
        'path': str(clone_path),
        'bare': False
    }

    gitdir = command_clone(git, gitproject, project, common.AttrDict(clargs))

    assert os.path.exists(gitdir)
    assert os.path.exists(Path(gitdir) / '.git')
    assert gitdir == str(clone_path)
