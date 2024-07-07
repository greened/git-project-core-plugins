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

import git_project
from git_project_core_plugins import Worktree, WorktreePlugin
import common

import io
import os
from pathlib import Path

def test_worktree_add_arguments(reset_directory,
                                git,
                                gitproject,
                                project,
                                parser_manager,
                                plugin_manager):
    plugin = WorktreePlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    worktree_add_parser = parser_manager.find_parser('worktree-add')

    worktree_add_args = [
        'path',
        'committish',
        '-b',
    ]

    common.check_args(worktree_add_parser, worktree_add_args)

    assert worktree_add_parser.get_default('func').__name__ == 'command_worktree_add'

    worktree_rm_parser = parser_manager.find_parser('worktree-rm')

    worktree_rm_args = [
        'name',
        '-f',
    ]

    common.check_args(worktree_rm_parser, worktree_rm_args)

    assert worktree_rm_parser.get_default('func').__name__ == 'command_worktree_rm'

def test_worktree_modify_clone_arguments(reset_directory,
                                         git,
                                         gitproject,
                                         project,
                                         clone_parser_manager,
                                         plugin_manager):
    plugin = WorktreePlugin()

    plugin.modify_arguments(git,
                            gitproject,
                            project,
                            clone_parser_manager,
                            plugin_manager)

    clone_parser = clone_parser_manager.find_parser('clone')

    assert clone_parser.get_default('func').__name__ == 'worktree_command_clone'

def test_worktree_modify_init_arguments(reset_directory,
                                        git,
                                        gitproject,
                                        project,
                                        init_parser_manager,
                                        plugin_manager):
    plugin = WorktreePlugin()

    plugin.modify_arguments(git,
                            gitproject,
                            project,
                            init_parser_manager,
                            plugin_manager)

    init_parser = init_parser_manager.find_parser('init')

    assert init_parser.get_default('func').__name__ == 'worktree_command_init'

def test_worktree_get(reset_directory,
                      git,
                      gitproject,
                      project,
                      parser_manager):
    setattr(project, 'builddir', '/path/to/build')

    worktree = Worktree.get(git,
                            project,
                            'test',
                            path='/path/to/test',
                            committish='master')

    assert worktree._section == 'project.worktree.test'
    assert worktree.path == '/path/to/test'
    assert worktree._pathsection.worktree == 'test'
    assert worktree.committish == 'master'

    assert not hasattr(worktree, 'builddir')
    assert not hasattr(worktree, 'prefix')

def test_worktree_get_by_path(reset_directory,
                              git,
                              gitproject,
                              project,
                              parser_manager):
    worktree = Worktree.get(git,
                            project,
                            'test',
                            builddir='/path/to/test',
                            path='/path/to/test',
                            committish='master')

    assert worktree._section == 'project.worktree.test'
    assert worktree.path == '/path/to/test'
    assert worktree._pathsection.worktree == 'test'
    assert worktree.committish == 'master'
    assert worktree.builddir == '/path/to/test'

    path_worktree = Worktree.get_by_path(git, project, worktree.path)

    assert path_worktree._section == worktree._section
    assert path_worktree._ident == worktree._ident
    assert path_worktree.path == worktree.path
    assert path_worktree.committish == worktree.committish
    assert path_worktree.builddir == worktree.builddir

def test_worktree_scope(reset_directory,
                        git,
                        gitproject,
                        project,
                        parser_manager):
    setattr(project, 'builddir', '/path/to/build')

    worktree = Worktree.get(git,
                            project,
                            'test',
                            builddir='/path/to/test',
                            path='/path/to/test',
                            committish='master')

    assert worktree._section == 'project.worktree.test'
    assert worktree.path == '/path/to/test'
    assert worktree._pathsection.worktree == 'test'
    assert worktree.committish == 'master'
    assert worktree.builddir == '/path/to/test'

    assert not hasattr(worktree, 'prefix')

    assert project._section == 'project'
    assert project.path == '/path/to/test'
    assert project.committish == 'master'
    assert project.builddir == '/path/to/test'

def test_worktree_clone(git_project_runner,
                        remote_repository):
    repo_path = Path('.git')

    git_project_runner.run('.*',
                           '',
                           'clone',
                           '--worktree',
                           remote_repository.path)

    assert os.path.exists(repo_path)
    assert os.path.exists('master')

def test_worktree_clone_bare(git_project_runner,
                             remote_repository):
    git_project_runner.run('.*',
                           '',
                           'clone',
                           '--bare',
                           '--worktree',
                           remote_repository.path)

    repo_path = Path('.git')

    assert os.path.exists(repo_path)
    assert os.path.exists('master')

def test_worktree_clone_path(git_project_runner,
                             remote_repository):
    repo_path = Path.cwd() / 'foo' / 'bar'

    git_project_runner.run('.*',
                           '',
                           'clone',
                           '--worktree',
                           remote_repository.path,
                           str(repo_path))

    assert os.path.exists(str(repo_path / '.git'))
    assert os.path.exists(repo_path / 'master')

def test_worktree_init(git,
                       git_project_runner,
                       tmp_path_factory):
    path = tmp_path_factory.mktemp('clone-workdir')

    os.chdir(path)

    clone_path = git.clone('file://' + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / '.git')
    assert not os.path.exists(workarea / 'MergedRemote.txt')
    assert os.path.exists(workarea / 'master')

def test_worktree_init_nonclean(git,
                                git_project_runner):
    workarea = git.get_working_copy_root()

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    # Remove a file from the index to make it unclean.
    index = git._repo.index
    index.read()

    for entry in index:
        index.remove(entry.path)
        index.write()
        break

    git_project_runner.chdir(workarea)

    git_project_runner.expect_fail = True

    git_project_runner.run('git-project: Cannot initialize worktree layout, working copy not clean',
                           '',
                           'init',
                           '--worktree')

def test_worktree_init_main(git,
                            git_project_runner,
                            tmp_path_factory):
    path = tmp_path_factory.mktemp('clone-workdir')

    os.chdir(path)

    clone_path = git.clone('file://' + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('main', 'master')
    git.checkout('main')
    git.delete_branch('master')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / '.git')
    assert not os.path.exists(workarea / 'MergedRemote.txt')
    assert os.path.exists(workarea / 'main')

def test_worktree_init_main_master(git,
                                   git_project_runner,
                                   tmp_path_factory):
    path = tmp_path_factory.mktemp('clone-workdir')

    os.chdir(path)

    clone_path = git.clone('file://' + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('main', 'master')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / '.git')
    assert not os.path.exists(workarea / 'MergedRemote.txt')
    # Prefer main over master.
    assert not os.path.exists(workarea / 'master')
    assert os.path.exists(workarea / 'main')

def test_worktree_init_nomain(git,
                              git_project_runner,
                              tmp_path_factory):
    path = tmp_path_factory.mktemp('clone-workdir')

    os.chdir(path)

    clone_path = git.clone('file://' + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('newmain', 'master')
    git.checkout('newmain')
    git.delete_branch('master')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / '.git')
    assert not os.path.exists(workarea / 'MergedRemote.txt')
    assert not os.path.exists(workarea / 'master')
    assert os.path.exists(workarea / 'newmain')

def test_worktree_init_nomain_multi(git,
                                    git_project_runner,
                                    tmp_path_factory):
    path = tmp_path_factory.mktemp('clone-workdir')

    os.chdir(path)

    clone_path = git.clone('file://' + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('newmain', 'master')
    git.checkout('newmain')
    git.delete_branch('master')
    git.create_branch('other', 'newmain')
    git.create_branch('another', 'newmain')
    git.create_branch('yetanother', 'newmain')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree',
                           stdin=io.StringIO('newmain'))

    assert os.path.exists(workarea / '.git')
    assert not os.path.exists(workarea / 'MergedRemote.txt')
    assert not os.path.exists(workarea / 'master')
    assert os.path.exists(workarea / 'newmain')
    assert not os.path.exists(workarea / 'other')
    assert not os.path.exists(workarea / 'another')
    assert not os.path.exists(workarea / 'yetanother')

def test_worktree_add(git,
                      git_project_runner,
                      tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../test',
                           'master')

    assert os.path.exists(workarea.parent / 'test')
    assert git.branch_name_to_refname('test') == 'refs/heads/test'

def test_worktree_add_subdir(git,
                             git_project_runner,
                             tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test',
                           'master')

    assert os.path.exists(workarea.parent / 'user' / 'test')
    os.chdir(workarea.parent / 'user' / 'test')
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == 'user/test'
