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

"""A plugin to add a 'configure' command to git-project.  The configure command
invokes an arbitrary command intended to configure the project for build.

Summary:

git-project configure <flavor>

"""

from git_project import RunnableConfigObject, Plugin, Project
from git_project import get_or_add_top_level_command

import argparse
from pathlib import Path

def command_configure(git, gitproject, project, clargs):
    """Implement git-project configure"""
    configure = Configure.get(git, project, clargs.flavor)
    configure.run(git, project, clargs)

def command_add_configure(git, gitproject, project, clargs):
    """Implement git-project add configure"""
    configure = Configure.get(git, project, clargs.flavor, command=clargs.command)
    project.add_item('configure', clargs.flavor)

    return configure

class Configure(RunnableConfigObject):
    """A RunnableConfigObject to manage configure flavors.  Each configure flavor
    gets its own config section.

    """

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
        """Configure construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Configure.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         **kwargs)

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'configure'

    @classmethod
    def get(cls, git, project, flavor, **kwargs):
        """Factory to construct Configures.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        flavor: Name of the configure to construct.

        kwargs: Attributes to set.

        """
        return super().get(git,
                           project.get_section(),
                           cls.subsection(),
                           flavor,
                           **kwargs)

    @classmethod
    def get_managing_command(cls):
        return 'configure'

class ConfigurePlugin(Plugin):
    """A plugin to add the configure command to git-project"""
    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project configure.'"""
        if git.has_repo():
            add_parser = get_or_add_top_level_command(parser_manager,
                                                      'add',
                                                      'add',
                                                      help=f'Add config sections to {project.get_section()}')

            add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                                'add-command',
                                                                help='add sections')

            add_configure_parser = parser_manager.add_parser(add_subparser,
                                                             Configure.get_managing_command(),
                                                             'add-' + Configure.get_managing_command(),
                                                             help=f'Add a configure to {project.get_section()}')

            add_configure_parser.set_defaults(func=command_add_configure)

            add_configure_parser.add_argument('flavor',
                                              help='Name for the configure')

            add_configure_parser.add_argument('command',
                                              help='Command to run')

            configures = []
            if hasattr(project, 'configure'):
                configures = [configure for configure in project.iter_multival('configure')]

            command_subparser = parser_manager.find_subparser('command')

            configure_parser = parser_manager.add_parser(command_subparser,
                                                         Configure.get_managing_command(),
                                                         Configure.get_managing_command(),
                                                         help='Configure project',
                                                         formatter_class=
                                                         argparse.RawDescriptionHelpFormatter)

            configure_parser.set_defaults(func=command_configure)

            if configures:
                configure_parser.add_argument('flavor', choices=configures,
                                            help='Configure type')

    def iterclasses(self):
        """Iterate over public classes for git-project configure."""
        yield Configure
