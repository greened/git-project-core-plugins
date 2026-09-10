..
    SPDX-FileCopyrightText: 2023-present David A. Greene <dag@obbligato.org>

..
    SPDX-License-Identifier: AGPL-3.0-or-later

..
    Copyright 2023 David A. Greene

..
    This file is part of git-project

..
    git-project is free software: you can redistribute it and/or modify it under
    the terms of the GNU Affero General Public License as published by the Free
    Software Foundation, either version 3 of the License, or (at your option)
    any later version.

..
    This program is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
    more details.

..
    You should have received a copy of the GNU Affero General Public License
    along with git-project. If not, see <https://www.gnu.org/licenses/>.

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

Setup
=====

::

  pip install git-project-core-plugins

Commands
========

These plugins add a number of commands to git-project.  Each command has an
associated ``--help`` option to describe its function and options.  There is
also a ``help`` command that accesses more extensive manpage-like descriptions
of commands.

* ``git <project> config [--add] [--unset] <name> [<value>]``

  Configure git-project or any git config sections added by projects.  This will
  add ``config`` subcommands to plugin commands that manipulate git config
  sections (e.g. ``git project build config``).

* ``git <project> clone <url> [<path>] [--bare] [--worktree]``

  Clone a repository.  Other plugins may hook into this command to provide
  additional functionality.  With ``--worktree``, set up a worktree environment.

* ``git <project> init [--worktree]``

  Initialize a ``git-project`` config in an existing cloned repository.  With
  ``--worktree``, set up a worktree environment.

* ``git <project> branch status [--all] [<refish>]``

  Report whether local branches are merged to a project branch and whether the
  local branch head is pushed to a remote.

* ``git <project> branch prune [--force] [--no-ask] [--keep-remote-branch]``

  Delete branches that are merged to a project branch and pushed to a remote.
  This acts on every branch matching the pattern, so it is the batch command.
  With ``--keep-remote-branch``, delete only the local branch and leave the
  copy on every remote in place.

* ``git <project> run <command> [<args>]``

  Run a pre-configured command, passing ``<args>`` to it.  With
  ``git <project> run --make-alias <name>``, promote a configured command to a
  top-level command of its own.

* ``git <project> worktree add [-b <branch>] <name-or-path> [<committish>]``

  Create a worktree with ``<committish>`` checked out.  With ``-b``, create the
  branch at ``HEAD``, or at ``<committish>`` when one is given.

* ``git <project> worktree rm [-f] [--keep-branch] [--keep-remote-branch] <name-or-path>``

  Remove a worktree, along with its workarea and its associated build and
  install trees.  The branch is deleted too, locally and on every remote, unless
  a flag says otherwise: ``--keep-branch`` leaves the branch alone everywhere,
  and ``--keep-remote-branch`` deletes only the local copy.  Removing a worktree
  whose branch is unmerged requires ``-f``, unless ``--keep-branch`` means the
  branch survives anyway.

* ``git <project> worktree config [--unset] <key> [<value>]``

  Configure a key in the worktree's own config scope, overriding the
  project-level value of the same key.

* ``git <project> artifact add <subsection> <path>``

  Associate an artifact with a project, so that removing the thing that owns it
  removes the artifact too.

* ``git <project> help <command>``

  Show the extended description of a command.  Add such text with
  ``git <project> add help [--manpage] <subsection> <text>``.

Worktree environment
====================

A number of commands can have knowledge of a "worktree environment" with a
specific layout::

  <path>
    .git
    worktree1
    worktree2
    worktree3

That is, either a bare clone is done, or an existing clone is converted to a
bare clone via ``git <project> init --worktree``.  Any conversion will abort if
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

  git <project> add configure debug "cd {builddir} && "
