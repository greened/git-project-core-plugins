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

import git_project
from git_project_core_plugins import Worktree, WorktreePlugin
import common

def test_worktree_add_arguments(reset_directory,
                                git,
                                gitproject,
                                project,
                                parser_manager):
    plugin = WorktreePlugin()

    plugin.add_arguments(git, gitproject, project, parser_manager)

    worktree_add_parser = parser_manager.find_parser('worktree-add')

    worktree_add_args = [
        'name_or_path',
        'committish',
        '-b',
    ]

    common.check_args(worktree_add_parser, worktree_add_args)

    assert worktree_add_parser.get_default('func').__name__ == 'command_worktree_add'

    worktree_rm_parser = parser_manager.find_parser('worktree-rm')

    worktree_rm_args = [
        'name_or_path',
        '-f',
    ]

    common.check_args(worktree_rm_parser, worktree_rm_args)

    assert worktree_rm_parser.get_default('func').__name__ == 'command_worktree_rm'

def test_worktree_modify_arguments(reset_directory,
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

def test_worktree_get(reset_directory,
                      git,
                      gitproject,
                      project,
                      parser_manager):
    project.set_item('builddir', '/path/to/build')

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
    project.set_item('builddir', '/path/to/build')

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
