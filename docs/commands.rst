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

Commands
========

Each command's manual is its plugin's class docstring, which
``git <project> help <command>`` also shows.

.. currentmodule:: git_project_core_plugins

artifact
--------

.. autoclass:: git_project_core_plugins.artifact.ArtifactPlugin

branch
------

.. autoclass:: git_project_core_plugins.branch.BranchPlugin

clone
-----

.. autoclass:: git_project_core_plugins.clone.ClonePlugin

config
------

.. autoclass:: git_project_core_plugins.config.ConfigPlugin

help
----

.. autoclass:: git_project_core_plugins.help.HelpPlugin

init
----

.. autoclass:: git_project_core_plugins.init.InitPlugin

run
---

.. autoclass:: git_project_core_plugins.run.RunPlugin

worktree
--------

.. autoclass:: git_project_core_plugins.worktree.WorktreePlugin

