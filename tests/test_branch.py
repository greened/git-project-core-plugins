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

from git_project_core_plugins import BranchPlugin
import common

def test_add_arguments(reset_directory,
                       git,
                       gitproject,
                       project,
                       parser_manager):
    plugin = BranchPlugin()

    plugin.add_arguments(git, gitproject, project, parser_manager)

    branch_status_parser = parser_manager.find_parser('branch-status')

    branch_status_args = [
        'name_or_ref',
        'target',
        '--all',
        '--all-user',
    ]

    common.check_args(branch_status_parser, branch_status_args)

    assert branch_status_parser.get_default('func').__name__ == 'command_branch_status'

    branch_prune_parser = parser_manager.find_parser('branch-prune')

    branch_prune_args = [
        'name_or_ref',
        '--all-user',
        '--force',
        '--no-ask',
    ]

    common.check_args(branch_prune_parser, branch_prune_args)

    assert branch_prune_parser.get_default('func').__name__ == 'command_branch_prune'

def test_branch_status(reset_directory,
                       git,
                       gitproject,
                       project,
                       parser_manager,
                       capsys):
    plugin = BranchPlugin()

    plugin.add_arguments(git, gitproject, project, parser_manager)

    branch_status_parser = parser_manager.find_parser('branch-status')

    command_branch_status = branch_status_parser.get_default('func')

    clargs = {
        'name_or_ref': None,
        'all_user': False,
        'all': True,
        'target': None,
    }

    command_branch_status(git,
                          gitproject,
                          project,
                          common.AttrDict(clargs))

    captured = capsys.readouterr()

    expected = """-----------------------------------------------------------
branch                                       merged  pushed  
-----------------------------------------------------------
refs/heads/master                            yes     no      
refs/heads/merged_local                      yes     no      
refs/heads/merged_remote                     yes     yes     
refs/heads/notpushed                         no      no      
refs/heads/pushed                            no      yes     
refs/heads/unmerged                          no      no      
refs/remotes/origin/HEAD                     yes     yes     
refs/remotes/origin/master                   yes     yes     
refs/remotes/origin/notpushed                yes     yes     
refs/remotes/origin/pushed                   no      no      
-----------------------------------------------------------
"""
    assert captured.out == expected
    assert captured.err == ''

def test_branch_prune(reset_directory,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      capsys):
    plugin = BranchPlugin()

    plugin.add_arguments(git, gitproject, project, parser_manager)

    branch_prune_parser = parser_manager.find_parser('branch-prune')

    command_branch_prune = branch_prune_parser.get_default('func')

    clargs = {
        'name_or_ref': 'merged_remote',
        'all': True,
        'no_ask': True,
        'force': False,
    }

    command_branch_prune(git,
                         gitproject,
                         project,
                         common.AttrDict(clargs))

    captured = capsys.readouterr()

    print(captured)

    expected = """---------------------------------------------------------------------------
branch                                       local status   remote status  
---------------------------------------------------------------------------
refs/heads/merged_remote                     merged         
"""
    assert captured.out == expected
    assert captured.err == ''

    assert not git.committish_exists('merged_remote')
    assert not git.committish_exists('refs/heads/merged_remote')
    assert not git.committish_exists('refs/remotes/origin/merged_remote')
