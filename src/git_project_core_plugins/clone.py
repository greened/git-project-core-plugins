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

"""A plugin to add a 'clone' command to git-project.  The clone command clones a
repository and optionally initializes a master worktree environment.

Summary:

git-project clone <url> [path] [--bare] [--no-master-worktree]

"""

from git_project import add_top_level_command, Plugin

from git_project_core_plugins.common import add_plugin_version_argument

import getpass
import os
from pathlib import Path
import pygit2

def command_clone(git, gitproject, project, clargs):
    """Implement git-project clone"""
    gitdir = git.clone(clargs.url,
                       path=clargs.path if hasattr(clargs, 'path') else None,
                       bare=clargs.bare)

    # Now that we have a repository, add sensible project defaults.  We know
    # there is no existing project in the config file since we just cloned.
    # This will have the effect of adding a project section.
    project.set_defaults()

    return gitdir

class ClonePlugin(Plugin):
    """
    The clone command clones a repository.

    Summary:

      git <project> clone <url> [<path>] [--bare]

    By itself clone has just the very basic funcionality of the built-in git
    clone command.  Plugins may add options to give the clone command more
    features.  For example, the woktree command adds a --worktree option to have
    clone create a ``worktree layout.''

    See also:

      worktree

    """

    def __init__(self):
        super().__init__('clone')

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manager):
        """Add arguments for 'git-project clone.'"""
        # clone
        clone_parser = add_top_level_command(parser_manager,
                                             'clone',
                                             'clone',
                                             help='Clone project')

        add_plugin_version_argument(clone_parser)

        clone_parser.set_defaults(func=command_clone)

        clone_parser.add_argument('url',
                                  help='URL to clone')

        clone_parser.add_argument('path',
                                  nargs='?',
                                  help='Local repository location')

        clone_parser.add_argument('--bare',
                                  action='store_true',
                                  help='Clone a bare repository')
