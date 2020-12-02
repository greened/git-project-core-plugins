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
from git_project_core_plugins import Install, InstallPlugin
import common

def test_install_add_arguments(reset_directory,
                               git,
                               gitproject,
                               project,
                               parser_manager):
    plugin = InstallPlugin()

    project.add_item('install', 'debug')
    project.add_item('install', 'release')

    plugin.add_arguments(git, gitproject, project, parser_manager)

    install_parser = parser_manager.find_parser(Install.get_managing_command())

    install_args = [
        'debug',
        'release',
    ]

    common.check_args(install_parser, install_args)

    assert install_parser.get_default('func').__name__ == 'command_install'

def test_install_get_no_repo(reset_directory, git, project):
    install = Install.get(git, project, 'test')

    assert not hasattr(install, 'command')
    assert not hasattr(install, 'description')

def test_install_get_with_repo(reset_directory, install_git, project):
    install = Install.get(install_git, project, 'test')

    assert install.command == 'make install'
    assert install.description == 'Install build'

def test_install_get_managing_command():
    assert Install.get_managing_command() == 'install'

def test_install_get_kwargs(reset_directory, install_git, project):
    install = Install.get(install_git,
                          project,
                          'test',
                          command='test command')

    assert install.command == 'test command'
    assert install.description == 'Install build'

def test_install_add_and_run(git_project_runner,
                             git,
                             capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'install',
                           'test',
                           '{path}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/doit master'),
                           '.*',
                           'install',
                           'test')

def test_install_recursive_sub(git_project_runner,
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
                           'install',
                           'test',
                           '{builddir}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/master/doit master'),
                           '.*',
                           'install',
                           'test')
