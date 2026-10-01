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
from git_project import ConfigObject
from git_project.test_support import check_config_file
from git_project_core_plugins import Artifact, ArtifactPlugin
import common

import os
from pathlib import Path

class MyConfigObject(ConfigObject):
    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         **kwargs)

    @classmethod
    def get(cls, git, project_section, ident, **kwargs):
        return super().get(git,
                           project_section,
                           'myconfigobject',
                           ident,
                           **kwargs)

def test_artifact_add_arguments(reset_directory,
                                git,
                                gitproject,
                                project,
                                parser_manager,
                                plugin_manager):
    plugin = ArtifactPlugin()

    plugin.add_arguments(git,
                         gitproject,
                         project,
                         parser_manager,
                         plugin_manager)

    artifact_add_parser = parser_manager.find_parser('artifact-add')

    artifact_add_args = [
        'subsection',
        'path',
    ]

    common.check_args(artifact_add_parser, artifact_add_args)

    assert artifact_add_parser.get_default('func').__name__ == 'command_artifact_add'

    artifact_rm_parser = parser_manager.find_parser('artifact-rm')

    artifact_rm_args = [
        'subsection',
        'path',
    ]

    common.check_args(artifact_rm_parser, artifact_rm_args)

    assert artifact_rm_parser.get_default('func').__name__ == 'command_artifact_rm'

def test_artifact_get(reset_directory,
                      git,
                      gitproject,
                      project):
    setattr(project, 'builddir', '/path/to/build')

    artifact = Artifact.get(git,
                            project.get_section(),
                            'worktree',
                            itempath='{builddir}')

    assert artifact._section == 'project.artifact.worktree'
    assert artifact.itempath == '{builddir}'

def test_artifact_add(git_project_runner,
                      git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'worktree',
                           '{builddir}')

    check_config_file('project.artifact.worktree',
                      'itempath',
                      {'{builddir}'})

def test_artifact_rm_item(git_project_runner,
                          git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'worktree',
                           '{builddir}')

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'worktree',
                           '{installdir}')

    check_config_file('project.artifact.worktree',
                      'itempath',
                      {'{builddir}', '{installdir}'})

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'rm',
                           'worktree',
                           '\\\\{builddir\\\\}')

    check_config_file('project.artifact.worktree',
                      'itempath',
                      {'{installdir}'})

def test_artifact_rm_items(git_project_runner,
                           git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'worktree',
                           '{builddir}')


    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'worktree',
                           '{installdir}')

    check_config_file('project.artifact.worktree',
                      'itempath',
                      {'{builddir}', '{installdir}'})

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'rm',
                           'worktree')

    check_config_file('project.artifact.worktree',
                      'itempath',
                      {'{builddir}, ''{installdir}'},
                      section_present = False)

def test_artifact_rm_config(git_project_runner,
                            git,
                            project):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    tempdir = Path(workdir) / 'temp'

    tempdir.mkdir()

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'myconfigobject',
                           f'{tempdir}')

    git.reload_config()

    obj = MyConfigObject.get(git, project.get_section(), 'test')
    obj.rm()

    assert not tempdir.exists()

def test_artifact_rm_substitution(git_project_runner,
                                  git,
                                  project):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    tempdir = Path(workdir) / 'temp'

    tempdir.mkdir()

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'myconfigobject',
                           '{git_workdir}/temp')

    git.reload_config()

    obj = MyConfigObject.get(git, project.get_section(), 'test')
    obj.rm()

    assert not tempdir.exists()

def test_artifact_rm_path_with_space(git_project_runner,
                                     git,
                                     project):
    workdir = Path(git.get_working_copy_root())

    git_project_runner.chdir(workdir)

    target = workdir / 'has space'
    target.mkdir()
    (target / 'file').write_text('x')

    # A shell would split the path into these two and remove them.
    (workdir / 'has').mkdir()
    (workdir / 'space').mkdir()

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'myconfigobject',
                           f'{target}')

    git.reload_config()

    obj = MyConfigObject.get(git, project.get_section(), 'test')
    obj.rm()

    assert not target.exists()
    assert (workdir / 'has').exists()
    assert (workdir / 'space').exists()

def test_artifact_rm_glob(git_project_runner,
                          git,
                          project,
                          monkeypatch):
    workdir = Path(git.get_working_copy_root())

    git_project_runner.chdir(workdir)
    # rm runs in this process, so the relative pattern resolves here.
    monkeypatch.chdir(workdir)

    out = workdir / 'out'
    out.mkdir()
    (out / 'a.o').write_text('x')
    (out / 'b.o').write_text('x')
    (out / 'keep.c').write_text('x')

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'add',
                           'myconfigobject',
                           # Relative, because pytest's directory names hold
                           # '[' and ']', which are glob characters too.
                           'out/*.o')

    git.reload_config()

    obj = MyConfigObject.get(git, project.get_section(), 'test')
    obj.rm()

    assert not (out / 'a.o').exists()
    assert not (out / 'b.o').exists()
    assert (out / 'keep.c').exists()

def test_artifact_remove_empty_path_removes_nothing(tmp_path, monkeypatch):
    from git_project_core_plugins.artifact import remove_artifact_path

    (tmp_path / 'keep').write_text('x')
    monkeypatch.chdir(tmp_path)

    remove_artifact_path('')

    assert (tmp_path / 'keep').exists()

def test_artifact_remove_expands_home_and_vars(tmp_path, monkeypatch):
    from git_project_core_plugins.artifact import remove_artifact_path

    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('ARTIFACT_TEST_DIR', 'viavar')
    (tmp_path / 'viahome').mkdir()
    (tmp_path / 'viavar').mkdir()

    remove_artifact_path('~/viahome')
    remove_artifact_path(f'{tmp_path}/$ARTIFACT_TEST_DIR')

    assert not (tmp_path / 'viahome').exists()
    assert not (tmp_path / 'viavar').exists()

def test_artifact_remove_unset_var_stays_literal(tmp_path, monkeypatch):
    from git_project_core_plugins.artifact import remove_artifact_path

    # The shell made an unset variable empty, so $UNSET/keep meant /keep.
    monkeypatch.delenv('ARTIFACT_TEST_UNSET', raising=False)
    (tmp_path / 'keep').mkdir()
    monkeypatch.chdir(tmp_path)

    remove_artifact_path('$ARTIFACT_TEST_UNSET/keep')

    assert (tmp_path / 'keep').exists()

def test_artifact_remove_symlinks_removes_only_the_link(tmp_path, monkeypatch):
    from git_project_core_plugins.artifact import remove_artifact_path

    monkeypatch.chdir(tmp_path)

    # A link that points at itself. resolve() raises on it.
    os.symlink('loop', tmp_path / 'loop')

    target = tmp_path / 'target'
    target.mkdir()
    (target / 'file').write_text('x')
    os.symlink(target, tmp_path / 'link')

    remove_artifact_path(str(tmp_path / 'loop'))
    remove_artifact_path(str(tmp_path / 'link'))

    assert not os.path.lexists(tmp_path / 'loop')
    assert not os.path.lexists(tmp_path / 'link')
    assert (target / 'file').exists()
