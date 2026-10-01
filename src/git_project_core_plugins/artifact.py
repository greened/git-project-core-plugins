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

"""A plugin to add a 'config' command to git-project.  The config command sets
project-wide git configuration values and prints their values to stdout.

Summary:

git-project config <key> [--unset] [<value>]

"""

from git_project import ConfigObject, SubstitutableConfigObject, Plugin
from git_project import GitProjectException, add_top_level_command

from git_project_core_plugins.common import add_plugin_version_argument

import argparse
import glob
import os
from pathlib import Path
import re
import shlex
import shutil

def _protected_paths(git):
    """Return the resolved paths that an artifact removal must not remove or
    contain: the root, the home directory and, inside a repository, the
    working copy and the git common dir. Protecting the common dir also
    protects a worktree container, which holds it.

    """
    protected = [Path('/'), Path.home()]
    if git is not None and git.has_repo():
        workdir = git.get_working_copy_root()
        if workdir:
            protected.append(Path(workdir))
        # A worktree's commondir file may hold a relative path, which git
        # reads relative to the worktree's own gitdir, not the cwd.
        common_dir = Path(git.get_git_common_dir())
        if not common_dir.is_absolute():
            common_dir = Path(git.get_gitdir()) / common_dir
        protected.append(common_dir)
    return [path.resolve() for path in protected]

def remove_artifact_path(fullpath, git=None):
    """Remove the file or directory at fullpath, as rm -rf would, without a shell.

    A leading ~ and $VAR references are expanded first, as the shell did. A
    variable that is not set is left as written, where the shell made it
    empty. A path that exists is then removed as written, so spaces and glob
    characters in it are literal. Otherwise it is expanded as a glob, and
    each match is removed. A symbolic link is removed, not its target. An
    empty path removes nothing.

    A match that is a protected path, or that contains one, raises
    GitProjectException before anything is removed. The protected paths are
    the root, the home directory and, when git is given, the working copy
    and the git common dir.

    """
    if not fullpath:
        return

    fullpath = os.path.expandvars(os.path.expanduser(fullpath))

    if os.path.lexists(fullpath):
        paths = [fullpath]
    else:
        paths = sorted(glob.glob(fullpath))

    protected = _protected_paths(git)

    # Check every match before removing any, so a glob that reaches a
    # protected path removes nothing at all. Removing a link never touches
    # its target, so a link needs no check. resolve() would also raise on a
    # link that loops.
    for path in paths:
        if os.path.islink(path):
            continue
        resolved = Path(path).resolve()
        for guard in protected:
            if guard == resolved or guard.is_relative_to(resolved):
                raise GitProjectException(
                    f'Refusing to remove {path}: it is or contains {guard}')

    for path in paths:
        print(f'rm -rf {shlex.quote(path)}')

        if os.path.islink(path):
            os.remove(path)
            continue

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

class Artifact(SubstitutableConfigObject):
    @classmethod
    def _split_ident(cls, ident):
        parts = ident.rsplit('.', 1)

        ident = parts[-1]

        subsection = cls.subsection()
        if len(parts) > 1:
            subsection += '.' + '.'.join(parts[:-1])

        return subsection, ident

    @classmethod
    def get(cls, git, project_section, ident, **kwargs):
        """Factory to construct an Artifact object.

        git: An object to query the repository and make config changes.

        project_section: the active project section.

        ident: The subsection under <project>.artifact where this Artifact will
               live.

        **kwargs: Keyword arguments of property values to set upon
                  construction.

        """
        subsection, ident = cls._split_ident(ident)

        return super().get(git,
                           project_section,
                           subsection,
                           ident,
                           **kwargs)

    @classmethod
    def exists(cls,
               git,
               project_section,
               ident):
        """Return whether an existing git config exists for the Artifact.

        cls: The derived class being checked.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        ident: The subsection under <project>.artifact where this Artifact lives.

        """
        subsection, ident = cls._split_ident(ident)

        return super().exists(git, project_section, subsection, ident)

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 **kwargs):
        """Artifact construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Artifact.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git,
                         project_section,
                         subsection,
                         ident,
                         **kwargs)

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'artifact'

    @classmethod
    def get_managing_command(cls):
        return 'artifact'

def command_artifact_add(git, gitproject, project, clargs):
    """Implement git-project artifact add."""
    ident = clargs.subsection
    path = clargs.path

    artifact = Artifact.get(git, project.get_section(), ident)
    artifact.add_item('itempath', path)

def command_artifact_rm(git, gitproject, project, clargs):
    """Implement git-project artifact rm."""
    ident = clargs.subsection

    artifact = Artifact.get(git, project.get_section(), ident)

    if hasattr(clargs, 'path') and clargs.path:
        path = clargs.path
        artifact.rm_item('itempath', path)
    else:
        artifact.rm_items('itempath')

class ArtifactPlugin(Plugin):
    """
    The artifact command adds or removes associations between git config objects
    and file-system objects.

    Summary::

      git <project> artifact add <subsection> <path>
      git <project> artifact rm <subsection> [<path>]

    <subsection> is a git config section which will appear under the
    <project>.artifact section.  Artifacts look up objects associated with
    <subsection> and perform substitutions on paths to yield the final
    associated file-system object.  The ``artifact rm`` command simply removes
    an artifact association, it does not remove the artifact itself.  Multiple
    artifact paths may be associated under a single <subsection> and the option
    <path> argument to ``artifact rm`` allows us to remove a single association
    rather than all of them at once.

    For example::

      git <project> artifact add worktree.myworktree /path/to/artifact

    Presumably, /path/to/artifact is in some way created in association with
    myworktree, for example by the ``run`` command.  When we delete myworktree,
    the artifact association causes /path/to/artifact to also be removed.
    Substitutions can make artifact associations easier to manage::

      git <project> artifact add worktree /path/to/{worktree}/artifact

    Notice that we've added the artifact under the more general ``worktree``
    subsection instead of naming a worktree explicitly as before.  Because the
    {worktree} substitution appears in the artifact path, deleting any worktree
    will cause the worktree's name to be substituted into the artifact path,
    forming a unique artifact path to remove.

    We may make this even more general::

      git <project> config srcdir "{path}"
      git <project> config builddir "{srcdir}/build/{worktree}"
      git <project> config make "make -C {srcdir} BUILDDIR={builddir} {build}"
      git <project> run --make-alias build
      git <project> add build debug "{make}"
      git <project> add build release "{make}"
      git <project> add build check "{make}"
      git <project> artifact add worktree "{builddir}"

    We've added a single artifact association that will handle any worktree and
    all of our different build types.  When we delete the worktree, all
    artifacts related to debug, release and check builds will also be removed.

    See also::

      config
      run
      worktree

    """

    def __init__(self): super().__init__('artifact')

    def add_arguments(self,
                      git,
                      gitproject,
                      project,
                      parser_manager,
                      plugin_manager):
        """Add arguments for 'git-project artifact.'"""

        artifact_parser = add_top_level_command(parser_manager,
                                                'artifact',
                                                'artifact',
                                                help='Manipulate artifacts')

        add_plugin_version_argument(artifact_parser)

        artifact_subparser = parser_manager.add_subparser(artifact_parser,
                                                          'artifact-command',
                                                          help='artifact commands')

        # add
        add_parser = parser_manager.add_parser(artifact_subparser,
                                               'add',
                                               'artifact-add',
                                               help='Add an artifact',
                                               epilog = """
The <subsection> argument is appended to the <project>.artifact section to form
the final git config section that will hold the artifact path.
""",
                                               formatter_class = argparse.RawDescriptionHelpFormatter)

        add_parser.add_argument('subsection',
                                help='Subsection under which to add the artifact')
        add_parser.add_argument('path',
                                help='Artifact path, may use substitutions')

        add_parser.set_defaults(func=command_artifact_add)

        # rm
        rm_parser = parser_manager.add_parser(artifact_subparser,
                                              'rm',
                                              'artifact-rm',
                                              help='Remove an artifact path',
                                              epilog = """
The <subsection> argument is appended to the <project>.artifact section to form
the final git config section that will hold the artifact path.
""",
                                              formatter_class =
                                              argparse.RawDescriptionHelpFormatter)

        rm_parser.add_argument('subsection',
                               help='Subsection the artifact was added under')
        rm_parser.add_argument('path', nargs='?',
                               help='Artifact path, may use substitutions')

        rm_parser.set_defaults(func=command_artifact_rm)

    def add_class_hooks(self, git, project, plugin_manager):
        # Enhance ConfigObject rm to also remove artifacts.
        config_object_rm = ConfigObject.rm

        def artifact_rm(self):
            # See if there is any artifact associated with this ConfigObject.
            artifact = None
            if Artifact.exists(self._git,
                               self._project_section,
                               self._subsection + '.' + self._ident):
                artifact = Artifact.get(self._git,
                                        self._project_section,
                                        self._subsection + '.' + self._ident)
            elif Artifact.exists(self._git,
                                 self._project_section,
                                 self._subsection):
                artifact = Artifact.get(self._git,
                                        self._project_section,
                                        self._subsection)

            if artifact:
                for path in artifact.iter_multival('itempath'):
                    fullpath = artifact.substitute_value(self._git, project, path)
                    remove_artifact_path(fullpath, self._git)

            config_object_rm(self)

        ConfigObject.rm = artifact_rm
