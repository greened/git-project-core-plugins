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
        '--keep-branch',
        '--keep-remote-branch',
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
    repo_path = Path(f'.{Path(remote_repository.path).name}.git')

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

    repo_path = Path(f'.{Path(remote_repository.path).name}.git')

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

    assert os.path.exists(
        str(repo_path / f'.{Path(remote_repository.path).name}.git')
    )
    assert os.path.exists(repo_path / 'master')

def test_worktree_init(git,
                       git_project_runner,
                       tmp_path_factory):
    path = tmp_path_factory.mktemp('clone-workdir')

    os.chdir(path)

    clone_path = git.clone('file://' + git.get_gitdir())

    os.chdir(clone_path)
    git = git_project.Git()

    clone_url = git.get_remote_url('origin')
    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / f'.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / f'.{Path(clone_url).parent.name}.git')
    assert not os.path.exists(workarea / '.git')
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

    os.chdir(workarea)
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

    clone_url = git.get_remote_url('origin')
    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('main', 'master')
    git.checkout('main')
    git.delete_branch('master')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / f'.{Path(clone_url).parent.name}.git')
    assert not os.path.exists(workarea / '.git')
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

    clone_url = git.get_remote_url('origin')
    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('main', 'master')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / f'.{Path(clone_url).parent.name}.git')
    assert not os.path.exists(workarea / '.git')
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

    clone_url = git.get_remote_url('origin')
    workarea = git.get_working_copy_root()

    print(f'Workarea: {workarea}')

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git.create_branch('newmain', 'master')
    git.checkout('newmain')
    git.delete_branch('master')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree')

    assert os.path.exists(workarea / f'.{Path(clone_url).parent.name}.git')
    assert not os.path.exists(workarea / '.git')
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

    clone_url = git.get_remote_url('origin')
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

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'init',
                           '--worktree',
                           stdin=io.StringIO('newmain'))

    assert os.path.exists(workarea / f'.{Path(clone_url).parent.name}.git')
    assert not os.path.exists(workarea / '.git')
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
                           '../user/test2',
                           'master')

    assert os.path.exists(workarea.parent / 'user' / 'test2')
    os.chdir(workarea.parent / 'user' / 'test2')
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == 'user/test2'


def test_worktree_rm(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test_rm',
                           'master')

    assert os.path.exists(workarea.parent / 'user' / 'test_rm')
    os.chdir(workarea.parent / 'user' / 'test_rm')
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == 'user/test_rm'

    assert os.path.exists(workarea.parent / 'user' / 'test_rm')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'rm',
                           'test_rm')

    assert not os.path.exists(workarea.parent / 'user' / 'test_rm')

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert not git.committish_exists('user/test_rm')


def test_worktree_rm_keep_branch(git,
                                 git_project_runner,
                                 tmp_path_factory,
                                 monkeypatch):
    # This test pushes, so it reaches a pre-push hook.  Ignore the user's git
    # configuration to keep it hermetic.
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')

    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test_keep_branch',
                           'master')

    assert os.path.exists(workarea.parent / 'user' / 'test_keep_branch')
    assert git.committish_exists('user/test_keep_branch')

    # --keep-branch keeps the branch on remotes too, so push it first or that
    # half of the promise holds no matter what rm does.  Name the destination
    # ref explicitly: the fixture remote is a mirror and also carries
    # refs/remotes/origin/*, so a bare branch name lands there instead of in
    # refs/heads, which is the only place remote_branch_exists looks.
    git_project.capture_command('git push origin '
                                'user/test_keep_branch:refs/heads/user/test_keep_branch')

    assert git.remote_branch_exists('user/test_keep_branch', 'origin')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'rm',
                           '--keep-branch',
                           'test_keep_branch')

    assert not os.path.exists(workarea.parent / 'user' / 'test_keep_branch')

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert git.committish_exists('user/test_keep_branch')
    assert git.remote_branch_exists('user/test_keep_branch', 'origin')

def test_worktree_rm_keep_branch_supersedes_keep_remote_branch(
        git,
        git_project_runner,
        tmp_path_factory,
        monkeypatch):
    # keep_branch short-circuits the prune entirely, so keep_remote_branch
    # never gets consulted and both copies survive.  Passing both flags must
    # therefore behave exactly like --keep-branch alone, not like
    # --keep-remote-branch.
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')

    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test_keep_both',
                           'master')

    git_project.capture_command('git push origin '
                                'user/test_keep_both:refs/heads/user/test_keep_both')

    assert git.remote_branch_exists('user/test_keep_both', 'origin')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'rm',
                           '--keep-branch',
                           '--keep-remote-branch',
                           'test_keep_both')

    assert not os.path.exists(workarea.parent / 'user' / 'test_keep_both')

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert git.committish_exists('user/test_keep_both')
    assert git.remote_branch_exists('user/test_keep_both', 'origin')

def test_worktree_rm_unmerged_requires_force(git,
                                             git_project_runner,
                                             tmp_path_factory):
    # Branch the worktree off the fixture's unmerged branch so the merge check
    # actually fires.  Every other rm test branches off master, which is
    # merged by construction.
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test_rm_unmerged',
                           'unmerged')

    assert os.path.exists(workarea.parent / 'user' / 'test_rm_unmerged')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.expect_fail = True

    # A plain rm prunes the branch, so losing it would lose the commits.
    git_project_runner.run('Worktree branch .*test_rm_unmerged is not merged, use -f to force',
                           '',
                           'worktree',
                           'rm',
                           'test_rm_unmerged')

    # --keep-remote-branch keeps only the remote copy, and this branch was
    # never pushed, so the local branch is still the only copy.
    git_project_runner.run('Worktree branch .*test_rm_unmerged is not merged, use -f to force',
                           '',
                           'worktree',
                           'rm',
                           '--keep-remote-branch',
                           'test_rm_unmerged')

    # The check runs before anything is destroyed.
    assert os.path.exists(workarea.parent / 'user' / 'test_rm_unmerged')

    git = git_project.Git()

    assert git.committish_exists('user/test_rm_unmerged')

def test_worktree_rm_keep_branch_unmerged(git,
                                          git_project_runner,
                                          tmp_path_factory):
    # --keep-branch keeps the branch, so an unmerged branch costs nothing and
    # rm does not demand -f.
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test_keep_unmerged',
                           'unmerged')

    assert os.path.exists(workarea.parent / 'user' / 'test_keep_unmerged')

    # Guard against a false pass.  If this branch were merged, the check under
    # test would be skipped for the wrong reason and rm would succeed anyway.
    assert not git.refname_is_merged('user/test_keep_unmerged', 'master')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'rm',
                           '--keep-branch',
                           'test_keep_unmerged')

    assert not os.path.exists(workarea.parent / 'user' / 'test_keep_unmerged')

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert git.committish_exists('user/test_keep_unmerged')

def test_worktree_rm_keep_remote_branch(git,
                                        git_project_runner,
                                        tmp_path_factory,
                                        monkeypatch):
    # This is the only test that pushes, so it is the only one that reaches a
    # pre-push hook.  Ignore the user's git configuration to keep it hermetic.
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')

    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    git = git_project.Git()  # Reinitialize in new workarea.

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           '../user/test_keep_remote',
                           'master')

    # prune_branch only deletes from a remote the branch is actually on, so
    # push it first or the assertion below holds no matter what rm does.  Name
    # the destination ref explicitly: the fixture remote is a mirror and also
    # carries refs/remotes/origin/*, so a bare branch name lands there instead
    # of in refs/heads, which is the only place remote_branch_exists looks.
    git_project.capture_command('git push origin '
                                'user/test_keep_remote:refs/heads/user/test_keep_remote')

    assert git.remote_branch_exists('user/test_keep_remote', 'origin')

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'rm',
                           '--keep-remote-branch',
                           'test_keep_remote')

    assert not os.path.exists(workarea.parent / 'user' / 'test_keep_remote')

    git = git_project.Git()  # Reinitialize after the worktree went away.

    assert not git.committish_exists('user/test_keep_remote')
    assert git.remote_branch_exists('user/test_keep_remote', 'origin')

def test_worktree_add_in_workarea(git,
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
                           'test_workarea',
                           'master')

    assert os.path.exists(workarea / 'test_workarea')
    os.chdir(workarea / 'test_workarea')
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == 'test_workarea'


def test_worktree_rm_in_workarea(git, git_project_runner, tmp_path_factory):
    workarea = git.get_working_copy_root()

    os.chdir(workarea)

    assert os.path.exists(workarea / '.git')
    assert os.path.exists(workarea / 'MergedRemote.txt')

    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'add',
                           'test_rm_workarea',
                           'master')

    assert os.path.exists(workarea / 'test_rm_workarea')
    os.chdir(workarea / 'test_rm_workarea')
    git = git_project.Git()  # Reinitialize in new workarea.
    assert git.get_current_branch() == 'test_rm_workarea'

    os.chdir(workarea)
    git_project_runner.chdir(workarea)

    git_project_runner.run('.*',
                           '',
                           'worktree',
                           'rm',
                           'test_rm_workarea')

    assert not os.path.exists(workarea / 'test_rm_workarea')
