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

def make_script(*paths, status=0):
    """Create an executable script at each of paths, exiting with status.  Create
    each script's parent directory as well if it does not exist.

    A test that invokes a run command has to create the script the command runs,
    because run propagates the exit code and a missing script fails the run.

    """
    for path in paths:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as script:
            script.write(f'#!/bin/sh\nexit {status}\n')
        os.chmod(path, 0o755)

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

    make_script(f'{workdir}/doit')

    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/doit {branch}')

    git_project_runner.run(re.escape(f'{workdir}/doit master'),
                           '.*',
                           'run',
                           'test')

def test_run_exit_code(git_project_runner,
                       git,
                       script_runner):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    # 3 is not a status anything else in the pipeline produces, so it cannot be
    # confused with a shell, argparse, crash or git-project error.
    make_script(f'{workdir}/doit', status=3)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/doit {branch}')

    ret = script_runner.run(['git-project', 'run', 'test'], cwd=workdir)

    assert ret.returncode == 3

def test_run_recursive_sub(git_project_runner,
                           git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    make_script(f'{workdir}/master/doit')

    git_project_runner.run('.*',
                           '',
                           'config',
                           'rundir',
                           '{git_workdir}/{branch}')

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

    make_script(f'{workdir}/master/doit',
                f'{workdir}/master/check-doit')

    git_project_runner.run('.*',
                           '',
                           'config',
                           'rundir',
                           '{git_workdir}/{branch}')

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

    make_script(f'{workdir}/buildit')

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
                           '{git_workdir}/buildit {branch}')

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

    make_script(f'{workdir}/buildit',
                f'{workdir}/checkit')

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
                           '{git_workdir}/buildit {branch} {build}')

    # Add a check.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'check',
                           'test',
                           '{git_workdir}/checkit {build}')

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

    make_script(f'{workdir}/buildit')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit {options} {run}')

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

    make_script(f'{workdir}/buildit')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit {options} {run}')

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

    make_script(f'{workdir}/buildit')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit {option_names} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit branch git_workdir test'),
                           '.*',
                           'run',
                           'test',
                           '{branch}',
                           '{git_workdir}')

def test_run_substitute_empty_option_names(git_project_runner,
                                           git,
                                           capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    make_script(f'{workdir}/buildit')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit {option_names} {run}')

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

    make_script(f'{workdir}/buildit-branch-git_workdir')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit{option_keysep}{option_key} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit-branch-git_workdir test'),
                           '.*',
                           'run',
                           'test',
                           '{branch}',
                           '{git_workdir}')

def test_run_substitute_empty_option_name_key(git_project_runner,
                                              git,
                                              capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    make_script(f'{workdir}/buildit')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit{option_keysep}{option_key} {run}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit test'),
                           '.*',
                           'run',
                           'test')

def test_run_substitute_option_positions(git_project_runner,
                                         git,
                                         capsys):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    make_script(f'{workdir}/buildit')

    # Add a run.
    git_project_runner.run('.*',
                           '',
                           'add',
                           'run',
                           'test',
                           '{git_workdir}/buildit {options_1} {run} {options_0}')

    # Check run invocation.
    git_project_runner.run(re.escape(f'{workdir}/buildit foo test master'),
                           '.*',
                           'run',
                           'test',
                           '{branch}',
                           'foo')
