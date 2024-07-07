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

"""A plugin to add an 'init' command to git-project.  The init command does
initialization of a workarea,

Summary:

git-project init

"""
from git_project import Git, RunnableConfigObject, Plugin
from git_project import add_top_level_command, Project, GitProjectException

from git_project_core_plugins.common import add_plugin_version_argument

import getpass

def command_init(git, gitproject, project, clargs):
    """Implement git-project init."""
    pass

class InitPlugin(Plugin):
    """
    The init command initializes project state.

    Summary:

      git <project> init

    Basic config entries are added to name the project and default branches.
    Plugins may add options to enhance functionality.  For example the worktree
    command adds a --worktree option to convert an existing local clone to a
    ``worktree layout.''

    See also:

      worktree

    """
    def __init__(self):
        super().__init__('init')

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manager):
        """Add arguments for 'git project init.'"""
        # init
        init_parser = add_top_level_command(parser_manager,
                                            'init',
                                            'init',
                                            help='Initialize project')

        add_plugin_version_argument(init_parser)

        init_parser.set_defaults(func=command_init)
