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

from git_project_core_plugins import HelpPlugin
from git_project.test_support import check_config_file
import common

import shlex

def test_help_print_manpage(git_project_runner,
                            git):

    expected = """This is a manpage for foo.

It has multiple lines.
"""
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'config',
                           'help.foo.manpage',
                           shlex.quote(expected))

    git_project_runner.run(expected, '', 'help', 'foo')

def test_help_and_help(git_project_runner,
                       git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'help',
                           'foo',
                           'Test help')

    check_config_file('project.help.foo',
                      'short',
                      {'Test help'})

    git_project_runner.run('.*',
                           '',
                           'add',
                           'help',
                           '--manpage',
                           'foo',
                           'Manpage help')

    check_config_file('project.help.foo',
                      'manpage',
                      {'Manpage help'})

def test_help_rm_help(git_project_runner,
                       git):
    workdir = git.get_working_copy_root()

    git_project_runner.chdir(workdir)

    git_project_runner.run('.*',
                           '',
                           'add',
                           'help',
                           'foo',
                           'Test help')

    check_config_file('project.help.foo',
                      'short',
                      {'Test help'})

    git_project_runner.run('.*',
                           '',
                           'add',
                           'help',
                           '--manpage',
                           'foo',
                           'Manpage help')

    check_config_file('project.help.foo',
                      'manpage',
                      {'Manpage help'})

    git_project_runner.run('.*',
                           '',
                           'rm',
                           'help',
                           'foo')

    check_config_file('project.help.foo',
                      'short',
                      {'Test help'},
                      key_present=False)

    check_config_file('project.help.foo',
                      'manpage',
                      {'Manpage help'})

    git_project_runner.run('.*',
                           '',
                           'rm',
                           'help',
                           '--manpage',
                           'foo')

    check_config_file('project.help.foo',
                      'manpage',
                      {},
                      section_present=False,
                      key_present=False)
