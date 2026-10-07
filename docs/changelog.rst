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
    FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License
    for more details.

..
    You should have received a copy of the GNU Affero General Public License
    along with git-project. If not, see <https://www.gnu.org/licenses/>.

ChangeLog
=========
`Unreleased`_
-------------
Added
.....
- ``worktree migrate`` converts a store already bare at ``<top>/.git``
  with its worktrees inside ``<top>``. It renames the store to the hidden
  name, writes the ``.git`` file and repairs each worktree. An absolute
  ``commondir`` becomes ``../..``, so each worktree finds the renamed
  store. Worktrees may be nested, such as ``<top>/x/b1``. A file or
  directory on the way to a worktree that holds no worktree is refused,
  unless its name starts with ``.``. Sparse checkouts and skip-worktree
  files are allowed in this form.
- ``worktree migrate`` lists each local branch with commits that its
  upstream lacks. A branch with no upstream, or one that is gone, is
  compared with the main branch.
- ``worktree migrate --apply`` runs the command in
  ``<project>.postmigrate`` in the top-level directory after a successful
  migration. ``<project>.postmigratetimeout`` sets its time limit in
  seconds, 600 by default and 86400 at most. The manifest records the result.

Changed
.......
- A ``worktree migrate --apply`` failure prints the reason as well as the
  step. When ``verify`` finds a worktree that is not clean, it names up to
  10 of the changed or untracked paths. Like the precheck, it ignores
  ``status.showUntrackedFiles`` and ``submodule.<name>.ignore``.

`0.0.29`_ - 2026-10-06
----------------------
Added
.....
- ``worktree migrate`` converts a flat clone and its linked worktrees to the
  worktree layout. It keeps every branch, ref, stash and config, and changes
  nothing without ``--apply``.

Changed
.......
- core-plugins now needs git-project 0.0.41 or later. That release no
  longer evaluates a config value as Python, so an expression such as
  ``{branch.replace(...)}`` in a config value stays as written. Only a
  plain ``{name}`` is replaced.
- The ``artifact`` manual says that the <path> given to ``artifact rm`` is
  a regular expression. Escape characters such as ``{`` and ``.`` to match
  them literally.

Fixed
.....
- ``worktree rm`` stopped removing directories at the first one it could
  not remove. A worktree with no builddir kept its prefix and installdir.
  Each directory is now removed on its own.

`0.0.28`_ - 2026-10-05
----------------------
Changed
.......
- core-plugins now needs git-project 0.0.40 or later. That release passes
  the value given to ``artifact rm`` or ``config --unset`` to git as one
  argument. So a path or value that holds a space can be removed. The value
  is a regular expression, and one escaped twice to get past the old split
  must now be escaped once.
- The command manuals that ``git <project> help <command>`` shows are
  corrected against the code. Several synopses named options that do not
  exist or left out required arguments, and ``artifact`` showed the
  ``config`` plugin's description. The package description now links to
  git-project's Substitution and Scopes sections rather than repeating them.
- Removing a config object now refuses to remove an artifact path that is,
  or contains, the root, the home directory, the working copy or the git
  common dir. A glob that matches one of them removes nothing at all.

Fixed
.....
- The words given to ``run`` and its aliases after the name went into the
  command unquoted, and the command runs through a shell. So a ``;``,
  ``|`` or ``$( )`` in one ran as shell, and text in braces ran as Python.
  ``{options}``, ``{options_N}``, ``{option_names}`` and ``{option_key}`` now
  shell-quote each word, and only a plain ``{name}`` in a word is
  substituted.
- ``init --worktree`` in a repository with no ``origin`` remote ended in a
  Python traceback. In a repository that was not bare, it had by then set
  ``core.bare`` and deleted the files in the workarea. It now checks for the
  remote first and reports a missing one without changing anything.
- ``worktree add`` with no path ended in a Python traceback, and its help
  said a missing path would be inferred. The path is now a required
  argument, so a missing one gives a usage error.
- ``rm run <name>``, and ``rm`` for any run alias, failed with a
  ``NameError`` and never removed anything. It also took no name when no
  runs were defined. It now removes the named run, and an unknown name is an
  error.
- ``branch status <pattern> <target>`` failed with an ``AttributeError``. It
  called a ``Git`` method that does not exist. It now reports whether each
  branch is merged to <target>.
- Removing a config object removed its artifacts with ``rm -rf`` through a
  shell, so a path that held a space deleted the wrong directories. A path
  with ``a b`` in it removed ``a`` and ``b`` instead. Artifacts are now
  removed without a shell. A leading ``~`` and ``$VAR`` references are
  still expanded. A path that exists is taken literally, and otherwise it is
  expanded as a glob, as before. A variable that is not set is now left as
  written, where the shell made it empty.
- The package description now shows the ``.git`` file that ``clone
  --worktree`` and ``init --worktree`` write, and says why it is a file.
- The last example in the package description stopped partway through a
  command. It now shows a whole ``configure`` command and how to run it.

`0.0.27`_ - 2026-09-30
----------------------
Fixed
.....
- ``clone --worktree`` and ``init --worktree`` now write a ``.git`` file
  beside the hidden bare clone, holding ``gitdir: .<urlname>.git``. The
  container was not a repository before, so any tool that stood there and
  asked git a question got nothing, and callers worked around it by reaching
  for ``common_dir`` themselves.

  It has to be a file. The hidden name exists because a go build run from the
  container fails when a ``.git`` that resolves to a directory sits above the
  module, since go then runs ``git status`` against the bare clone. A symlink
  resolves to a directory and fails the same way. Go walks past a ``.git``
  file, while git and pygit2 follow it, so a file serves both.

  A repository that was already bare when ``init --worktree`` ran keeps its
  ``.git`` as the clone itself and gets no pointer.

`0.0.26`_ - 2026-09-27
----------------------
Added
.....
- ``worktree rm`` takes ``--keep-branch`` and ``--keep-remote-branch``. It
  previously pruned the worktree's branch, locally and from every project
  remote, unless the project configured that branch, so retiring a worktree
  destroyed its branch. ``--keep-branch`` skips the prune entirely and
  supersedes ``--keep-remote-branch``.
- ``branch prune`` takes ``--keep-remote-branch``, the same option
  ``worktree rm`` takes. It matters more here, because ``branch prune`` acts on
  every branch matching the pattern.

Changed
.......
- git-project 0.0.38 or later is now required. ``worktree rm`` and
  ``branch prune`` both pass ``keep_remote_branch``, which older versions do
  not accept, so pruning a branch raises ``TypeError``.
- Python 3.10 or later is now required, matching git-project.
- The docstrings are now the single source for this package's documentation.
  The command reference is generated from the plugin classes, and both the
  Sphinx docs and the PyPI description are built from the module docstring
  and that reference. This release is the first to publish them, which meant
  making them render: command blocks were quoted prose rather than literal
  text, and one wrapped synopsis was an outright error.

Fixed
.....
- ``branch prune`` without ``--no-ask``, which is the interactive path and the
  default, raised ``NameError``. The module never imported ``sys``, which
  ``query_yes_no`` uses, so that path had never worked.
- ``git <project> help <command>`` showed wrong text. The ``worktree config``
  synopsis omitted the identifier the command takes first, so the documented
  form could not work. A ``run`` example repeated a word and could not be
  pasted. A third of the ``artifact`` description was about the worktree
  plugin.
- The worktree plugin's description said nothing about ``worktree rm``
  deleting the branch. It now states that default and its exception.
- The Issues and Documentation links on the PyPI project page both returned
  404. Issues named ``unknown/greened``, a leftover from hatch's project
  template, and Documentation misspelled the package name.

.. _Unreleased: https://github.com/greened/git-project-core-plugins/compare/v0.0.29...HEAD
.. _0.0.29: https://github.com/greened/git-project-core-plugins/compare/v0.0.28...v0.0.29
.. _0.0.28: https://github.com/greened/git-project-core-plugins/compare/v0.0.27...v0.0.28
.. _0.0.27: https://github.com/greened/git-project-core-plugins/compare/v0.0.26...v0.0.27
.. _0.0.26: https://github.com/greened/git-project-core-plugins/compare/v0.0.25...v0.0.26
