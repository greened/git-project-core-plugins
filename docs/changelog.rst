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

.. _Unreleased: https://github.com/greened/git-project-core-plugins/compare/v0.0.26...HEAD
.. _0.0.26: https://github.com/greened/git-project-core-plugins/compare/v0.0.25...v0.0.26
