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

"""A plugin to add a 'help' command to git-project.

Summary:

git-project help [<command>] [<ident>]

"""

from git_project import ConfigObject, RunnableConfigObject, ConfigObjectItem
from git_project import Plugin, Project, GitProjectException

def command_help(git, gitproject, project, clargs):
    """Implement git-project help."""
    if hasattr(clargs, 'command'):
        getter = clargs.getter
        exister = clargs.exister
        classname = clargs.classname

        subsection = None
        if hasattr(clargs, 'subsection'):
            subsection = clargs.subsection

        ident = None
        if hasattr(clargs, 'ident'):
            ident = clargs.ident

        if not exister(git, project.section, subsection, ident):
            if ident:
                raise GitProjectException(f'{classname} \'{ident}\' does not exist')
            else:
                raise GitProjectException(f'No {classname} configured')

        configitem = getter(git, project, ident) if ident else getter(git, project.section)
        if hasattr(configitem, 'help'):
            print(configitem.__class_.help)
        else if hasattr(configitem.__class__, 'print_help'):
            configitem.print_help()
    else:
        print("""git-project: The extensible stupid project manager

git-project manages various aspects of project development, including things
like branches, builds and so on.""")

class HelpPlugin(Plugin):
    def _add_help_parser(self, cls, project, parser_manager):
        command = cls.get_managing_command()
        help_key = command + '-help' if command else 'help'
        help_parser = parser_manager.find_parser(help_key)
        if not help_parser:
            # Create a help parser under the managing command.
            command_subparser_key = command + '-command' if command else 'command'
            command_subparser = parser_manager.find_subparser(command_subparser_key)
            if not command_subparser:
                # This plugin doesn't have subcommands, so don't add one.
                return

            help_help = 'Print help for ' + command if command else 'Print help for git-project'
            help_parser = parser_manager.add_parser(command_subparser,
                                                    'help',
                                                    help_key,
                                                    help=help_help)

            help_parser.set_defaults(func=command_help)
            help_parser.set_defaults(getter=cls.get)
            help_parser.set_defaults(exister=cls.exists)
            help_parser.set_defaults(classname=cls.__name__)

            if hasattr(cls, 'subsection'):
                help_parser.set_defaults(subsection=cls.subsection())
                help_parser.add_argument('ident', help=f'{cls.__name__} to modify')

            help_parser.add_argument('name', help='Property name')
            help_parser.add_argument('value', nargs='?', help='Property value to set')
            help_parser.add_argument('--add', action='store_true',
                                     help='Add a value to a property')
            help_parser.add_argument('--unset', action='store_true',
                                     help='Remove a value from a property')

    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project help'"""
        self._add_help_parser(Project, project, parser_manager)

    def modify_arguments(self, git, gitproject, project, parser_manager, plugin_manager):
        """Modify arguments for 'git-project help.'"""

        # Find all plugins with classes that derive from ConfigObject and add
        # help commands to them.
        for plugin in plugin_manager.iterplugins():
            for cls in plugin.iterclasses():
                if (issubclass(cls, ConfigObject)):
                    self._add_help_parser(cls, project, parser_manager)
