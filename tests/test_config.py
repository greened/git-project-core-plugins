#!/usr/bin/env python3
#
# Copyright 2020 David A. Greene
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <https://www.gnu.org/licenses/>.
#

from git_project_core_plugins import ConfigPlugin
import common

def test_config_add_arguments(reset_directory,
                              git,
                              gitproject,
                              project,
                              parser_manager):
    plugin = ConfigPlugin()

    plugin.add_arguments(git, gitproject, project, parser_manager)

    config_parser = parser_manager.find_parser('config')

    config_args = [
        'name',
        'value',
        '--add',
        '--unset',
    ]

    common.check_args(config_parser, config_args)

    assert config_parser.get_default('func').__name__ == 'command_config'


def test_config(reset_directory,
                git,
                gitproject,
                project,
                parser_manager):
    plugin = ConfigPlugin()

    plugin.add_arguments(git, gitproject, project, parser_manager)

    config_parser = parser_manager.find_parser('config')

    command_config = config_parser.get_default('func')

    clargs = {
        'name': 'remote',
        'value': 'testval',
        'add': None,
        'unset': None,
        'getter': project.get,
        'exister': project.exists,
        'classname': 'Project'
    }

    command_config(git, gitproject, project, common.AttrDict(clargs))

    assert project.remote == 'testval'

    clargs = {
        'name': 'remote',
        'value': None,
        'add': None,
        'unset': True,
        'getter': project.get,
        'exister': project.exists,
        'classname': 'Project'
    }

    command_config(git, gitproject, project, common.AttrDict(clargs))

    assert not hasattr(project, 'remote')
