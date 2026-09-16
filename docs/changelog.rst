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

`0.0.26`_ - 2026-09-15
----------------------
Added
.....
- ``worktree rm`` takes ``--keep-branch`` and ``--keep-remote-branch``. It
  previously always pruned the worktree's branch, locally and from every
  project remote, so retiring a worktree destroyed its branch.
  ``--keep-branch`` skips the prune entirely and supersedes
  ``--keep-remote-branch``.
- ``branch prune`` takes ``--keep-remote-branch``, the same option
  ``worktree rm`` takes. It matters more here, because ``branch prune`` acts on
  every branch matching the pattern.

Changed
.......
- git-project 0.0.38 or later is now required. ``Worktree.rm`` passes
  ``keep_remote_branch`` unconditionally, so against an older git-project even
  a plain ``worktree rm`` raises ``TypeError``.
- Python 3.10 or later is now required, matching git-project.
- The user documentation now lives in ``docs/intro.rst``, which also supplies
  the PyPI description.

Fixed
.....
- ``branch prune`` without ``--no-ask``, which is the interactive path and the
  default, raised ``NameError``. The module never imported ``sys``, which
  ``query_yes_no`` uses, so that path had never worked.
- ``worktree rm`` no longer demands ``-f`` for an unmerged branch under
  ``--keep-branch``. The branch survives there both locally and on every
  remote, so its merge state cannot cost anything.

.. _Unreleased: https://github.com/greened/git-project-core-plugins/compare/v0.0.26...HEAD
.. _0.0.26: https://github.com/greened/git-project-core-plugins/compare/v0.0.25...v0.0.26
