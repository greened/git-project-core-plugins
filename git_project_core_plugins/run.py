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

"""A plugin to add a 'run' command to git-project.  The run command invokes an
arbitrary command.  It can be used to perform any action, such as building the
project.

Summary:

git-project run <name>

"""

from git_project import RunnableConfigObject, Plugin, Project
from git_project import get_or_add_top_level_command

import argparse

def command_run(git, gitproject, project, clargs):
    """Implement git-project run"""
    run = Run.get(git, project, clargs.name)
    run.run(git, project, clargs)

def command_add_run(git, gitproject, project, clargs):
    """Implement git-project add run"""
    run = Run.get(git, project, clargs.name, command=clargs.command)
    project.add_item('run', clargs.name)

    return run

def command_rm_run(git, gitproject, project, clargs):
    """Implement git-project rm run"""
    run = Run.get(git, project, clargs.name, command=clargs.command)
    run.rm()
    print(f'Removing project run {clargs.name}')
    project.rm_item('run', clargs.name)

class Run(RunnableConfigObject):
    """A RunnableConfigObject to manage run names.  Each run name gets its
    own config section.

    """

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'run'

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
        """Run construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Run.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         **kwargs)

    @classmethod
    def get(cls, git, project, name, **kwargs):
        """Factory to construct Runs.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        name: Name of the command to run.

        kwargs: Attributes to set.

        """
        return super().get(git,
                           project.get_section(),
                           cls.subsection(),
                           name,
                           **kwargs)

    @classmethod
    def get_managing_command(cls):
        return 'run'

class RunPlugin(Plugin):
    """A plugin to add the run command to git-project"""
    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project run.'"""
        if git.has_repo():
            # add run
            add_parser = get_or_add_top_level_command(parser_manager,
                                                      'add',
                                                      'add',
                                                      help=f'Add config sections to {project.get_section()}')

            add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                                'add-command',
                                                                help='add sections')

            add_run_parser = parser_manager.add_parser(add_subparser,
                                                       Run.get_managing_command(),
                                                       'add-' + Run.get_managing_command(),
                                                       help=f'Add a run to {project.get_section()}')

            add_run_parser.set_defaults(func=command_add_run)

            add_run_parser.add_argument('name',
                                        help='Name for the run')

            add_run_parser.add_argument('command',
                                        help='Command to run')

            runs = []
            if hasattr(project, 'run'):
                runs = [run for run in project.iter_multival('run')]

            # rm run
            rm_parser = get_or_add_top_level_command(parser_manager,
                                                     'rm',
                                                     'rm',
                                                     help=f'Remove config sections from {project.get_section()}')

            rm_subparser = parser_manager.get_or_add_subparser(rm_parser,
                                                               'rm-command',
                                                               help='rm sections')

            rm_run_parser = parser_manager.add_parser(rm_subparser,
                                                      Run.get_managing_command(),
                                                      'rm-' + Run.get_managing_command(),
                                                      help=f'Remove a run from {project.get_section()}')

            rm_run_parser.set_defaults(func=command_rm_run)

            if runs:
                rm_run_parser.add_argument('name', choices=runs,
                                           help='Command name')

            # run
            command_subparser = parser_manager.find_subparser('command')

            run_parser = parser_manager.add_parser(command_subparser,
                                                   Run.get_managing_command(),
                                                   Run.get_managing_command(),
                                                   help='Run project',
                                                   formatter_class=
                                                   argparse.RawDescriptionHelpFormatter)

            run_parser.set_defaults(func=command_run)

            if runs:
                run_parser.add_argument('name', choices=runs,
                                        help='Command name')

    def iterclasses(self):
        """Iterate over public classes for git-project run."""
        yield Run
