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

"""A plugin to add a 'branch' command to git-project. The branch command
reports branch status against the project's branches and prunes finished
branches.

Summary:

git-project branch status (--all | --all-user | <pattern>) [<target>]
git-project branch prune [--force] [--no-ask] [--keep-remote-branch] (--all-user | <pattern>)

"""

import getpass
import sys

from git_project import (
    Git,
    GitProjectException,
    Plugin,
    Project,
    RunnableConfigObject,
    add_top_level_command,
)

from git_project_core_plugins.common import add_plugin_version_argument


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write(
                "Please respond with 'yes' or 'no' (or 'y' or 'n').\n"
            )


def command_branch_status(git, gitproject, project, clargs):
    """Implement git-project branch status."""
    ref = clargs.name_or_ref

    if not ref:
        if clargs.all_user:
            ref = "refs/heads/user/" + getpass.getuser()
        elif clargs.all:
            ref = "refs/heads"
        else:
            raise GitProjectException(
                "merged requires branch name, pattern, --all-user or --all"
            )
    else:
        if not ref.startswith("refs/"):
            ref = "refs/heads/" + ref

    target = clargs.target if clargs.target else None

    branch_width = 45
    status_width = 8
    separator_width = (
        branch_width + 2 * status_width - (status_width - len("merged"))
    )

    print("-" * separator_width)
    print(
        "{:<{branch_width}s}{:<{status_width}s}{:<{status_width}s}".format(
            "branch",
            "merged",
            "pushed",
            branch_width=branch_width,
            status_width=status_width,
        )
    )
    print("-" * separator_width)

    for branch in git.iterrefnames([ref]):
        merge_status = "no"
        if target:
            merge_status = (
                "yes" if git.refname_is_merged(branch, target) else "no"
            )
        else:
            merge_status = "yes" if project.branch_is_merged(branch) else "no"

        push_status = "yes" if project.branch_is_pushed(branch) else "no"

        print(
            "{:<{branch_width}s}{:<{status_width}s}{:<{status_width}s}".format(
                branch[: branch_width - 2],
                merge_status,
                push_status,
                branch_width=branch_width,
                status_width=status_width,
            )
        )
    print("-" * separator_width)


def command_branch_prune(git, gitproject, project, clargs):
    """Implement git-project branch prune."""
    ref = clargs.name_or_ref
    if not ref:
        if clargs.all_user:
            ref = "refs/heads/user/" + getpass.getuser()
        else:
            raise GitProjectException(
                "Prune requires branch name, pattern or --all-user"
            )
    else:
        ref = Git.branch_name_to_refname(ref)

    branch_width = 45
    status_width = 15
    separator_width = branch_width + 2 * status_width

    print("-" * separator_width)
    print(
        "{:<{branch_width}s}{:<{status_width}s}{:<{status_width}s}".format(
            "branch",
            "local status",
            "remote status",
            branch_width=branch_width,
            status_width=status_width,
        )
    )
    print("-" * separator_width)

    # FIXME: Prunes all branchs that start with the given name becuase
    # iterrefnames does a startswith match.  This is probably not what we should
    # do.
    for branch in git.iterrefnames([ref]):
        status = "merged" if project.branch_is_merged(branch) else "unmerged"

        print(
            "{:<{branch_width}s}{:<{status_width}s}".format(
                branch[: branch_width - 2],
                status,
                branch_width=branch_width,
                status_width=status_width,
            )
        )
        if clargs.force or status == "merged":
            if clargs.no_ask or query_yes_no("Prune?", default=None):
                project.prune_branch(
                    branch, keep_remote_branch=clargs.keep_remote_branch
                )


class BranchPlugin(Plugin):
    """
    The branch command queries the status of branches against the project's
    branches and prunes branches that are finished.

    Summary::

      git <project> branch status (--all | --all-user | <pattern>) [<target>]
      git <project> branch prune [--force] [--no-ask] [--keep-remote-branch] (--all-user | <pattern>)

    A <pattern> matches every branch whose name starts with it, and a name
    without ``refs/`` is looked up under ``refs/heads/``. --all-user matches
    the branches under ``user/<login>``.

    branch status prints a table of the matching branches, with whether each
    is merged to a project branch and whether it is pushed to a project
    remote. --all reports on every local branch. With <target>, merged means
    merged to <target> instead. For example::

      git <project> config --add branch release
      git <project> branch status mybranch

    The project branch defaults to the repository's main branch, main or
    master, when none is configured. config --add adds more.

    branch prune asks whether to delete each matching branch that is merged
    to a project branch, locally or on a project remote. If the answer is
    yes, it deletes the local branch and its copy on each project remote.
    A pattern matches project branches too, so check the list before you
    answer.

    With --force, branch prune offers every matching branch, merged or not.
    With --no-ask, it deletes without asking. With --keep-remote-branch, it
    deletes only the local branch and leaves the remote copies in place.
    worktree rm takes the same option, and it matters more here, because
    branch prune acts on every branch that matches the pattern.

    See also::

      config
      worktree

    """

    def __init__(self):
        super().__init__("branch")

    def add_arguments(
        self, git, gitproject, project, parser_manager, plugin_manager
    ):
        """Add arguments for 'git project branch.'"""
        # branch
        branch_parser = add_top_level_command(
            parser_manager, "branch", "branch", help="Manipulate branches"
        )

        add_plugin_version_argument(branch_parser)

        branch_subparser = parser_manager.add_subparser(
            branch_parser, "branch_command", help="branch commands"
        )

        # branch status
        branch_status_parser = parser_manager.add_parser(
            branch_subparser,
            "status",
            "branch-status",
            help="Show branch status",
        )

        branch_status_parser.set_defaults(func=command_branch_status)

        branch_status_parser.add_argument(
            "name_or_ref",
            nargs="?",
            help="Branch or pattern to filter branches",
        )
        branch_status_parser.add_argument(
            "target", nargs="?", help="Target branch to check against"
        )
        branch_status_parser.add_argument(
            "--all", action="store_true", help="Show all branches"
        )
        branch_status_parser.add_argument(
            "--all-user", action="store_true", help="Show all user's branches"
        )

        # branch prune
        branch_prune_parser = parser_manager.add_parser(
            branch_subparser,
            "prune",
            "branch-prune",
            help="Delete merged branches",
        )

        branch_prune_parser.set_defaults(func=command_branch_prune)

        branch_prune_parser.add_argument(
            "name_or_ref",
            nargs="?",
            help="Branch name or pattern to filter branches",
        )
        branch_prune_parser.add_argument(
            "--all-user", action="store_true", help="Prune all user's branches"
        )
        branch_prune_parser.add_argument(
            "--force", action="store_true", help="Prune even if unmerged"
        )
        branch_prune_parser.add_argument(
            "--no-ask", action="store_true", help="Do not ask before pruning"
        )
        branch_prune_parser.add_argument(
            "--keep-remote-branch",
            action="store_true",
            help="Keep the branch on remotes, deleting only the local copy",
        )
