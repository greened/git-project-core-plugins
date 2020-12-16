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

import os
import re

import git_project
from git_project.test_support import check_config_file
from git_project_core_plugins import Run, RunPlugin
import common

plugin_name = 'run'
plugin_class = Run
plugins = [('run', RunPlugin)]

def test_run_add_arguments(reset_directory,
                           git,
                           gitproject,
                           project,
                           parser_manager):
    plugin = RunPlugin()

    project.add_item('run', 'debug')
    project.add_item('run', 'release')

    plugin.add_arguments(git, gitproject, project, parser_manager)

    run_parser = parser_manager.find_parser(Run.get_managing_command())

    run_args = [
        'debug',
        'release',
    ]

    common.check_args(run_parser, run_args)

    assert run_parser.get_default('func').__name__ == 'command_run'

def test_run_get_no_repo(reset_directory, git, project):
    run = Run.get(git, project, 'test')

    assert not hasattr(run, 'command')
    assert not hasattr(run, 'description')

def test_run_get_with_repo(reset_directory, run_git, project):
    run = Run.get(run_git, project, 'test')

    assert run.command == 'make test'
    assert run.description == 'Run tests'

def test_run_get_managing_command():
    assert Run.get_managing_command() == 'run'

def test_run_get_kwargs(reset_directory, run_git, project):
    run = Run.get(run_git,
                      project,
                      'test',
                      command='test command')

    assert run.command == 'test command'
    assert run.description == 'Run tests'

def test_run_add_and_run(git_project_runner,
                           git,
                           capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/doit master'),
                           '.*',
                           'run',
                           'test')

def test_run_recursive_sub(git_project_runner,
                             git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'config',
                           'rundir',
                           '{path}/{branch}')

    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{rundir}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/master/doit master'),
                           '.*',
                           'run',
                           'test')

def test_run_no_dup(reset_directory, git_project_runner, git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'config',
                           'rundir',
                           '{path}/{branch}')

    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'devrel',
                           '{rundir}/doit {branch}')

    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'check-devrel',
                           '{rundir}/check-doit {branch}')

    os.chdir(git._repo.path)

    check_config_file('project',
                      'run',
                      {'devrel', 'check-devrel'})

    git_project_runner.run(re.escape(f'{workdir}/master/doit master'),
                           '.*',
                           'run',
                           'devrel')

    check_config_file('project',
                      'run',
                      {'devrel', 'check-devrel'})

    git_project_runner.run(re.escape(f'{workdir}/master/check-doit master'),
                           '.*',
                           'run',
                           'check-devrel')

    check_config_file('project',
                      'run',
                      {'devrel', 'check-devrel'})
