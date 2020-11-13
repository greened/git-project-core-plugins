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

from git_project import ConfigObject, ConfigObjectItem, Plugin, Project
from git_project import gen_config_epilog, ScopedConfigObject
from git_project import add_top_level_command, GitProjectException

import argparse
import os
from pathlib import Path
import shutil

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
            path = Path(git.get_repository_root()).parent / path

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
        refname = git.committish_name_to_refname(clargs.committish)

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
    if clargs.branch:
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

        _configitems = [ConfigObjectItem('worktree', None, 'Worktree name')]

        def __init__(self,
                     git,
                     project_section,
                     subsection,
                     ident,
                     configitems,
                     **kwargs):
            """Path construction.

            cls: The derived class being constructed.

            git: An object to query the repository and make config changes.

            project_section: git config section of the active project.

            subsection: An arbitrarily-long subsection appended to project_section

            ident: The name of this specific Build.

            configitems: A list of ConfigObjectItem describing members of the config
                         section.

            **kwargs: Keyword arguments of property values to set upon construction.

            """
            super().__init__(git,
                             project_section,
                             subsection,
                             ident,
                             configitems,
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

            configitems: A list of ConfigObjectItem describing members of the config
                         section.

            **kwargs: Keyword arguments of property values to set upon
                      construction.

            """
            return super().get(git,
                               project_section,
                               cls.subsection(),
                               path,
                               cls.configitems(),
                               **kwargs)

    _configitems = [ConfigObjectItem('path', None, 'Worktree path'),
                    ConfigObjectItem('committish', None, 'Worktree branch')]

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 configitems,
                 **kwargs):
        """Worktree construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Build.

        configitems: A list of ConfigObjectItem describing members of the config
                     section.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         configitems,
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
                               project.section,
                               cls.subsection(),
                               name,
                               cls.configitems(),
                               **kwargs)
        project.push_scope(worktree)
        return worktree

    @classmethod
    def get_managing_command(cls):
        return 'worktree'

    @classmethod
    def get_by_path(cls, git, project, path):
        """Given a Project section and a path, get the associated Worktree."""
        pathsection = cls.Path.get(git, project.section, path)
        if hasattr(pathsection, 'worktree'):
            assert pathsection.worktree
            return cls.get(git, project, pathsection.worktree, path=path)
        return None

    def add(self):
        """Create a new worktree"""
        self._git.add_worktree(self.name, self.path, self.committish)

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

        self._git.prune_worktree(self.name)

        project = Project.get(self._git, self._project_section)
        project.prune_branch(self.committish)

        self._pathsection.rm()
        super().rm()

class WorktreePlugin(Plugin):
    """A plugin to provide the git-project worktree command."""

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
                                   project.section,
                                   Worktree.Path.subsection(),
                                   str(path)):
                worktree = Worktree.get_by_path(git, project, str(path))
                break
            parent = path.parent
            if parent == path:
                break
            path = parent

    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project worktree.'"""

        # worktree
        worktree_parser = add_top_level_command(parser_manager,
                                                Worktree.get_managing_command(),
                                                Worktree.get_managing_command(),
                                                help='Manage worktrees',
                                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                                epilog=gen_config_epilog(Worktree,
                                                                         project,
                                                                         Worktree.subsection(),
                                                                         Worktree.configitems(),
                                                                         secparam='<name>'))

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

        # add a clone option to defer creating a master worktree when doing a
        # bare clone.
        clone_parser = parser_manager.find_parser('clone')
        if clone_parser:
            clone_parser.add_argument('--no-master-worktree', action='store_true',
                                      help='Do not create a master worktree (only created with --bare)')

    def modify_arguments(self, git, gitproject, project, parser_manager, plugin_manager):
        """Modify arguments for 'git-project worktree.'"""

        # If a bare clone is done, set up a master worktree unless told not to.
        clone_parser = parser_manager.find_parser('clone')
        if clone_parser:
            command_clone = clone_parser.get_default('func')
            def worktree_command_clone(p_git, p_gitproject, p_project, clargs):
                path = command_clone(p_git, p_gitproject, p_project, clargs)
                if clargs.bare and not clargs.no_master_worktree:
                    barepath = (Path(path).parent / '.bare.git').resolve()
                    dotgitpath = (barepath.parent / '.git').resolve()
                    os.rename(path, barepath)
                    os.symlink(barepath, dotgitpath)
                    path = str(dotgitpath)

                    # Make HEAD point to something other than master so we can
                    # worktree master.
                    git.create_branch('git-project-init', 'HEAD')
                    git.update_symbolic_ref('HEAD', 'refs/heads/git-project-init')

                    # Set up a master worktree.
                    setattr(clargs, 'committish', 'master')
                    setattr(clargs, 'path', 'master')
                    command_worktree_add(clargs)
                return path

            clone_parser.set_defaults(func=worktree_command_clone)

    def iterclasses(self):
        """Iterate over public classes for git-project worktree."""
        yield Worktree
