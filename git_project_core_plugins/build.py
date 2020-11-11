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

"""A plugin to add a 'build' command to git-project.  The build command invokes
an arbitrary command intended to build the project.

Summary:

git-project build <flavor>

"""

from git_project import RunnableConfigObject, ConfigObjectItem, Plugin, Project
from git_project import get_or_add_top_level_command, gen_runnable_epilog

import argparse

def command_build(git, gitproject, project, clargs):
    """Implement git-project build"""
    build = Build.get(git, project, clargs.flavor)
    build.run(git, project, clargs)

def command_add_build(git, gitproject, project, clargs):
    """Implement git-project add build"""
    build = Build.get(git, project, clargs.flavor, command=clargs.command)
    project.add_item('build', clargs.flavor)

    return build

def command_rm_build(git, gitproject, project, clargs):
    """Implement git-project rm build"""
    build = Build.get(git, project, clargs.flavor, command=clargs.command)
    build.rm()
    print(f'Removing project build {clargs.flavor}')
    project.rm_item('build', clargs.flavor)

class Build(RunnableConfigObject):
    """A RunnableConfigObject to manage build flavors.  Each build flavor gets its
    own config section.

    """

    _configitems = [ConfigObjectItem('command',
                                     None,
                                     'Command to build project'),
                    ConfigObjectItem('description', None, 'Build flavor help')]

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'build'

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 configitems,
                 **kwargs):
        """Build construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Build.

        configitems: A list of ConfigObjectItem describing members of the config
                     section.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         configitems,
                         **kwargs)

    @classmethod
    def get(cls, git, project, flavor, **kwargs):
        """Factory to construct Builds.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        flavor: Name of the build to construct.

        kwargs: Attributes to set.

        """
        return super().get(git,
                           project.section,
                           cls.subsection(),
                           flavor,
                           cls.configitems(),
                           **kwargs)

    @staticmethod
    def substitutions():
        """RunnableConfigObject protocol substitutions."""
        return [ConfigObjectItem('path', None, 'Workarea root directory'),
                ConfigObjectItem('builddir', None, 'Build directory'),
                ConfigObjectItem('buildwidth', 1, 'Build width')]

    @classmethod
    def get_managing_command(cls):
        return 'build'

class BuildPlugin(Plugin):
    """A plugin to add the build command to git-project"""
    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project build.'"""
        if git.has_repo():
            # add build
            add_parser = get_or_add_top_level_command(parser_manager,
                                                      'add',
                                                      'add',
                                                      help=f'Add config sections to {project.section}')

            add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                                'add-command',
                                                                help='add sections')

            add_build_parser = parser_manager.add_parser(add_subparser,
                                                         Build.get_managing_command(),
                                                         'add-' + Build.get_managing_command(),
                                                         help=f'Add a build to {project.section}')

            add_build_parser.set_defaults(func=command_add_build)

            add_build_parser.add_argument('flavor',
                                          help='Name for the build')

            add_build_parser.add_argument('command',
                                          help='Command to run')

            builds = []
            if hasattr(project, 'build'):
                builds = [build for build in project.iter_multival('build')]

            # rm build
            rm_parser = get_or_add_top_level_command(parser_manager,
                                                     'rm',
                                                     'rm',
                                                     help=f'Remove config sections from {project.section}')

            rm_subparser = parser_manager.get_or_add_subparser(rm_parser,
                                                               'rm-command',
                                                               help='rm sections')

            rm_build_parser = parser_manager.add_parser(rm_subparser,
                                                        Build.get_managing_command(),
                                                        'rm-' + Build.get_managing_command(),
                                                        help=f'Remove a build from {project.section}')

            rm_build_parser.set_defaults(func=command_rm_build)

            if builds:
                rm_build_parser.add_argument('flavor', choices=builds,
                                             help='Build type')

            # build
            command_subparser = parser_manager.find_subparser('command')

            build_parser = parser_manager.add_parser(command_subparser,
                                                     Build.get_managing_command(),
                                                     Build.get_managing_command(),
                                                     help='Build project',
                                                     formatter_class=
                                                     argparse.RawDescriptionHelpFormatter,
                                                     epilog=
                                                     gen_runnable_epilog(Build,
                                                                         project,
                                                                         Build.subsection(),
                                                                         Build.configitems(),
                                                                         secparam='<flavor>'))

            build_parser.set_defaults(func=command_build)

            if builds:
                build_parser.add_argument('flavor', choices=builds,
                                          help='Build type')

    def add_class_hooks(self, git, plugin_manager):
        """Add hooks for build."""
        Project.add_config_item('build', None, 'Builds for the project')

    def iterclasses(self):
        """Iterate over public classes for git-project build."""
        yield Build
