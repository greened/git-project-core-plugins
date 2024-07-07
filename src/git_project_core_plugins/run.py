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

"""A plugin to add a 'run' command to git-project.  The run command invokes an
arbitrary command.  It can be used to perform any action, such as building the
project.

Summary:

git-project run <name>

"""

from git_project import ConfigObject, RunnableConfigObject, Plugin, Project
from git_project import get_or_add_top_level_command, GitProjectException

from git_project_core_plugins.common import add_plugin_version_argument

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
    """
    The run command executes commands via a shell.

    Summary:

      git <project> add run <name> <command>
      git <project> run --make-alias <name>
      git <project> run <name>

    Full shell substitution is supported, as well as config {key} substitution,
    where the text ``{key}'' is replaced by key's value.

    The add run command associates a command string with a name.  The run
    command itself invokes the command string via a shell.  With --make-alias,
    the run comand instead registers an alternative name for ``run.''  For
    example:

      git <project> run --make-alias build
      git <project> add build all "make -C {path} all"
      git <project> build all

    Note that an alias will prevent ``run'' from invoking the command so in the
    above example we could not invoke the build as such:

      git <project> run all

    In this way we may use the same <name> for different registered run aliases,
    which can be convenient:

      git <project> build all
      git <project> check all

    In general any project config {key} will be replaced with its value before
    the command is executed.  Substitution occurs recursively, so if a {key}
    value itself contains a substitution string, it will be replaced as well.
    There are a few special case substitutions.  The {path} key will be replaced
    by the absolute path to the root of the current workarea.  The {branch} key
    will be replaced by the currently-active branch nme.  In addition the {run}
    (or {build}, etc. aliases) will be replaced by their names.  Again, an
    example will make this more clear:

      git <project> config cmd "make -C {path} BLDDIR=/path/to/{build} {build}"
      git project add build all "{cmd}"
      git project add build some "{cmd}"

    We have configured two different build flavors, each which place build
    results in separate directories and invoke different targets.  Substitution
    proceeds as follows:

      git project build all -> make -C /cur/workarea BLDDIR=/path/to/all all
      git project build some -> make -C /cur/workarea BLDDIR=/path/to/some some

    Some plugins may add scoping rules to the project config, such that a scope
    nested inside the project may override the global project config key value.
    For example the worktree plugin adds a ``worktree'' scope.  The worktree may
    contain key values that override similar keys in the project config.

    See also:

      config
      worktree

    """
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

    def _gen_runs_epilog(self, git, project, alias, runs):
        result = f'Available {alias}s:\n'
        run_width = 20
        for run in runs:
            help_section = f'{project.get_section()}.help.{alias}.{run}'
            help_key = 'short'
            if git.config.has_item(help_section, help_key):
                shorthelp = git.config.get_item(help_section, help_key)
                result += f'    {run:<{run_width}} - {shorthelp}\n'
            else:
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
                                               epilog=self._gen_runs_epilog(git,
                                                                            project,
                                                                            alias,
                                                                            runs),
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

                translation_table = dict.fromkeys(map(ord, '{}'), None)

                option_names = ' '.join(clargs.options)
                option_names = option_names.translate(translation_table)
                option_key = '-'.join(clargs.options)
                option_key = option_key.translate(translation_table)

                formats = {
                    'options': ' '.join(clargs.options),
                    'option_names': option_names,
                    'option_key': option_key,
                    'option_keysep': '-' if len(clargs.options) > 0 else ''
                }

                run.run(git, project, formats)

        run_parser.set_defaults(func=command_run)

        add_plugin_version_argument(run_parser)

        run_parser.add_argument('--make-alias', action='store_true',
                                help=f'Alias "{alias}" to another command')

        run_parser.add_argument('name', help='Command name or alias')

        run_parser.add_argument('options',
                                nargs='*',
                                help='Additions options to pass to command')

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
