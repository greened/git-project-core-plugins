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
#z

"""A plugin to add an 'install' command to git-project.  The install command
invokes an arbitrary command intended to install the project.

Summary:

git-project install <flavor>

Note that the line between 'build' and 'install' is blurry.  Many build systems
provide an install target, for example.  A project could choose to add an
'install' build flavor or to define a separate install flavor.  This plugin is
useful when a project requires a 'higher-level' process to do an install,
consisting of not only installing build artifacts but also any other
dependencies the project might have or other steps to take outside the build
system proper.

"""

from git_project import RunnableConfigObject, Plugin, Project
from git_project import get_or_add_top_level_command

import argparse

def command_install(git, gitproject, project, clargs):
    """Implement git-project install."""
    install = Install.get(git, project, clargs.flavor)
    install.run(git, project, clargs)

def command_add_install(git, gitproject, project, clargs):
    """Implement git-project add install"""
    install = Install.get(git, project, clargs.flavor, command=clargs.command)
    project.add_item('install', clargs.flavor)

    return install

class Install(RunnableConfigObject):
    """A RunnableConfigObject to manage install flavors."""

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
        """Install construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Install.

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
        return 'install'

    @classmethod
    def get(cls, git, project, flavor, **kwargs):
        """Factory to construct Installs.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        flavor: Name of the install to construct.

        kwargs: Attributes to set.

        """
        return super().get(git,
                           project.get_section(),
                           cls.subsection(),
                           flavor,
                           **kwargs)

    @classmethod
    def get_managing_command(cls):
        return 'install'

class InstallPlugin(Plugin):
    """A plugin to add the install command to git-project"""
    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project install.'"""
        if git.has_repo():
            add_parser = get_or_add_top_level_command(parser_manager,
                                                      'add',
                                                      'add',
                                                      help=f'Add config sections to {project.get_section()}')

            add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                                'add-command',
                                                                help='add sections')

            add_install_parser = parser_manager.add_parser(add_subparser,
                                                           Install.get_managing_command(),
                                                           'add-' + Install.get_managing_command(),
                                                           help=f'Add a install to {project.get_section()}')

            add_install_parser.set_defaults(func=command_add_install)

            add_install_parser.add_argument('flavor',
                                            help='Name for the install')

            add_install_parser.add_argument('command',
                                            help='Command to run')

            installs = []
            if hasattr(project, 'install'):
                installs = [install for install in project.iter_multival('install')]

            command_subparser = parser_manager.find_subparser('command')

            install_parser = parser_manager.add_parser(command_subparser,
                                                       Install.get_managing_command(),
                                                       Install.get_managing_command(),
                                                       help='Install project',
                                                       formatter_class=
                                                       argparse.RawDescriptionHelpFormatter)

            install_parser.set_defaults(func=command_install)

            if installs:
                install_parser.add_argument('flavor', choices=installs,
                                            help='Install type')

    def iterclasses(self):
        """Iterate over public classes for git-project install."""
        yield Install
