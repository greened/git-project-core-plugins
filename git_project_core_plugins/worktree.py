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

"""A plugin to add a 'worktree' command to git-project.  The worktree command
manages worktrees and connects them to projects.

Summary:

git-project worktree add <name-or-path> [<committish>]
git-project worktree rm <name-or-path>

"""

from git_project import ConfigObject, Git, Plugin, Project
from git_project import ScopedConfigObject
from git_project import add_top_level_command, GitProjectException

from git_project_core_plugins.common import add_plugin_version_argument

import argparse
import os
from pathlib import Path
import shutil
import urllib

# Take a path and normalize it to the current working directory.  If the current
# directory is a bare repository, place this path inside it.  If not, place this
# path outside it.
def normalize_path(git, path):
    """Find an appropriate repository-relative path.  Given a path, if it is not an
    absolute path, place it in the current directory if the repository is a bare
    repository or place it one level above the repository root directory if it
    is not a bare repository.

    path: A string path

    """
    path = Path(path).expanduser()

    if not path.is_absolute() and path.parts[0] != '..':
        # If this is a bare repository, put this in a directory below it.
        # Otherwise put it in the directory above it.
        if git.is_bare_repository():
            path = Path.cwd() / path
        else:
            path = Path(git.get_working_copy_root()) / path

    path = path.resolve()

    return str(path)

# Determine a path and committish from args.
def get_name_path_and_refname(git, gp, clargs):
    """Given a Project and worktree command-line arguments <name-or-path> and
    <committish>, determine an appropriate worktree name, a path based on the
    name and refname based on the name.  If one or the other of <name-or-path>
    or <committish> is not provided, figure it out from the provided value.  If
    neither <name-or-path> nor <committish> is provided, raise an exception.

    """
    name = str(Path(clargs.path).name)
    path = normalize_path(git, clargs.path)
    refname = git.committish_to_refname('HEAD')
    if hasattr(clargs, 'committish') and clargs.committish:
        refname = git.committish_to_refname(clargs.committish)

    return name, path, refname

# worktree add
def command_worktree_add(git, gitproject, project, clargs):
    """Implement git-project worktree add."""
    name, path, refname = get_name_path_and_refname(git, gitproject, clargs)

    branch = git.refname_to_branch_name(refname)
    branch_point = refname

    if not git.committish_exists(branch_point):
        raise GitProjectException(f'Branch point {branch_point} does not exist for worktree add')

    # Either use the branch the user gave us or create a branch (if needed)
    # named after the given name.
    if hasattr(clargs, 'branch') and clargs.branch:
        branch = clargs.branch
        git.create_branch(branch, branch_point)
    elif name != branch:
        branch = name
        if not git.committish_exists(name):
            git.create_branch(branch, branch_point)

    worktree = Worktree.get(git,
                            project,
                            name,
                            path=path,
                            committish=branch)
    worktree.add()

    return worktree

def command_worktree_rm(git, gitproject, project, clargs):
    """Implement git-project worktree rm."""
    name = clargs.name
    worktree = Worktree.get(git, project, name)

    if not project.branch_is_merged(worktree.committish) and not clargs.force:
        raise GitProjectException(f'Worktree branch {worktree.committish} is not merged, use -f to force')

    worktree.rm()

class Worktree(ScopedConfigObject):
    """A ScopedConfigObject to manage worktree git configs."""
    class Path(ConfigObject):
        """A ConfigObject to manage worktree paths.  Each worktree config section has an
        associated worktreepath config section to allow fast mapping from a
        worktree path to its Worktree ConfigObject.

        """

        def __init__(self,
                     git,
                     project_section,
                     subsection,
                     ident,
                     **kwargs):
            """Path construction.

            cls: The derived class being constructed.

            git: An object to query the repository and make config changes.

            project_section: git config section of the active project.

            subsection: An arbitrarily-long subsection appended to project_section

            ident: The name of this specific Build.

            **kwargs: Keyword arguments of property values to set upon construction.

            """
            super().__init__(git,
                             project_section,
                             subsection,
                             ident,
                             **kwargs)

        @classmethod
        def subsection(cls):
            """ConfigObject protocol subsection."""
            return 'worktreepath'

        @classmethod
        def get(cls, git, project_section, path, **kwargs):
            """Factory to construct a worktree Path object.

            git: An object to query the repository and make config changes.

            project_section: git config section of the active project.

            path: The path to reference this Path..

            **kwargs: Keyword arguments of property values to set upon
                      construction.

            """
            return super().get(git,
                               project_section,
                               cls.subsection(),
                               path,
                               **kwargs)

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
        """Worktree construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Build.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         **kwargs)
        self._pathsection = self.Path.get(git,
                                          project_section,
                                          self.path,
                                          worktree=ident)

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'worktree'

    @classmethod
    def get(cls, git, project, name, **kwargs):
        """Factory to construct Worktrees.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        name: Name of the worktree to construct.

        """
        worktree = super().get(git,
                               project.get_section(),
                               cls.subsection(),
                               name,
                               **kwargs)
        project.push_scope(worktree)
        return worktree

    @classmethod
    def get_managing_command(cls):
        return 'worktree'

    @classmethod
    def get_by_path(cls, git, project, path):
        """Given a Project section and a path, get the associated Worktree."""
        pathsection = cls.Path.get(git, project.get_section(), path)
        if hasattr(pathsection, 'worktree'):
            assert pathsection.worktree
            return cls.get(git, project, pathsection.worktree, path=path)
        return None

    def add(self):
        """Create a new worktree"""
        self._git.add_worktree(self.get_ident(), self.path, self.committish)

    def rm(self):
        """Remove a worktree, deleting its workarea, builds and installs."""
        # TODO: Use python utils.
        try:
            shutil.rmtree(self.path)
            shutil.rmtree(self.builddir)
            shutil.rmtree(self.prefix)
            shutil.rmtree(self.installdir)
        except:
            pass

        self._git.prune_worktree(self.get_ident())

        project = Project.get(self._git, self._project_section)

        for branch in project.iterbranches():
            branch_name = self._git.committish_to_refname(branch)
            committish_name = self._git.committish_to_refname(self.committish)
            if branch_name == committish_name:
                break
        else:
            project.prune_branch(self.committish)

        self._pathsection.rm()
        super().rm()

class WorktreePlugin(Plugin):
    """A plugin to provide the git-project worktree command."""

    def __init__(self):
        super().__init__('worktree')

    def initialize(self, git, gitproject, project, plugin_manager):
        """Instantiate a Worktree if we are in a worktree path, providing scoping for
        Project config variables.

        git: A Git object to examine the repository.

        gitproject: A GitProject object to explore and manipulate the active
                    project.

        project: The active Project.

        plugin_manager: The active  PluginManager.

        """
        path = Path.cwd()
        path.resolve()
        while True:
            if ConfigObject.exists(git,
                                   project.get_section(),
                                   Worktree.Path.subsection(),
                                   str(path)):
                worktree = Worktree.get_by_path(git, project, str(path))
                break
            parent = path.parent
            if parent == path:
                break
            path = parent

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manage):
        """Add arguments for 'git-project worktree.'"""

        # worktree
        worktree_parser = add_top_level_command(parser_manager,
                                                Worktree.get_managing_command(),
                                                Worktree.get_managing_command(),
                                                help='Manage worktrees',
                                                formatter_class=argparse.RawDescriptionHelpFormatter)

        add_plugin_version_argument(worktree_parser)

        worktree_subparser = parser_manager.add_subparser(worktree_parser,
                                                          'worktree-command',
                                                          help='worktree commands')

        # worktree add
        worktree_add_parser = parser_manager.add_parser(worktree_subparser,
                                                        'add',
                                                        'worktree-add',
                                                        help='Create a worktree',
                                                        epilog='One of path or committish is required.  If only one is specifiedd, the other will be inferred from the specified value.')

        worktree_add_parser.set_defaults(func=command_worktree_add)

        worktree_add_parser.add_argument('path',
                                         nargs='?',
                                         help='Path for worktree checkout')
        worktree_add_parser.add_argument('committish',
                                         nargs='?',
                                         help='Branch point for worktree')
        worktree_add_parser.add_argument('-b',
                                         '--branch',
                                         metavar='BRANCH',
                                         help='Create BRANCH for the worktree')

        # worktree rm
        worktree_rm_parser = parser_manager.add_parser(worktree_subparser,
                                                       'rm',
                                                       'worktree-rm',
                                                       help='Remove a worktree')

        worktree_rm_parser.set_defaults(func=command_worktree_rm)

        worktree_rm_parser.add_argument('name',
                                        help='Worktree to remove')
        worktree_rm_parser.add_argument('-f', '--force', action='store_true',
                                        help='Remove even if branch is not merged')

        # add a clone option to create a worktree layout.
        clone_parser = parser_manager.find_parser('clone')
        if clone_parser:
            clone_parser.add_argument('--worktree', action='store_true',
                                      help='Create a layout convenient for worktree use')

        # add an init option to create a worktree layout.
        init_parser = parser_manager.find_parser('init')
        if init_parser:
            init_parser.add_argument('--worktree', action='store_true',
                                     help='Create a layout convenient for worktree use')

    def _rewrite_bare_refspects(self, p_git):
        """Modify refspects to convert from a bare repository so that we merge origin
        branches to local branches.

        """
        assert p_git.is_bare_repository()

        p_git.set_remote_fetch_refspecs('origin',
                                        ['+refs/heads/*:refs/remotes/origin/*'])
        p_git.fetch_remote('origin')

        for refname in p_git.iterrefnames(['refs/heads']):
            if refname == 'refs/heads/master':
                remote_refname = p_git.get_remote_fetch_refname(refname, 'origin')
                p_git.set_branch_upstream(refname, remote_refname)
            else:
                p_git.delete_branch(refname)

    def _setup_master_worktree(self,
                               p_git,
                               p_gitproject,
                               p_project,
                               path,
                               clargs):
        """Create a master woorktree for a newly-created worktree layout."""
        # Set up a master worktree.
        master_path = path / 'master'
        setattr(clargs, 'committish', 'master')
        setattr(clargs, 'path', str(master_path))

        command_worktree_add(p_git, p_gitproject, p_project, clargs)

    def modify_arguments(self, git, gitproject, project, parser_manager, plugin_manager):
        """Modify arguments for 'git-project worktree.'"""

        # If a clone is done, set up a master worktree if told to.
        clone_parser = parser_manager.find_parser('clone')
        if clone_parser:
            command_clone = clone_parser.get_default('func')

            def worktree_command_clone(p_git, p_gitproject, p_project, clargs):
                if clargs.worktree:
                    path = Path.cwd()
                    if hasattr(clargs, 'path') and clargs.path:
                        path = Path(clargs.path)

                    path = path / '.git'

                    bare_specified = clargs.bare

                    setattr(clargs, 'path', str(path))
                    setattr(clargs, 'bare', True)

                    # Bare clone to the hidden .git directory.
                    path = command_clone(p_git, p_gitproject, p_project, clargs)

                    # If the user did not ask for a bare repo, rewrite refspecs,
                    # fetch remote refs and rewrite existing refs (just master)
                    # to track the remote ref.  Delete other "local" branches.
                    if not bare_specified:
                        self._rewrite_bare_refspects(p_git)

                    # Detach HEAD so we can worktree master.
                    p_git.detach_head()

                    self._setup_master_worktree(p_git,
                                                p_gitproject,
                                                p_project,
                                                Path(path).parent,
                                                clargs)
                else:
                    path = command_clone(p_git, p_gitproject, p_project, clargs)

                return path

            clone_parser.set_defaults(func=worktree_command_clone)

        # If an init is done, set up a master worktree layout if told to.
        init_parser = parser_manager.find_parser('init')
        if init_parser:
            command_init = init_parser.get_default('func')

            def worktree_command_init(p_git, p_gitproject, p_project, clargs):
                path = command_init(p_git, p_gitproject, p_project, clargs)

                if clargs.worktree:
                    was_bare = p_git.is_bare_repository()

                    # If it's not already, convert the current workarea to a bare repository.
                    if not p_git.is_bare_repository():
                        if not p_git.workarea_is_clean():
                            raise GitProjectException('Cannot initialize worktree layout, working copy not clean')

                        gitdir = Path(p_git.get_gitdir())
                        workarea_root = Path(p_git.get_working_copy_root())
                        assert workarea_root.exists()

                        if gitdir != workarea_root / '.git':
                            raise GitProjectException('Not creating worktree layout -- are you in a worktree?')

                        # Set bare and detach before removing files so they
                        # don't come back.  If we detach later, files will be
                        # checkout out.
                        p_git.config.set_item('core', 'bare', 'true')
                        p_git.detach_head()

                        # Remove everything except .git.
                        for filename in os.listdir(workarea_root):
                            if filename == '.git':
                                continue
                            path = workarea_root / filename
                            if os.path.isfile(path) or os.path.islink(path):
                                os.unlink(path)
                                assert not os.path.exists(path)
                            elif os.path.isdir(path):
                                shutil.rmtree(path)
                                assert not os.path.exists(path)

                    if was_bare:
                        workarea_root = Path(p_git.get_gitdir()).parent

                        # Note that since this is a bare repository, we may have
                        # branches besides master that are not pushed to
                        # whatever remote they should go to.  In general we
                        # cannot know which branches should go where so just
                        # punt and tell the user to clean them up.
                        for refname in p_git.iterrefnames(['refs/heads']):
                            if refname != 'refs/heads/master':
                                raise GitProjectException('Non-master branches detected, please push and/or delete them and try again.')

                        self._rewrite_bare_refspects(p_git)

                    self._setup_master_worktree(p_git,
                                                p_gitproject,
                                                p_project,
                                                workarea_root,
                                                clargs)

            init_parser.set_defaults(func=worktree_command_init)

    def iterclasses(self):
        """Iterate over public classes for git-project worktree."""
        yield Worktree
