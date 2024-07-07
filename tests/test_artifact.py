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
                            path='{builddir}')

    assert artifact._section == 'project.artifact.worktree'
    assert artifact.path == '{builddir}'

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
                      'path',
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
                      'path',
                      {'{builddir}', '{installdir}'})

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'rm',
                           'worktree',
                           '\\\\{builddir\\\\}')

    check_config_file('project.artifact.worktree',
                      'path',
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
                      'path',
                      {'{builddir}', '{installdir}'})

    git_project_runner.run('.*',
                           '',
                           'artifact',
                           'rm',
                           'worktree')

    check_config_file('project.artifact.worktree',
                      'path',
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
                           '{path}/temp')

    git.reload_config()

    obj = MyConfigObject.get(git, project.get_section(), 'test')
    obj.rm()

    assert not tempdir.exists()
