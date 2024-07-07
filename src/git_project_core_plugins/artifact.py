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
from git_project import run_command_with_shell, add_top_level_command

from git_project_core_plugins.common import add_plugin_version_argument

import argparse
import re

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

    def rm(self, git, project, clargs, string):
        """Remove the paths associated with this Artifact.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        clargs: Command-line arguments

        string: The string on which to perform substitution.

        """
        for path in self.iter_multival('path'):
            path = self.substitute_value(git, poject, clargs, path)

def command_artifact_add(git, gitproject, project, clargs):
    """Implement git-project artifact add."""
    ident = clargs.subsection
    path = clargs.path

    artifact = Artifact.get(git, project.get_section(), ident)
    artifact.add_item('path', path)

def command_artifact_rm(git, gitproject, project, clargs):
    """Implement git-project artifact rm."""
    ident = clargs.subsection

    artifact = Artifact.get(git, project.get_section(), ident)

    if hasattr(clargs, 'path') and clargs.path:
        path = clargs.path
        artifact.rm_item('path', path)
    else:
        artifact.rm_items('path')

class ArtifactPlugin(Plugin):
    """
    The artifact command adds or removes associations between git config objects
    and file-system objects.

    Summary:

      git <project> artifact add <subsection> <path>
      git <project> artifact rm <subsection> [<path>]

    <subsection> is a git config section which will appear under the
    <project>.artifact section.  Artifacts look up objects associated with
    <subsection> and perform substitutions on paths to yield the final
    associated file-system object.  The ``artifact rm'' command simply removes
    an artifact association, it does not remove the artifact itself.  Multiple
    artifact paths may be associated under a single <subsection> and the option
    <path> argument to ``artifact rm'' allows us to remove a single association
    rather than all of them at once.

    For example:

      git <project> artifact add worktree.myworktree /path/to/artifact

    Presumably, /path/to/artifact is in some way created in association with
    myworktree, for example by the ``run'' command.  When we delete myworktree,
    the artifact association causes /path/to/artifact to also be removed.
    Substitutions can make artifact associations easier to manage:

      git <project> artifact add worktree /path/to/{worktree}/artifact

    Notice that we've added the artifact under the more general ``worktree''
    subsection instead of naming a worktree explicitly as before.  Because the
    {worktree} substitution appears in the artifact path, deleting any worktree
    will cause the worktree's name to be substituted into the artifact path,
    forming a unique artifact path to remove.

    We may make this even more general:

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

    The worktree plugin also modifies the clone and init commands, adding a
    --worktree option to both.  With --worktree, clone will create a ``worktree
    layout'' as so:

      clonedir
        .git
         master

    Here, ``master'' is a worktree created from the master branch.  ``clonedir''
    becames a bare repository, though with refspecs that make it operate like a
    regular clone for fetch and push operations.  That is, the cloned repository
    will still have refs/heads and refs/remotes namespaces.

    With --worktree, init will take an existing local clone and convert it to a
    bare repository, removing all checked out files and creating a master
    worktree:

      clonedir
        .git
         master

    Conversion will abort if the workarea is not in a clean state.  Note that
    all files in clonedir will be deleted so if there are important files not
    part of the underlying repository, the user must take care to preserve them.
    If the workarea hd a branch other than master checked out, no worktree for
    it will be created automatically, though the user may easily create one
    after conversion.

    See also:

      clone
      config
      init
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
                               help='Subsection under which to add the artifact')
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
                for path in artifact.iter_multival('path'):
                    fullpath = artifact.substitute_value(self._git, project, path)
                    run_command_with_shell(f'rm -rf {fullpath}',
                                           show_command=True)

            config_object_rm(self)

        ConfigObject.rm = artifact_rm
