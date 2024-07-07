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

"""A plugin to add a 'config' command to git-project.  The config command sets
project-wide git configuration values and prints their values to stdout.

Summary:

git-project config <key> [--unset] [<value>]

"""

from git_project import ConfigObject, RunnableConfigObject
from git_project import Plugin, Project, GitProjectException

from git_project_core_plugins.common import add_plugin_version_argument

def command_config(git, gitproject, project, clargs):
    """Implement git-project config."""
    getter = clargs.getter
    exister = clargs.exister
    classname = clargs.classname

    subsection = None
    if hasattr(clargs, 'subsection'):
        subsection = clargs.subsection

    ident = None
    if hasattr(clargs, 'ident'):
        ident = clargs.ident

    if not exister(git, project.get_section(), subsection, ident):
        if ident:
            raise GitProjectException(f'{classname} \'{ident}\' does not exist')
        else:
            raise GitProjectException(f'No {classname} configured')

    configitem = getter(git, project, ident) if ident else getter(git, project.get_section())

    if clargs.value:
        if clargs.unset:
            configitem.rm_item(clargs.name, clargs.value)
        else:
            if clargs.add:
                configitem.add_item(clargs.name, clargs.value)
            else:
                setattr(configitem, clargs.name, clargs.value)
    elif clargs.unset:
        delattr(configitem, clargs.name)
    else:
        value = getattr(configitem, clargs.name)
        print(value)

class ConfigPlugin(Plugin):
    """
    The config command manages git config settings under the <project> section.

    Summary:

      git <project> config [--add] [--unset] <name> [<value>]

    The config command operates much like git's built-in config command, except
    all configuration keys are prefixed with <project>, keeping values under a
    single project namespace.  This is a convenient way to store parameters for
    other commands.  For example:

      git <project> config builddir /path/to/build
      git <project> add run build "make BUILDDIR={builddir} all"

    Configuration kays may have their values substituted into other
    configuration values via the {key} specifier.  Special commands like build
    perform the substitution recursively, so configuration vaalues may contain
    substitutions of other configuration values which themselves contain
    substitutions, and so on.  Importantly, substitution only happens when
    commands are run.  Commands should document whether or not they perform
    substitutions.

    A git config ``sub-section'' may be substituted with its identifier.  For
    example:

      git <project> worktree add myworktree
      git <project> config builddir /path/to/{worktree}/build

    Here, myworktree is the identifier of a specific worktree sub-section.  If
    myworktree is the currently active worktree (that is, the current directory
    is under the myworktree root), then ``myworktree'' will substitute for
    {woktree}.

    See also:

      run
      worktree

    """
    def __init__(self):
        super().__init__('config')

    def _add_config_parser(self, cls, project, parser_manager):
        command = cls.get_managing_command()
        config_key = command + '-config' if command else 'config'
        config_parser = parser_manager.find_parser(config_key)

        if not config_parser:
            # Create a config parser under the managing command.
            command_subparser_key = command + '-command' if command else 'command'
            command_subparser = parser_manager.find_subparser(command_subparser_key)
            if not command_subparser:
                # This plugin doesn't have subcommands, so don't add one.
                return

            config_help = 'Configure ' + command if command else 'Configure git-project'
            config_parser = parser_manager.add_parser(command_subparser,
                                                      'config',
                                                      config_key,
                                                      help=config_help)

            config_parser.set_defaults(func=command_config)
            config_parser.set_defaults(getter=cls.get)
            config_parser.set_defaults(exister=cls.exists)
            config_parser.set_defaults(classname=cls.__name__)

            if hasattr(cls, 'subsection'):
                config_parser.set_defaults(subsection=cls.subsection())
                config_parser.add_argument('ident', help=f'{cls.__name__} to modify')

            if not command:
                # This is the top-level 'config' command.
                add_plugin_version_argument(config_parser)

            config_parser.add_argument('name', help='Property name')
            config_parser.add_argument('value', nargs='?', help='Property value to set')
            config_parser.add_argument('--add', action='store_true',
                                       help='Add a value to a property')
            config_parser.add_argument('--unset', action='store_true',
                                       help='Remove a value from a property')

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manager):
        """Add arguments for 'git-project config'"""
        self._add_config_parser(Project, project, parser_manager)

    def modify_arguments(self, git, gitproject, project, parser_manager, plugin_manager):
        """Modify arguments for 'git-project config.'"""

        # Find all plugins with classes that derive from ConfigObject and add
        # config commands to them.
        for plugin in plugin_manager.iterplugins():
            for cls in plugin.iterclasses():
                if (issubclass(cls, ConfigObject)):
                    self._add_config_parser(cls, project, parser_manager)
