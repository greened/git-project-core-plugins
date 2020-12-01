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

"""A plugin to add a 'config' command to git-project.  The config command sets
project-wide git configuration values and prints their values to stdout.

Summary:

git-project config <key> [--unset] [<value>]

"""

from git_project import ConfigObject, RunnableConfigObject, ConfigObjectItem
from git_project import Plugin, Project, GitProjectException

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
            setattr(configitem, clargs.name, clargs.value)
    elif clargs.unset:
        delattr(configitem, clargs.name)
    else:
        value = getattr(configitem, clargs.name)
        print(value)

class ConfigPlugin(Plugin):
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

            config_parser.add_argument('name', help='Property name')
            config_parser.add_argument('value', nargs='?', help='Property value to set')
            config_parser.add_argument('--add', action='store_true',
                                       help='Add a value to a property')
            config_parser.add_argument('--unset', action='store_true',
                                       help='Remove a value from a property')

    def add_arguments(self, git, gitproject, project, parser_manager):
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
