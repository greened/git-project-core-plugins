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
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

"""A plugin to add a 'run' command to git-project.  The run command invokes an
arbitrary command.  It can be used to perform any action, such as building the
project.

Summary:

git-project run <name> [<option>...]

"""

import argparse
import re
import secrets
import shlex

from git_project import (
    ConfigObject,
    GitProjectError,
    Plugin,
    RunnableConfigObject,
    get_or_add_top_level_command,
    run_command_with_shell,
)

from git_project_core_plugins.common import add_plugin_version_argument


class RunConfig(ConfigObject):
    """A ConfigObject to manage run aliases."""

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return "run"

    def __init__(self, git, project_section, subsection, ident=None, **kwargs):
        """RunConfig construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git, project_section, subsection, ident, **kwargs)

    @classmethod
    def get(cls, git, project, **kwargs):
        """Factory to construct RunConfigs.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        kwargs: Attributes to set.

        """
        return super().get(
            git, project.get_section(), cls.subsection(), None, **kwargs
        )


class RunPlugin(Plugin):
    """
    The run command executes commands via a shell.

    Summary::

      git <project> add run <name> <command>
      git <project> rm run <name>
      git <project> run --make-alias <name>
      git <project> run <name> [<option>...]

    Full shell substitution is supported, as well as config {key} substitution,
    where the text ``{key}`` is replaced by key's value. The command is printed
    after substitution. The words given after <name> on the command line are
    shell-quoted, so the shell sees each as one argument and never runs it. In
    those words only a plain {name} is substituted, and other text in braces
    is passed on as it is.

    The add run command associates a command string with a name, and rm run
    removes it. The run command itself invokes the command string via a shell.
    With --make-alias, run registers a new command, such as ``build``, that
    works like run. For example::

      git <project> run --make-alias build
      git <project> add build all "make -C {git_workdir} all"
      git <project> build all

    Each such command keeps its own list of names. So in the example above
    this fails, because ``all`` was added as a build, not a run::

      git <project> run all

    In this way we may use the same <name> for different commands, which can
    be convenient::

      git <project> build all
      git <project> check all

    The Substitution section of the git-project documentation lists the names
    a command may use, such as {git_workdir} and {branch}:
    https://pypi.org/project/git-project/

    The run command adds its own. {run}, or the alias name such as {build},
    gives the name of the command being run. An example will make this more
    clear::

      git <project> config cmd \
          "make -C {git_workdir} BLDDIR=/path/to/{build} {build}"
      git <project> add build all "{cmd}"
      git <project> add build some "{cmd}"

    We have configured two different build flavors, each which place build
    results in separate directories and invoke different targets.  Substitution
    proceeds as follows::

      git <project> build all -> make -C /cur/workarea BLDDIR=/path/to/all all
      git <project> build some -> make -C /cur/workarea BLDDIR=/path/to/some some

    Extra options passed to the run command may be referenced in the command
    string::

      git <project> add build extra "echo {options}"
      git <project> build extra hello world! -> echo hello world!

    Individual options may also be referenced::

      git <project> add build extra "echo {options_1} {options_0}"
      git <project> build extra hello world! -> echo world! hello

    A special dash-separated "key" string composed of option values may be
    generated::

      git <project> add build any "make {option_key}"
      git <project> build any target debug -> make target-debug

    A special {option_keysep} substitution will result in a - if there are
    options and the empty string otherwise::

      git <project> add build any "make my{option_keysep}{option_key}"
      git <project> build any target debug -> make my-target-debug
      git <project> build any -> make my

    Other substitutions may be used in options::

      git <project> add build branch "make {options}"
      git <project> build branch {branch} -> make dev  # On the dev branch

    A special substitution {option_names} gives the options separated by
    spaces, with their braces removed, so they are not substituted::

      git <project> add build branch "make {option_names} {options}"
      git <project> build branch {branch} -> make branch dev  # On the dev branch

    Inside a worktree, a value set for that worktree overrides the project's
    value of the same name. See the Scopes section of the git-project
    documentation.

    See also::

      config
      worktree

    """

    def __init__(self):
        super().__init__("run")
        self.classes = {}
        self.classes["run"] = self._make_alias_class("run")

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

        alias_class = type(
            alias + "Class",
            (RunnableConfigObject,),
            {
                #            __doc__ = f"""A RunnableConfigObject to manage {alias} names.  Each run name gets its own
                #            config section.
                #
                #            """
                "subsection": subsection,
                "get_managing_command": get_managing_command,
            },
        )

        def cons(self, git, project_section, subsection, ident, **kwargs):
            # Construct one alias object.
            super(alias_class, self).__init__(
                git, project_section, subsection, ident, **kwargs
            )

        @classmethod
        def get(cls, git, project, name, **kwargs):
            # Look up or make one alias object.
            return super(alias_class, cls).get(
                git, project.get_section(), cls.subsection(), name, **kwargs
            )

        alias_class.__init__ = cons
        alias_class.get = get

        self.classes[alias] = alias_class
        return alias_class

    def _gen_runs_epilog(self, git, project, alias, runs):
        result = f"Available {alias}s:\n"
        run_width = 20
        for run in runs:
            help_section = f"{project.get_section()}.help.{alias}.{run}"
            help_key = "short"
            if git.config.has_item(help_section, help_key):
                shorthelp = git.config.get_item(help_section, help_key)
                result += f"    {run:<{run_width}} - {shorthelp}\n"
            else:
                result += f"    {run}\n"

        return result

    def _add_alias_arguments(
        self, git, gitproject, project, parser_manager, alias_class
    ):
        alias = alias_class.get_managing_command()

        # add run
        add_parser = get_or_add_top_level_command(
            parser_manager,
            "add",
            "add",
            help=f"Add config sections to {project.get_section()}",
        )

        add_subparser = parser_manager.get_or_add_subparser(
            add_parser, "add-command", help="add sections"
        )

        add_run_parser = parser_manager.add_parser(
            add_subparser,
            alias,
            "add-" + alias,
            help=f"Add a {alias} to {project.get_section()}",
        )

        def command_add_run(git, gitproject, project, clargs):
            # Implement git-project add {alias}
            run = alias_class.get(
                git, project, clargs.name, command=clargs.command
            )
            project.add_item(alias, clargs.name)
            return run

        add_run_parser.set_defaults(func=command_add_run)

        add_run_parser.add_argument("name", help="Name for the run")

        add_run_parser.add_argument("command", help="Command to run")

        runs = []
        if hasattr(project, alias):
            runs = list(project.iter_multival(alias))

        # rm run
        rm_parser = get_or_add_top_level_command(
            parser_manager,
            "rm",
            "rm",
            help=f"Remove config sections from {project.get_section()}",
        )

        rm_subparser = parser_manager.get_or_add_subparser(
            rm_parser, "rm-command", help="rm sections"
        )

        rm_run_parser = parser_manager.add_parser(
            rm_subparser,
            alias,
            "rm-" + alias,
            help=f"Remove a {alias} from {project.get_section()}",
        )

        def command_rm_run(git, gitproject, project, clargs):
            # Implement git-project rm {alias}
            if clargs.name not in project.iter_multival(alias):
                raise GitProjectError(f"No {alias} named {clargs.name}")
            run = alias_class.get(git, project, clargs.name)
            run.rm()
            print(f"Removing project {alias} {clargs.name}")
            project.rm_item(alias, clargs.name)

        rm_run_parser.set_defaults(func=command_rm_run)

        # Offer the names as choices when there are some. The argument is
        # needed either way, or the command has no name to remove.
        rm_run_parser.add_argument(
            "name", choices=runs if runs else None, help="Command name"
        )

        # run
        command_subparser = parser_manager.find_subparser("command")

        run_parser = parser_manager.add_parser(
            command_subparser,
            alias,
            alias,
            help=f"Invoke {alias}",
            epilog=self._gen_runs_epilog(git, project, alias, runs),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        def command_run(git, gitproject, project, clargs):
            """Implement git-project run"""
            if clargs.make_alias:
                run_config = RunConfig.get(git, project)
                run_config.add_item("alias", clargs.name)
            else:
                if clargs.name not in runs:
                    raise GitProjectError(
                        f'Unknown {alias} "{clargs.name}," choose one of: {{ {runs} }}'
                    )
                run = alias_class.get(git, project, clargs.name)

                translation_table = dict.fromkeys(map(ord, "{}"), None)

                # An option may name a value, such as {branch}. Only a plain
                # {name} is looked up. The substitution evaluates what it is
                # given as Python, so anything else in braces stays text.
                def substitute_names(option):
                    return re.sub(
                        r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
                        lambda match: run.substitute_value(
                            git, project, "{" + match.group(1) + "}", {}
                        ),
                        option,
                    )

                words = [substitute_names(option) for option in clargs.options]
                names = [
                    option.translate(translation_table)
                    for option in clargs.options
                ]
                option_key = "-".join(names)

                # The command runs through a shell, so each word from the
                # command line is shell-quoted, or a ';' in one would run as
                # shell. The quoting cannot go into the substitution itself,
                # which evaluates every value as a Python f-string that a
                # quote would break. So a plain placeholder stands in for each
                # word during substitution, and the quoted word replaces it
                # afterward.
                token = secrets.token_hex(8)

                def placeholder(name):
                    return f"GITPROJECT{token}{name}END"

                quoted = {
                    placeholder("options"): " ".join(
                        shlex.quote(word) for word in words
                    ),
                    placeholder("optionnames"): " ".join(
                        shlex.quote(name) for name in names
                    ),
                    placeholder("optionkey"): (
                        shlex.quote(option_key) if option_key else ""
                    ),
                }

                formats = {
                    "options": placeholder("options"),
                    "option_names": placeholder("optionnames"),
                    "option_key": placeholder("optionkey"),
                    "option_keysep": "-" if len(clargs.options) > 0 else "",
                }

                for i, word in enumerate(words):
                    formats[f"options_{i}"] = placeholder(f"option{i}")
                    quoted[placeholder(f"option{i}")] = shlex.quote(word)

                command = run.substitute_command(git, project, formats)
                for name, value in quoted.items():
                    command = command.replace(name, value)

                print(command)

                return run_command_with_shell(command)

        run_parser.set_defaults(func=command_run)

        add_plugin_version_argument(run_parser)

        run_parser.add_argument(
            "--make-alias",
            action="store_true",
            help=f'Alias "{alias}" to another command',
        )

        run_parser.add_argument("name", help="Command name or alias")

        run_parser.add_argument(
            "options", nargs="*", help="Additions options to pass to command"
        )

    def add_arguments(
        self, git, gitproject, project, parser_manager, plugin_manage
    ):
        """Add arguments for 'git-project run.'"""
        if git.has_repo():
            # Get the global run ConfigObject and add any aliases.
            run_config = RunConfig.get(git, project)
            for alias in run_config.iter_multival("alias"):

                alias_class = self._make_alias_class(alias)

            for alias_class in self.iterclasses():
                self._add_alias_arguments(
                    git, gitproject, project, parser_manager, alias_class
                )

    def get_class_for(self, alias):
        return self.classes[alias]

    def iterclasses(self):
        """Iterate over public classes for git-project run."""
        yield from self.classes.values()
