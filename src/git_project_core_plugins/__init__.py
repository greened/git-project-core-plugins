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

"""
************************
git-project-core-plugins
************************

Plugins for `git-project <http://www.github.com/greened/git-project>`_

This is a set of basic plugins to manage several aspects of projects kept within
git repositories.  These plugins include commands to:

#. Configure git-project and its various plugins
#. Clone repositories
#. Initialize a project in an existing repository
#. Manage branches
#. Manage worktrees
#. Run commands (e.g. configure/build/install)
#. Associate artifacts with a project
#. Show extended help for a command

These plugins add a number of commands to git-project.  Each command has an
associated ``--help`` option to describe its function and options.  There is
also a ``help`` command that accesses more extensive manpage-like descriptions
of commands.

Setup
=====

::

  pip install git-project-core-plugins

Worktree environment
====================

A number of commands can have knowledge of a "worktree environment" with a
specific layout::

  <path>
    .<name>.git
    .git
    worktree1
    worktree2
    worktree3

That is, either a bare clone is done, or an existing clone is converted to a
bare clone via ``git <project> init --worktree``.  The bare repository is the
hidden ``.<name>.git`` child, named for the last component of the remote url,
and ``<path>`` holds it alongside the worktrees. The ``.git`` beside it is a
file holding ``gitdir: .<name>.git``, so git works from ``<path>`` too. It is
a file, not a directory or a symlink, because a go build run from ``<path>``
fails if ``.git`` resolves to a directory there. Any conversion will abort if
the worktree is dirty.  Typically, an ordinary ``git clone`` is followed
immediately by ``git <project> init --worktree``.

Either route also creates a worktree for the project's main branch, so the
layout is usable straight away.  The main branch is taken from the repository
when it can be determined uniquely, and you are asked which to use when it
cannot.

The point of the layout is that each worktree can own its own build and install
trees.  Switching from worktree to worktree then does not result in "rebuilding
the world."

Examples
========

Initial setup
-------------

::

  git clone <url>
  git <project> init --worktree

Add convenience substitution variables
--------------------------------------

Configured values may reference other configured values by name, and
``{worktree}`` names the active worktree.  So a build directory written once
gives every worktree its own::

  git <project> config srcdir "{path}"
  git <project> config builddir "{srcdir}/build/{worktree}"
  git <project> config make "make -C {srcdir} BUILDDIR={builddir} {build}"

Adding custom commands
----------------------

::

  git <project> run --make-alias configure
  git <project> run --make-alias build
  git <project> run --make-alias install

  git <project> add configure debug "mkdir -p {builddir} && cd {builddir} && cmake -DCMAKE_BUILD_TYPE=Debug {srcdir}"
  git <project> configure debug
"""

from .artifact import Artifact, ArtifactPlugin
from .branch import BranchPlugin
from .run import RunPlugin
from .clone import ClonePlugin
from .common import add_plugin_version_argument
from .config import ConfigPlugin
from .help import Help, HelpPlugin
from .init import InitPlugin
from .worktree import Worktree, WorktreePlugin

from ._commanddocs import format_reference, from_classes

# The plugin classes document their own commands, so the reference is built
# from them rather than kept as a second copy that drifts. ``python -OO``
# strips the docstring, so guard against None to stay importable there.
# The prose ends in a literal block, so the join needs the newline or the
# reference heading unindents into it, which is an RST error.
__doc__ = (__doc__ or '') + '\n' + format_reference(from_classes(globals()))
