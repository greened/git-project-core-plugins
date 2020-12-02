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
from git_project_core_plugins import Build, BuildPlugin
import common

plugin_name = 'build'
plugin_class = Build
plugins = [('build', BuildPlugin)]

def test_build_add_arguments(reset_directory,
                             git,
                             gitproject,
                             project,
                             parser_manager):
    plugin = BuildPlugin()

    project.add_item('build', 'debug')
    project.add_item('build', 'release')

    plugin.add_arguments(git, gitproject, project, parser_manager)

    build_parser = parser_manager.find_parser(Build.get_managing_command())

    build_args = [
        'debug',
        'release',
    ]

    common.check_args(build_parser, build_args)

    assert build_parser.get_default('func').__name__ == 'command_build'

def test_build_get_no_repo(reset_directory, git, project):
    build = Build.get(git, project, 'test')

    assert not hasattr(build, 'command')
    assert not hasattr(build, 'description')

def test_build_get_with_repo(reset_directory, build_git, project):
    build = Build.get(build_git, project, 'test')

    assert build.command == 'make test'
    assert build.description == 'Run tests'

def test_build_get_managing_command():
    assert Build.get_managing_command() == 'build'

def test_build_get_kwargs(reset_directory, build_git, project):
    build = Build.get(build_git,
                      project,
                      'test',
                      command='test command')

    assert build.command == 'test command'
    assert build.description == 'Run tests'

def test_build_add_and_run(git_project_runner,
                           git,
                           capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'build',
                           'test',
                           '{path}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/doit master'),
                           '.*',
                           'build',
                           'test')

def test_build_recursive_sub(git_project_runner,
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
                           'build',
                           'test',
                           '{builddir}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/master/doit master'),
                           '.*',
                           'build',
                           'test')
