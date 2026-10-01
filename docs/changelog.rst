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

ChangeLog
=========
`Unreleased`_
-------------
Changed
.......
- Removing a config object now refuses to remove an artifact path that is,
  or contains, the root, the home directory, the working copy or the git
  common dir. A glob that matches one of them removes nothing at all.

Fixed
.....
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

.. _Unreleased: https://github.com/greened/git-project-core-plugins/compare/v0.0.27...HEAD
.. _0.0.27: https://github.com/greened/git-project-core-plugins/compare/v0.0.26...v0.0.27
.. _0.0.26: https://github.com/greened/git-project-core-plugins/compare/v0.0.25...v0.0.26
