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
========================
git-project-core-plugins
========================

Plugins for `git-project <http://www.github.com/greened/git-project>`_

This is a set of basic plugins to manage several aspects of projects kept within
git repositories.  These plugins include commands to:

#. Configure git-project and its various plugins
#. Clone repositories
#. Manage branches
#. Manage worktrees
#. Run commands (e.g configure/build/install)

Setup
=====

``pip install git-project-core-plugins``

Commands
========

These plugins add a number of commands to git-project.  Each command has an
associated ``--help`` option to describe its function and options.  There is
also a `help` command that accesses more extensive manpage-like descriptions of
commands.

* ``git <project> config``

  Configure git-project or any git config sections added by projects.  This will
  add ``config`` subcommands to plugin commands that manipulate git config
  sections (e.g. ``git project build config``).

* ``git <project> clone [--worktree]``

  Clone a repository.  Other plugins may hook into this command to provide
  additional functionality.  With ``--worktree``, set up a worktree environment.

* ``git <project> init [--worktree]``

  Initialize a ``git-project`` config in an existing cloed repository.  With
  ``--worktree``, setup a worktree environment.

* ``git <project> branch status``

  Report whether local branches are merged to a project branch and whether the
  local branch head is pushed to a remote.

* ``git <project> branch prune``

  Delete branches that are merged to a project branch and pushed to a remote.

* ``git <project> run <command> [<args>]``

  Run a pre-configured commandm, passing ``<args>`` to it.

* ``git <project> worktree``

  Create and manage worktrees for the project.  This plugin gives ``git
  <project> clone`` an option to create a special directory layout and a master
  worktree when performing a bare clone.

  Worktrees can be referenced to set up per-worktree build and install trees
  such that switching from worktree to worktree does not result in "rebuilding
  the world."

Worktree environment
====================

A number of commands can have knowledge of a "worktree environment" with a
specific layout:

  <path>
    .git
    worktree1
    worktree2
    worktree3

That is, either a bare clone is done, or an existing clone is converted to a
bare clone via ``git <project> init --worktree``.  Any conversion will abort if
the worktree is dirty.  Typically, an ordinary ``git clone`` is followed
immediately by ``git <project> init --worktree``.

Examples
========

Initial setup
-------------

  git clone <url>
  git <project> init --worktree

Add convenience substitution variables
--------------------------------------

Adding custom commands
----------------------

  git <project> run --make-alias configure
  git <project> run --make-alias build
  git <project> run --make-alias install

  git <project> add configure debug "cd {builddir} && "

Command Reference
-----------------

artifact
--------
The artifact command adds or removes associations between git config objects
and file-system objects.

Summary:

  git <project> artifact add <subsection> <path>
  git <project> artifact rm <subsection> [<path>]

<subsection> is a git config section which will appear under the
<project>.artifact section.  Artifacts look up objects associated with
<subsection> and perform substitutions on paths to yield the final
associated file-system object.  The ``artifact rm`` command simply removes
an artifact association, it does not remove the artifact itself.  Multiple
artifact paths may be associated under a single <subsection> and the option
<path> argument to ``artifact rm`` allows us to remove a single association
rather than all of them at once.

For example:

  git <project> artifact add worktree.myworktree /path/to/artifact

Presumably, /path/to/artifact is in some way created in association with
myworktree, for example by the ``run`` command.  When we delete myworktree,
the artifact association causes /path/to/artifact to also be removed.
Substitutions can make artifact associations easier to manage:

  git <project> artifact add worktree /path/to/{worktree}/artifact

Notice that we've added the artifact under the more general ``worktree``
subsection instead of naming a worktree explicitly as before.  Because the
{worktree} substitution appears in the artifact path, deleting any worktree
will cause the worktree's name to be substituted into the artifact path,
forming a unique artifact path to remove.

We may make this even more general:

  git <project> config srcdir "{path}"
  git <project> config builddir "{srcdir}/build/{worktree}"
  git <project> config make "make -C {srcdir} BUILDDIR={builddir} {build}"
  git <project> run --make-alias build
  git <project> add build debug "{make}"
  git <project> add build release "{make}"
  git <project> add build check "{make}"
  git <project> artifact add worktree "{builddir}"

We've added a single artifact association that will handle any worktree and
all of our different build types.  When we delete the worktree, all
artifacts related to debug, release and check builds will also be removed.

The worktree plugin also modifies the clone and init commands, adding a
--worktree option to both.  With --worktree, clone will create a ``worktree
layout`` as so:

  clonedir
    .git
     master

Here, ``master`` is a worktree created from the master branch.  ``clonedir``
becames a bare repository, though with refspecs that make it operate like a
regular clone for fetch and push operations.  That is, the cloned repository
will still have refs/heads and refs/remotes namespaces.

With --worktree, init will take an existing local clone and convert it to a
bare repository, removing all checked out files and creating a master
worktree:

  clonedir
    .git
     master

Conversion will abort if the workarea is not in a clean state.  Note that
all files in clonedir will be deleted so if there are important files not
part of the underlying repository, the user must take care to preserve them.
If the workarea hd a branch other than master checked out, no worktree for
it will be created automatically, though the user may easily create one
after conversion.

See also:

  clone
  config
  init
  run
  worktree

branch
------
The branch command queries the status of branches against known project
branches and provides methods to prune old branches.

Summary:

  git <project> branch status [--all] [<refish>]
  git <project> branch prune [--force] [--no-ask]

The branch status command checks the given <refish> (or all local branches
with the --all option) against the project-configured branches.  The command
outputs a table of branches and whether they are merged to a project branch
and/or pushed to a remote.  For example:

  git <project> config --add branch release
  git <project> branch status mybranch

The report will show whether mybranch is merged to the release or master
branches (master is always a configured project branch) and whether the
commit pointed to mybranch is pushed to a remote.

The branch prune command computes the same information and if the branch is
merged to a project branch and that project branch is pushed to a remote,
will ask whether mybranch should be deleted.  If the user indicates yes,
both the local mybranch and its remote counterpart, if any, will be deleted.

With --force, branches will be pruneed regardless of merge/push status.
With --no-ask branch prune operates in batch mode, assuming all merged and
pushed branches should be pruned.

See also:

  config

clone
-----
The clone command clones a repository.

Summary:

  git <project> clone <url> [<path>] [--bare]

By itself clone has just the very basic funcionality of the built-in git
clone command.  Plugins may add options to give the clone command more
features.  For example, the woktree command adds a --worktree option to have
clone create a ``worktree layout.``

See also:

  worktree

config
------
The config command manages git config settings under the <project> section.

Summary:

  git <project> config [--add] [--unset] <name> [<value>]

The config command operates much like git's built-in config command, except
all configuration keys are prefixed with <project>, keeping values under a
single project namespace.  This is a convenient way to store parameters for
other commands.  For example:

  git <project> config builddir /path/to/build
  git <project> add run build "make BUILDDIR={builddir} all"

Configuration kays may have their values substituted into other
configuration values via the {key} specifier.  Special commands like build
perform the substitution recursively, so configuration vaalues may contain
substitutions of other configuration values which themselves contain
substitutions, and so on.  Importantly, substitution only happens when
commands are run.  Commands should document whether or not they perform
substitutions.

A git config ``sub-section`` may be substituted with its identifier.  For
example:

  git <project> worktree add myworktree
  git <project> config builddir /path/to/{worktree}/build

Here, myworktree is the identifier of a specific worktree sub-section.  If
myworktree is the currently active worktree (that is, the current directory
is under the myworktree root), then ``myworktree`` will substitute for
{woktree}.

See also:

  run
  worktree

help
----
The help command displays tutorial-style help for commands.

Summary:

  git <project> add help [--manpage] <subsection> <text>
  git <project> help <command>

Users may add help to any project config section.  For example:

  git <project> add help run.build "Perform a build"
  git <project> add help run.check "Run tests"

All help is stored under a <project>.help config sub-section.  If a command
supports it, such help may appear in the command's own help output by
querying the appropriate <project>.help sub-section:

  git <project> run --help

  <standard help text>

  build     -- Perform a build
  check     -- Run tests

In this way projects can self-document their configurations.  Normally
<text> is stored in <project>.help.<subsection>.short.  With --manpage,
<text> is stored in <project>.help.<subsection>.manpage.  Commands may
reference short help or manpages in various ways to present help.

See also:

  run

init
----
The init command initializes project state.

Summary:

  git <project> init

Basic config entries are added to name the project and default branches.
Plugins may add options to enhance functionality.  For example the worktree
command adds a --worktree option to convert an existing local clone to a
``worktree layout.``

See also:

  worktree

run
---
The run command executes commands via a shell.

Summary:

  git <project> add run <name> <command>
  git <project> run --make-alias <name>
  git <project> run <name>

Full shell substitution is supported, as well as config {key} substitution,
where the text ``{key}`` is replaced by key's value.

The add run command associates a command string with a name.  The run
command itself invokes the command string via a shell.  With --make-alias,
the run comand instead registers an alternative name for ``run.``  For
example:

  git <project> run --make-alias build
  git <project> add build all "make -C {path} all"
  git <project> build all

Note that an alias will prevent ``run`` from invoking the command so in the
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
For example the worktree plugin adds a ``worktree`` scope.  The worktree may
contain key values that override similar keys in the project config.

See also:

  config
  worktree

worktree
--------
The worktree command manages worktrees and connects them to projects.

Summary:

  git <project> worktree add [-b <branch>] <name-or-path> [<committish>]
  git <project> worktree rm <name-or-path>
  git <project> worktree config <key> [<value>]
  git <project> worktree config [--unset] <key> [<value>]

``worktree add`` creates a new git worktree named via <name-or-path> with
<committish> checked out.  If we pass -b <branch> we'll get a new branch at
HEAD or <committish> if it is given.  The worktree name is either the given
name or if name-or-path is a path, the worktree name will be the same as the
last path component.  If <name-or-path> is a simple name with no directory
separators, the worktree will be created as a sub-directory of the current
directory.

To keep things simple, we'll usually always name worktrees similarly (or
identically) to the branches they reference, though it is not strictly
necessary to do so.

The key idea behind project worktrees is that they are connected to various
``artifacts.``  Worktrees are managed together with this artifacts to
provide a project-level view of various tasks.  For example, a ``run``
command can create artifacts associated with a worktree.  Removing the
worktree implicitly removes thee artifacts, making build cleanups easy and
convenient.  Commands may use the {worktree} substitution to create
worktree-unique artifacts.  Other substitutions may also referece {worktree}
in a recursive manner.

Here is a concrete example:

  git <project> config srcdir "{path}"
  git <project> config builddir "{srcdir}/build/{worktree}"
  git <project> config make "make -C {srcdir} BUILDDIR={builddir} {build}"
  git <project> run --make-alias build
  git <project> add build release "{make}"

Assuming the build system uses BUILDDIR to determine where build artifacts
go, each worktree will get a unique set of build artifacts, via the
{builddir} and, recursively., {worktree} substitutions.  When we delete the
worktree, we'll also delete the associoated build directory.

We associate artifacts with worktrees via the artifact commands.

Another important benefit of worktrees and associated builds is that
switching to work on a new worktree (by simply editing sources in a
different worktree directory) will not result in build artifacts from thte
previous worktree being overwritten.  Thus we avoid the ``rebuild the
world`` problems of switching branches within the same workarea.  Generally,
each created branch will have its own worktree and we will rarely, if ever,
switch branches within a worktree.

A worktree layers a config scope on top of the global project scope, so that
configuring a key in the worktree with the same name as a key in the project
will cause the worktree key's value to override the project key's value:

  git <project> config buildwidth 16
  git <project> worktree config buildwidth 32

If we are in a worktree configured with buildwidth=32, then wherever
{buildwidth} apeears (say, in a run command), the value 32 will be
substituted instead of 16.  If we are outside the worktree (for example a
worktree without a buildwidth configured), then {buildwidth} will be
substituted with 16.

See also:

  artifact
  config
  run
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
