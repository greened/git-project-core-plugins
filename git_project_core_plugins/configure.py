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

"""A plugin to add a 'configure' command to git-project.  The configure command
invokes an arbitrary command intended to configure the project for build.

Summary:

git-project configure <flavor>

"""

from git_project import RunnableConfigObject, ConfigObjectItem, Plugin, Project
from git_project import get_or_add_top_level_command, gen_runnable_epilog

import argparse
from pathlib import Path

def command_configure(git, gitproject, project, clargs):
    """Implement git-project configure"""
    configure = Configure.get(git, project, clargs.flavor)
    configure.run(clargs)

def command_add_configure(git, gitproject, project, clargs):
    """Implement git-project add configure"""
    configure = Configure.get(git, project, clargs.flavor, command=clargs.command)
    project.add_item('configure', clargs.flavor)

    return configure

class Configure(RunnableConfigObject):
    """A RunnableConfigObject to manage configure flavors.  Each configure flavor
    gets its own config section.

    """

    _configitems = [ConfigObjectItem('command',
                                     None,
                                     'Command to configure project'),
                    ConfigObjectItem('description',
                                     None,
                                     'Configure flavor help')]

    def __init__(self,
                 git,
                 project_section,
                 subsection,
                 ident,
                 configitems,
                 **kwargs):
        """Configure construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Configure.

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

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return 'configure'

    @classmethod
    def get(cls, git, project, flavor):
        """Factory to construct Configures.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        flavor: Name of the configure to construct.

        """
        return super().get(git,
                           project.section,
                           cls.subsection(),
                           flavor,
                           cls.configitems())

    @staticmethod
    def substitutions():
        """RunnableConfigObject protocol substitutions."""
        return [ConfigObjectItem('path', None, 'Workarea root directory'),
                ConfigObjectItem('builddir', None, 'Project or worktree build directory'),
                ConfigObjectItem('prefix', None, 'Project or worktree install directory'),
                ConfigObjectItem('buildwidth', None, 'Project or worktree build width')]

    @classmethod
    def get_managing_command(cls):
        return 'configure'

class ConfigurePlugin(Plugin):
    """A plugin to add the configure command to git-project"""
    def add_arguments(self, git, gitproject, project, parser_manager):
        """Add arguments for 'git-project configure.'"""
        if git.has_repo():
            add_parser = get_or_add_top_level_command(parser_manager,
                                                      'add',
                                                      'add',
                                                      help=f'Add config sections to {project.section}')

            add_subparser = parser_manager.get_or_add_subparser(add_parser,
                                                                'add-command',
                                                                help='add sections')

            add_configure_parser = parser_manager.add_parser(add_subparser,
                                                             Configure.get_managing_command(),
                                                             'add-' + Configure.get_managing_command(),
                                                             help=f'Add a configure to {project.section}')

            add_configure_parser.set_defaults(func=command_add_configure)

            add_configure_parser.add_argument('flavor',
                                              help='Name for the configure')

            add_configure_parser.add_argument('command',
                                              help='Command to run')

            configures = []
            if hasattr(project, 'configure'):
                configures = [configure for configure in project.iter_multival('configure')]

            command_subparser = parser_manager.find_subparser('command')

            configure_parser = parser_manager.add_parser(command_subparser,
                                                         Configure.get_managing_command(),
                                                         Configure.get_managing_command(),
                                                         help='Configure project',
                                                         formatter_class=
                                                         argparse.RawDescriptionHelpFormatter,
                                                         epilog=
                                                         gen_runnable_epilog(Configure,
                                                                             project,
                                                                             Configure.subsection(),
                                                                             Configure.configitems(),
                                                                             secparam='<flavor>'))

            configure_parser.set_defaults(func=command_configure)

            if configures:
                configure_parser.add_argument('flavor', choices=configures,
                                            help='Configure type')

    def modify_arguments(self, git, gitproject, project, parser_manager, plugin_manager):
        worktree_add_parser = parser_manager.find_parser('worktree-add')

        worktree_add_parser.add_argument('--buildwidth',
                                         dest='buildwidth',
                                         metavar='WIDTH',
                                         help='Default build width for worktree [default: project build width]')

        worktree_add_parser.add_argument('--builddir',
                                         dest='builddir',
                                         metavar='DIR',
                                         help='Where to place build artifacts for worktree [default: project builddir/name]')

        worktree_add_parser.add_argument('--prefix',
                                         metavar='DIR',
                                         help='Where to install for worktree [default: project prefix/name]')

        worktree_add_parser.add_argument('--sharedir',
                                         metavar='DIR',
                                         help='Where to install shared files for worktree [default: project sharedir]')

        if worktree_add_parser:
            command_worktree_add = worktree_add_parser.get_default('func')

            def configure_command_worktree_add(p_git, p_gitproject, p_project, clargs):
                worktree = command_worktree_add(p_git, p_gitproject, p_project, clargs)

                prefix = clargs.prefix if hasattr(clargs, 'prefix') else None
                if not prefix and hasattr(project, 'prefix'):
                    prefix = str(Path(project.prefix) / worktree.name)
                if prefix:
                    worktree.set_item('prefix', prefix)

                sharedir = clargs.sharedir if hasattr(clargs, 'sharedir') else None
                if not sharedir and hasattr(project, 'sharedir'):
                    sharedir = str(Path(project.sharedir) / worktree.name)
                if sharedir:
                    worktree.set_itme('sharedir', sharedir)

                builddir = clargs.builddir if hasattr(clargs, 'builddir') else None
                if not builddir and hasattr(project, 'builddir'):
                    builddir = str(Path(project.builddir) / worktree.name)
                if builddir:
                    worktree.set_item('builddir', builddir)

                return worktree

            worktree_add_parser.set_defaults(func=configure_command_worktree_add)

    def add_class_hooks(self, git, plugin_manager):
        """Add hooks for build."""
        Project.add_config_item('configure',
                                None,
                                'Configures for the project')
        Project.add_config_item('builddir',
                                None,
                                'Default project build directory')
        Project.add_config_item('buildwidth',
                                '1',
                                'Default project build width')
        Project.add_config_item('prefix',
                                None,
                                'Default project install directory')
        Project.add_config_item('sharedir',
                                None,
                                'Default project shared install directory')

        for plugin in plugin_manager.iterplugins():
            for cls in plugin.iterclasses():
                if cls.__name__ == 'Worktree':
                    cls.add_config_item('builddir',
                                        None,
                                        'Default worktree build directory')
                    cls.add_config_item('buildwidth',
                                        '1',
                                        'Default worktree build width')
                    cls.add_config_item('prefix',
                                        None,
                                        'Worktree install directory')
                    cls.add_config_item('sharedir',
                                        None,
                                        'Worktree shared install directory')

    def iterclasses(self):
        """Iterate over public classes for git-project configure."""
        yield Configure
