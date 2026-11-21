..
    SPDX-FileCopyrightText: 2026-present David A. Greene <dag@obbligato.org>

..
    SPDX-License-Identifier: AGPL-3.0-or-later

..
    Copyright 2026 David A. Greene

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

Umbrellas for other tools
=========================

This page is for a tool that works with an umbrella made by
git-project-core-plugins but does not use git-project itself. The
:doc:`intro` describes the layout. ``clone --worktree``, ``init
--worktree`` and ``worktree migrate`` make an umbrella, and ``git <project>
help worktree`` describes each.

An umbrella is one directory that holds a bare clone and its worktrees side
by side::

  myrepo/
    .git            a file holding "gitdir: .myrepo.git"
    .myrepo.git/    the bare repository
    master/         a worktree on the main branch
    topic/          a worktree on branch topic

The bare repository is named for the last component of the remote's url,
with a leading ``.`` and a ``.git`` suffix added if the url has none. So
``git@host:me/myrepo.git`` and ``https://host/me/myrepo`` both give
``.myrepo.git``. It has ``core.bare`` set to true.

The ``.git`` file lets git run from the umbrella itself, where it sees the
bare repository. ``git log`` and ``git worktree list`` work there, but
``git status`` does not, since the umbrella is not a checkout. The ``.git``
is a file, never a directory or a symlink.

Finding a checkout
------------------

A tool can find its way around an umbrella without git-project:

- A directory ``D`` is an umbrella when ``D/.git`` is a file whose whole
  content is ``gitdir: <name>`` and a newline, and ``D/<name>`` is the bare
  repository.
- Inside a worktree, ``git rev-parse --path-format=absolute
  --git-common-dir`` prints the bare repository's path. Its parent is the
  umbrella if the test above passes.
- In the umbrella, ``git rev-parse --is-bare-repository`` prints ``true``
  and ``git rev-parse --show-toplevel`` fails. Do not treat the umbrella as
  a checkout.
- To find the checkout of a branch, read ``git -C D worktree list
  --porcelain``. Skip the record marked ``bare``, which is the repository,
  and match the line ``branch refs/heads/<branch>``. Do not build the path
  from the branch name. A worktree lives wherever it was added, which can
  be outside the umbrella.
- git-project records each worktree it makes in the repository's config, as
  ``<project>.worktree.<name>.path``. A plain ``git worktree add`` leaves no
  record, so ``git worktree list`` is the complete answer.
