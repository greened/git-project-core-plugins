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

"""A plugin to add a 'clone' command to git-project.  The clone command clones a
repository and optionally initializes a master worktree environment.

Summary:

git-project clone <url> [--bare] [--no-master-worktree]

"""

from git_project import add_top_level_command, Plugin

import getpass
import os
from pathlib import Path
import progressbar
import pygit2

class CloneCallbacks(pygit2.RemoteCallbacks):
    def __init__(self):
        self.progress = progressbar.ProgressBar()

        self.started_transfer = False
        self.transfer_done = False

        self.started_deltas = False
        self.deltas_done = False

        self.null_oid = pygit2.Oid(hex='0000000000000000000000000000000000000000')

    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types & pygit2.credentials.GIT_CREDENTIAL_SSH_KEY:
            return pygit2.Keypair(username_from_url, str(Path.home() / '.ssh' / 'id_rsa.pub'),
                                  str(Path.home() / '.ssh' / 'id_rsa'), '')
        elif allowed_types & pygit2.credentials.GIT_CREDENTIAL_USERNAME:
            return pygit2.Username(username_from_url)
        return None

    def sideband_progress(self, message):
        print(f'Remote: {message}')

    def transfer_progress(self, stats):
        if not self.started_transfer:
            self.started_transfer = True
            print(f'Receiving objects ({stats.total_objects})...')
            self.progress.start(stats.total_objects)

        if not self.transfer_done:
            self.progress.update(stats.received_objects)
            if stats.received_objects >= stats.total_objects:
                self.progress.finish()
                self.transfer_done = True

        if stats.total_deltas > 0 and not self.started_deltas:
            self.started_deltas = True
            print(f'Resolving deltas ({stats.total_deltas})...')
            self.progress.start(stats.total_deltas)

        if self.started_deltas and not self.deltas_done:
            self.progress.update(stats.indexed_deltas)
            if stats.indexed_deltas >= stats.total_deltas:
                self.progress.finish()
                self.deltas_done = True
                print('')

    def update_tips(self, refname, old, new):
        if old != self.null_oid:
            print(f'{refname} {str(old)} -> {str(new)}')
        else:
            print(f'{refname} -> {str(new)}')

def command_clone(git, gitproject, project, clargs):
    """Implement git-project clone"""
    callbacks = CloneCallbacks()
    gitdir = git.clone(clargs.url, bare=clargs.bare, callbacks=callbacks)

    # Now that we have a repository, add sensible project defaults.  We know
    # there is no existing project in the config file since we just cloned.
    # This will have the effect of adding a project section.
    project.set_defaults()

    return gitdir

class ClonePlugin(Plugin):
    """A plugin to implement the clone command."""
    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project clone.'"""
        # clone
        clone_parser = add_top_level_command(parser_manager,
                                             'clone',
                                             'clone',
                                             help='Clone project')

        clone_parser.set_defaults(func=command_clone)

        clone_parser.add_argument('url',
                                  help='URL to clone')

        clone_parser.add_argument('--bare', action='store_true',
                                  help='Clone a bare repositrory')
