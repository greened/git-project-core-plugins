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

"""A plugin to add a 'clone' command to git-project. The clone command clones a
repository. The worktree plugin adds a --worktree option to it.

Summary:

git-project clone [--bare] <url> [<path>]

"""

from git_project import add_top_level_command, Plugin

from git_project_core_plugins.common import add_plugin_version_argument

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

    Summary::

      git <project> clone <url> [<path>] [--bare]

    By itself clone does a basic clone, then sets the project's defaults in
    the new repository. With no <path> it clones into the last component of
    <url> under the current directory, keeping any ``.git`` suffix, where
    ``git clone`` drops it. It offers no ssh key, so an ssh url fails to
    authenticate.

    Plugins add options to clone. For example, the worktree command adds a
    --worktree option to have clone create a ``worktree layout``.

    See also::

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
