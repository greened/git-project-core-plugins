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

from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='git_project_core_plugins',
      version='0.0.12',
      description='Core functionality for git-project',
      long_description=readme(),
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Programming Language :: Python :: 3.6',
          'Topic :: Software Development :: Version Control :: Git',
      ],
      keywords='git project development',
      url='http://github.com/greened/git-project-core-plugins',
      author='David A. Greene',
      author_email='dag@obbligato.org',
      license='GPLv3+',
      packages=['git_project_core_plugins'],
      install_requires = [
          'git_project>=0.0.10',
          'progressbar2',
          'pygit2',
      ],
      python_requires='~=3.9',
      entry_points = {
          'git_project.plugins': {
              'artifact = git_project_core_plugins.artifact:ArtifactPlugin',
              'branch = git_project_core_plugins.branch:BranchPlugin',
              'run = git_project_core_plugins.run:RunPlugin',
              'clone = git_project_core_plugins.clone:ClonePlugin',
              'config = git_project_core_plugins.config:ConfigPlugin',
              'help = git_project_core_plugins.help:HelpPlugin',
              'init = git_project_core_plugins.init:InitPlugin',
              'worktree = git_project_core_plugins.worktree:WorktreePlugin',
          }
      },
      zip_safe=False)
