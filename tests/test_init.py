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
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

import os
from pathlib import Path

from git_project_core_plugins import InitPlugin
import common

def test_add_arguments(reset_directory,
                       git,
                       gitproject,
                       project,
                       parser_manager,
                       plugin_manager):
    plugin = InitPlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    init_parser = parser_manager.find_parser('init')

    assert init_parser.get_default('func').__name__ == 'command_init'
