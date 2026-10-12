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

Working on git-project-core-plugins
===================================

This guide covers the changelog and releases. For the rest, such as the
test environment and lint, see
:projecturl:`the guide in git-project
<git-project/blob/master/docs/contributing.rst>`, which applies here too.

Changelog
---------

A branch with a change a user can see adds a fragment to ``changelog.d``,
named ``<slug>.<category>.rst``. The slug is lower case letters, digits
and hyphens. The branch name makes a good one, lower-cased with ``/`` and
``_`` turned into ``-``. A second fragment takes a suffix such as
``-2``. The category is ``added``, ``changed``, ``deprecated``,
``removed``, ``fixed`` or ``security``. A branch never edits
``docs/changelog.rst``.

Each fragment is one entry in plain RST, with no Sphinx roles.
``changelog.py`` refuses them because git-project, which shares it, puts
its newest changelog section on PyPI. Put code, options and file names in
double backticks and write a link inline, as ```text <URL>`__``. Describe
what changed for someone using the last release, not what changed in the
tree. Line breaks are kept, and an entry may have several paragraphs. A
defect that no release ever had needs no fragment.

Releasing
---------

A release is a tag on the main branch, named ``vX.Y.Z``. Tags are
lightweight. hatch-vcs takes the version from the tag, so there is no
version number to edit.

#. Run ``./changelog.py --version X.Y.Z``. It moves the fragments into a
   new section of the changelog, dated today, and stages their removal.
   With ``--stdout`` it prints the section and changes nothing.
#. Edit and review the result. Commit the changelog with the removed
   fragments and push that commit to the main branch.
#. Tag that commit.
#. Build from a clean checkout of the tagged commit, such as a new
   worktree, with ``hatch build``. An untracked file in the checkout ends up
   in the sdist.
#. Check that the built files say ``X.Y.Z``, with no ``.dev`` or ``+g``
   suffix. A suffix means the build did not see the tag.
#. Run ``twine check`` on the built files, then upload them with ``twine
   upload``. A version number can never be uploaded twice.
#. Push the tag last, so a failed upload leaves no published tag behind.

``changelog.py`` refuses, and changes nothing, when a fragment or the
changelog would give a wrong section. Its docstring lists every case.

core-plugins declares its floor on git-project in its ``requirements.txt``.
When core-plugins needs something new in git-project, release git-project
first, raise that floor, and then release core-plugins.
