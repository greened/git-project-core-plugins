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
import re

import git_project
from git_project.test_support import check_config_file
from git_project_core_plugins import RunPlugin
import common

def test_run_add_arguments(reset_directory,
                           project,
                           git_project_runner):
    project.add_item('run', 'release')
    project.add_item('run', 'debug')

    git_project_runner.run(r'(\s*debug\s*release|\s*release\s*debug)',
                           '',
                           'run',
                           '--help')

def test_run_get_no_repo(reset_directory, git, project):
    plugin = RunPlugin()
    Run = plugin.get_class_for('run')
    run = Run.get(git, project, 'test')

    assert not hasattr(run, 'command')
    assert not hasattr(run, 'description')

def test_run_get_with_repo(reset_directory, run_git, project):
    plugin = RunPlugin()
    Run = plugin.get_class_for('run')
    run = Run.get(run_git, project, 'test')

    assert run.command == 'make test'
    assert run.description == 'Run tests'

def test_run_get_managing_command():
    plugin = RunPlugin()
    Run = plugin.get_class_for('run')
    assert Run.get_managing_command() == 'run'

def test_run_get_kwargs(reset_directory, run_git, project):
    plugin = RunPlugin()
    Run = plugin.get_class_for('run')
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

def test_run_add_alias(git_project_runner,
                       git,
                       capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add aliases.
    git_project_runner.run('.*',
                           '',
                           'run',
                           '--make-alias',
                           'build')

    git_project_runner.run('.*',
                           '',
                           'run',
                           '--make-alias',
                           'check')

    check_config_file('project.run',
                      'alias',
                      {'build', 'check'})

    # Add a build.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'build',
                           'test',
                           '{path}/buildit {branch}')

    # Check build invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit master'),
                           '.*',
                           'build',
                           'test')

def test_run_substitute_alias(git_project_runner,
                              git,
                              capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add aliases.
    git_project_runner.run('.*',
                           '',
                           'run',
                           '--make-alias',
                           'build')

    git_project_runner.run('.*',
                           '',
                           'run',
                           '--make-alias',
                           'check')

    check_config_file('project.run',
                      'alias',
                      {'build', 'check'})

    # Add a build.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'build',
                           'test',
                           '{path}/buildit {branch} {build}')

    # Add a check.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'check',
                           'test',
                           '{path}/checkit {build}')

    # Check build invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit master test'),
                           '.*',
                           'build',
                           'test')

    # Check check invocation.
    git_project_runner.run(re.escape(f'{workdir}/checkit test'),
                           '.*',
                           'check',
                           'test')

def test_run_substitute_options(git_project_runner,
                                git,
                                capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/buildit {options} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit master test'),
                           '.*',
                           'run',
                           'test',
                           '{branch}')

def test_run_substitute_empty_options(git_project_runner,
                                git,
                                capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/buildit {options} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit  test'),
                           '.*',
                           'run',
                           'test')

def test_run_substitute_option_names(git_project_runner,
                                     git,
                                     capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/buildit {option_names} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit branch path test'),
                           '.*',
                           'run',
                           'test',
                           '{branch}',
                           '{path}')

def test_run_substitute_empty_option_names(git_project_runner,
                                           git,
                                           capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/buildit {option_names} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit  test'),
                           '.*',
                           'run',
                           'test')

def test_run_substitute_option_name_key(git_project_runner,
                                        git,
                                        capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/buildit{option_keysep}{option_key} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit-branch-path test'),
                           '.*',
                           'run',
                           'test',
                           '{branch}',
                           '{path}')

def test_run_substitute_empty_option_name_key(git_project_runner,
                                              git,
                                              capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{path}/buildit{option_keysep}{option_key} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit test'),
                           '.*',
                           'run',
                           'test')
