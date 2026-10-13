#!/usr/bin/env python3
#
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
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

from git_project import ConfigObject
from git_project.commandline import add_version_argument

# Each of these points git somewhere other than the repository the command was
# meant for.
_GIT_REDIRECT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_NAMESPACE",
)


def add_plugin_version_argument(parser):
    add_version_argument(parser, "git-project-core-plugins")


def add_config_properties(git, cls, project_section, subsection, ident):
    """Give cls a property for each key in the config section of
    subsection.ident. ConfigObject.get adds them too, but it writes every
    value back, which copies a global value into the local config.

    """
    config_section = git.config.get_section(
        ConfigObject._get_full_section(
            ConfigObject._map_project_section(project_section),
            subsection,
            ident,
        )
    )
    for itemname, _item in config_section or []:
        key = itemname.rsplit(".", 1)[-1]
        if not hasattr(cls, key):
            cls._add_property(key)
