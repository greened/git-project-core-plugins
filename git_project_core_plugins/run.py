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

from git_project import ConfigObject, RunnableConfigObject, Plugin, Project
from git_project import get_or_add_top_level_command, GitProjectException

import argparse

class RunConfig(ConfigObject):
    """A ConfigObject to manage run aliases."""

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'run'

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident = None,
                 **kwargs):
        """RunConfig construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         **kwargs)

    @classmethod
    def get(cls, git, project, **kwargs):
        """Factory to construct RunConfigs.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        kwargs: Attributes to set.

        """
        return super().get(git,
                           project.get_section(),
                           cls.subsection(),
                           None,
                           **kwargs)

class RunPlugin(Plugin):
    """A plugin to add the run command to git-project"""

    def __init__(self):
        super().__init__('run')
        self.classes = dict()
        self.classes['run'] = self._make_alias_class('run')

    def _make_alias_class(self, alias):
        # Create a class for the alias.
        @staticmethod
        def subsection():
            """ConfigObject protocol subsection."""
            return alias

        @classmethod
        def get_managing_command(cls):
            """ConfigObject protocol get_managing_command."""
            return alias

        Class = type(alias + "Class", (RunnableConfigObject, ), {
#            __doc__ = f"""A RunnableConfigObject to manage {alias} names.  Each run name gets its own
#            config section.
#
#            """
                'subsection': subsection,
                'get_managing_command': get_managing_command
        })

        def cons(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
            f"""{alias} construction.

            cls: The derived class being constructed.

            git: An object to query the repository and make config changes.

            project_section: git config section of the active project.

            subsection: An arbitrarily-long subsection appended to project_section

            ident: The name of this specific {alias}.

            **kwargs: Keyword arguments of property values to set upon construction.

            """
            super(Class, self).__init__(git,
                                        project_section,
                                        subsection,
                                        ident,
                                        **kwargs)

        @classmethod
        def get(cls, git, project, name, **kwargs):
            f"""Factory to construct {alias}s.

            cls: The derived class being constructed.

            git: An object to query the repository and make config changes.

            project: The currently active Project.

            name: Name of the command to run.

            kwargs: Attributes to set.

            """
            return super(Class, cls).get(git,
                                         project.get_section(),
                                         cls.subsection(),
                                         name,
                                         **kwargs)

        Class.__init__ = cons
        Class.get = get

        self.classes[alias] = Class
        return Class

    def _gen_runs_epilog(self, alias, runs):
        result = f'Available {alias}s:\n'
        for run in runs:
            result += f'    {run}\n'

        return result

    def _add_alias_arguments(self,
                             git,
                             gitproject,
                             project,
                             parser_manager,
                             Class):
        alias = Class.get_managing_command()

        # add run
        add_parser = get_or_add_top_level_command(parser_manager,
                                                  'add',
                                                  'add',
                                                  help=f'Add config sections to {project.get_section()}')

        add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                            'add-command',
                                                            help='add sections')

        add_run_parser = parser_manager.add_parser(add_subparser,
                                                   alias,
                                                   'add-' + alias,
                                                   help=f'Add a {alias} to {project.get_section()}')

        def command_add_run(git, gitproject, project, clargs):
            f"""Implement git-project add {alias}"""
            run = Class.get(git,
                            project,
                            clargs.name,
                            command=clargs.command)
            project.add_item(alias, clargs.name)
            return run


        add_run_parser.set_defaults(func=command_add_run)

        add_run_parser.add_argument('name',
                                    help='Name for the run')

        add_run_parser.add_argument('command',
                                    help='Command to run')

        runs = []
        if hasattr(project, alias):
            runs = [run for run in project.iter_multival(alias)]

        # rm run
        rm_parser = get_or_add_top_level_command(parser_manager,
                                                 'rm',
                                                 'rm',
                                                 help=f'Remove config sections from {project.get_section()}')

        rm_subparser = parser_manager.get_or_add_subparser(rm_parser,
                                                           'rm-command',
                                                           help='rm sections')

        rm_run_parser = parser_manager.add_parser(rm_subparser,
                                                  alias,
                                                  'rm-' + alias,
                                                  help=f'Remove a {alias} from {project.get_section()}')

        def command_rm_run(git, gitproject, project, clargs):
            f"""Implement git-project rm {alias}"""
            run = Run.get(git, project, alias, clargs.name, command=clargs.command)
            run.rm()
            print(f'Removing project {alias} {clargs.name}')
            project.rm_item(alias, clargs.name)

        rm_run_parser.set_defaults(func=command_rm_run)

        if runs:
            rm_run_parser.add_argument('name', choices=runs,
                                       help='Command name')

        # run
        command_subparser = parser_manager.find_subparser('command')

        run_parser = parser_manager.add_parser(command_subparser,
                                               alias,
                                               alias,
                                               help=f'Invoke {alias}',
                                               epilog=self._gen_runs_epilog(alias, runs),
                                               formatter_class=
                                               argparse.RawDescriptionHelpFormatter)

        def command_run(git, gitproject, project, clargs):
            """Implement git-project run"""
            if clargs.make_alias:
                run_config = RunConfig.get(git, project)
                run_config.add_item('alias', clargs.name)
            else:
                if not clargs.name in runs:
                    raise GitProjectException(f'Unknown {alias} "{clargs.name}," choose one of: {{ {runs} }}')
                run = Class.get(git, project, clargs.name)
                run.run(git, project, clargs)

        run_parser.set_defaults(func=command_run)

        run_parser.add_argument('--make-alias', action='store_true',
                                help='Alias "{alias}" to another command')

        run_parser.add_argument('name', help='Command name or alias')

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manage):
        """Add arguments for 'git-project run.'"""
        if git.has_repo():
            # Get the global run ConfigObject and add any aliases.
            run_config = RunConfig.get(git, project)
            for alias in run_config.iter_multival('alias'):

                Class = self._make_alias_class(alias)

            for Class in self.iterclasses():
                self._add_alias_arguments(git,
                                          gitproject,
                                          project,
                                          parser_manager,
                                          Class)

    def get_class_for(self, alias):
        return self.classes[alias]

    def iterclasses(self):
        """Iterate over public classes for git-project run."""
        for key, Class in self.classes.items():
            yield Class
