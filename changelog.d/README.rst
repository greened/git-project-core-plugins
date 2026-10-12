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

Each file here other than this one is one entry for the next release's
changelog, named ``<slug>.<category>.rst``, where the category is
``added``, ``changed``, ``deprecated``, ``removed``, ``fixed`` or
``security``. An entry is plain RST with no Sphinx roles, and a link
takes the anonymous inline form ```text <URL>`__``. At a release, ``changelog.py``
moves the entries into ``docs/changelog.rst`` and removes their files.
See the Changelog section of ``docs/contributing.rst``.
