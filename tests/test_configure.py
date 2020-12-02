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

import re

import git_project
from git_project_core_plugins import Configure, ConfigurePlugin
import common

def test_configure_add_arguments(reset_directory,
                                 git,
                                 gitproject,
                                 project,
                                 parser_manager):
    plugin = ConfigurePlugin()

    project.add_item('configure', 'debug')
    project.add_item('configure', 'release')

    plugin.add_arguments(git, gitproject, project, parser_manager)

    configure_parser = parser_manager.find_parser(Configure.get_managing_command())

    configure_args = [
        'debug',
        'release',
    ]

    common.check_args(configure_parser, configure_args)

    assert configure_parser.get_default('func').__name__ == 'command_configure'

def test_configure_modify_arguments(reset_directory,
                                    git,
                                    gitproject,
                                    project,
                                    worktree_parser_manager,
                                    plugin_manager):
    plugin = ConfigurePlugin()

    plugin.modify_arguments(git,
                            gitproject,
                            project,
                            worktree_parser_manager,
                            plugin_manager)

    worktree_add_parser = worktree_parser_manager.find_parser('worktree-add')

    worktree_add_args = [
        '--buildwidth',
        '--prefix',
        '--sharedir',
    ]

    common.check_args(worktree_add_parser, worktree_add_args)

    assert worktree_add_parser.get_default('func').__name__ == 'configure_command_worktree_add'

def test_configure_get_no_repo(reset_directory, git, project):
    configure = Configure.get(git, project, 'debug')

    assert not hasattr(configure, 'command')
    assert not hasattr(configure, 'description')

def test_configure_get_with_repo(reset_directory, configure_git, project):
    configure = Configure.get(configure_git, project, 'debug')

    assert configure.command == 'cmake debug'
    assert configure.description == 'Configure debug build'

def test_configure_get_managing_command():
    assert Configure.get_managing_command() == 'configure'

def test_configure_get_kwargs(reset_directory, configure_git, project):
    configure = Configure.get(configure_git,
                              project,
                              'debug',
                              command='test command')

    assert configure.command == 'test command'
    assert configure.description == 'Configure debug build'

def test_configure_add_and_run(git_project_runner,
                               git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'configure',
                           'test',
                           '{path}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/doit master'),
                           '.*',
                           'configure',
                           'test')

def test_configure_recursive_sub(git_project_runner,
                                 git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'config',
                           'builddir',
                           '{path}/{branch}')

    git_project_runner.run('.*',
                           '',
                           'add',
                           'configure',
                           'test',
                           '{builddir}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/master/doit master'),
                           '.*',
                           'configure',
                           'test')
