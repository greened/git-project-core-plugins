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

"""A plugin to add a 'help' command to git-project.  The help command looks up
help text in the gitconfig and displays it.

Summary:

git-project help [command] [options...]

"""

from git_project import ConfigObject, Plugin, Project
from git_project import add_top_level_command, GitProjectException
from git_project import get_or_add_top_level_command

from git_project_core_plugins.common import add_plugin_version_argument

from pydoc import pager

def _print_general_help(git, gitproject, project, clargs):
    pager("""git-project: The stupid extensible project manager

git-project aims to make managing various project aspects simple and convenient.
The key idea of git-project is that various project actions may be coupled to
the source code repository or workarea in some fashion.  For example, developers
may want builds isolated by the current branch, such that build directories are
encoded with the branch name.  Or users may want to create worktrees associated
with build and install directories, so that removing a worktree also removes the
associated build and install directories.

git-project may be invoked via ``git project <command> [options...]'' or, by
linking the git-project command to another command named ``git-<name>'' it may
be invoked via ``git <name> <command>.''  For example, linking ``git-project''
to ``git-fizzbin'' we may invoke commands via ``git fizzbin <command>'' and all
configuration will appear under a ``fizzbin'' config section.  Thus, a single
repository may support multiple projects, each with a unique name.  To emphasize
this, we will show invocations of git-project as ``git <project> [options...].''

Plugins extend git-project with new functionality.  Each plugin should include
extensive documentation accessible though --help flags or via help command
options.

To see help for a specific command, try ``git <project> help [command]
 [options...].''
""")

class Help(ConfigObject):
    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'help'

    @classmethod
    def get_managing_command(cls):
        """ConfigObject protocol get_managing_command."""
        return 'help'

    @staticmethod
    def _prepend_subsection(subsection):
        if subsection:
            return 'help.' + subsection
        return 'help'

    @classmethod
    def get(cls, git, project, subsection, ident, **kwargs):
        """Factory to construct Helps.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        subsection: The subsection under "help" to retrieve.

        ident: The specific help to retrieve.

        kwargs: Attributes to set.

        """
        return super().get(git,
                           project.get_section(),
                           cls._prepend_subsection(subsection),
                           ident,
                           **kwargs)

    @classmethod
    def exists(cls,
               git,
               project,
               subsection,
               ident):
        """Return whether an existing git config exists for the ConfigObject.

        cls: The derived class being checked.

        git: An object to query the repository and make config changes.

        project: The active project.

        subsection: Subsection under 'help' to query

        ident: The name of the specific help we're looking for.

        """
        return super().exists(git,
                              project.get_section(),
                              cls._prepend_subsection(subsection),
                              ident)

# Map command names to plugins.  We use this to see if a command given to
# git-project help has its own built-in help in its plugin.  This avoids the
# need to store large help pages in the git config and also allows later
# versions of plugins to provide new help and not be stuck with whatever happens
# to be stored in the config.
_command_plugin_registry = dict()

def command_help(git, gitproject, project, clargs):
    """Implement git-project help."""
    if not hasattr(clargs, 'options') or len(clargs.options) < 1:
        _print_general_help(git, gitproject, project, clargs)
        return

    ident = clargs.options[-1]
    subsection = ''

    if len(clargs.options) == 1:
        # See if this command has built-in help.
        plugin = _command_plugin_registry.get(ident, None)
        if hasattr(plugin, 'manpage'):
            pager(plugin.manpage())
            return
    else:
        subsection = '.'.join(clargs.options[:-1])

    if not Help.exists(git, project, subsection, ident):
        print(f'No help available for \'{" ".join(clargs.options)}\'')
        return

    command_help = Help.get(git,project, subsection, ident)

    if (hasattr(command_help, 'manpage')):
        pager(command_help.manpage)
    else:
        print(f'No help page available for \'{" ".join(clargs.options)}\'')

def command_add_help(git, gitproject, project, clargs):
    f"""Implement git-project add help"""
    help_section = f'{project.get_section()}.help.{clargs.name}'
    if clargs.manpage:
        git.config.add_item(help_section, 'manpage', clargs.text)
    else:
        git.config.add_item(help_section, 'short', clargs.text)

def command_rm_help(git, gitproject, project, clargs):
    f"""Implement git-project r help"""
    help_section = f'{project.get_section()}.help.{clargs.name}'
    if clargs.manpage:
        git.config.rm_items(help_section, 'manpage')
    else:
        git.config.rm_items(help_section, 'short')

class HelpPlugin(Plugin):
    """
    The help command displays tutorial-style help for commands.

    Summary:

      git <project> add help [--manpage] <subsection> <text>
      git <project> help <command>

    Users may add help to any project config section.  For example:

      git <project> add help run.build "Perform a build"
      git <project> add help run.check "Run tests"

    All help is stored under a <project>.help config sub-section.  If a command
    supports it, such help may appear in the command's own help output by
    querying the appropriate <project>.help sub-section:

      git <project> run --help

      <standard help text>

      build     -- Perform a build
      check     -- Run tests

    In this way projects can self-document their configurations.  Normally
    <text> is stored in <project>.help.<subsection>.short.  With --manpage,
    <text> is stored in <project>.help.<subsection>.manpage.  Commands may
    reference short help or manpages in various ways to present help.

    See also:

      run

    """
    def __init__(self):
        super().__init__('help')

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manager):
        """Add arguments for 'git-project help'"""
        # help
        help_parser = add_top_level_command(parser_manager,
                                            'help',
                                            'help',
                                            help='Display help')

        help_parser.set_defaults(func=command_help)

        add_plugin_version_argument(help_parser)

        help_parser.add_argument('options',
                                 nargs='*',
                                 help='Specify help section')

        # add help
        add_parser = get_or_add_top_level_command(parser_manager,
                                                  'add',
                                                  'add',
                                                  help=f'Add config sections to {project.get_section()}')

        add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                            'add-command',
                                                            help='add sections')

        add_help_parser = parser_manager.add_parser(add_subparser,
                                                    'help',
                                                    'add-help',
                                                    help=f'Add help to {project.get_section()}')

        add_help_parser.set_defaults(func=command_add_help)

        add_help_parser.add_argument('--manpage',
                                     action='store_true',
                                     help='Add help as manpage')

        add_help_parser.add_argument('name',
                                     help='Command name for which to add help')

        add_help_parser.add_argument('text',
                                     help='Help text')

        # rm help
        rm_parser = get_or_add_top_level_command(parser_manager,
                                                  'rm',
                                                  'rm',
                                                  help=f'Remove config sections from {project.get_section()}')

        rm_subparser = parser_manager.get_or_add_subparser(rm_parser,
                                                           'rm-command',
                                                           help='remove sections')

        rm_help_parser = parser_manager.add_parser(rm_subparser,
                                                   'help',
                                                   'rm-help',
                                                   help=f'Remove help from {project.get_section()}')

        rm_help_parser.set_defaults(func=command_rm_help)

        rm_help_parser.add_argument('--manpage',
                                    action='store_true',
                                    help='Add help as manpage')

        rm_help_parser.add_argument('name',
                                    help='Command name for which to add help')

    def modify_arguments(self,
                         git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager):
        """Register known plugins for 'git-project help.'"""

        for plugin in plugin_manager.iterplugins():
            _command_plugin_registry[plugin.name] = plugin
