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

"""Build the PyPI long description, command reference included.

The package docstring appends the command reference at import time, so the
docs and ``help()`` get it for free.  A build cannot rely on that: importing
the package needs its dependencies installed, which is not true while the
package is being built.  So this hook parses the sources instead, sharing the
formatter with the runtime path.

This replaces hatch-fancy-pypi-readme for this package, because that hook can
only concatenate files and text, and the reference is neither.
"""

import ast
import importlib.util
import re
from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface


def _load_commanddocs():
    """Load the formatter WITHOUT importing the package.

    A plain import would run ``git_project_core_plugins/__init__.py``, which
    imports git_project, so the build would need the runtime dependency
    installed before it could compute its own metadata.  This module stands
    alone, so load it straight from its path.
    """
    path = Path(__file__).parent / 'src' / 'git_project_core_plugins' / '_commanddocs.py'
    spec = importlib.util.spec_from_file_location('_commanddocs', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_commanddocs = _load_commanddocs()
format_reference = _commanddocs.format_reference
from_source = _commanddocs.from_source

REPO = 'https://github.com/greened/git-project-core-plugins'

#: A relative ``target_:path`` link, which PyPI cannot resolve.
_RELATIVE_LINK = re.compile(r'(.+?)_:((?!https?://)\S+?)')
_ISSUE_REF = re.compile(r':issue:`(\d+)`')


class ReadmeMetadataHook(MetadataHookInterface):
    """Assemble the long description: prose, command reference, authors."""

    # hatchling loads an in-tree hook only under the reserved name 'custom';
    # any other name has to be an installed plugin.
    PLUGIN_NAME = 'custom'

    def update(self, metadata):
        package = Path(self.root) / 'src' / 'git_project_core_plugins'

        prose = ast.get_docstring(ast.parse((package / '__init__.py').read_text()))
        reference = format_reference(from_source(package))

        authors = (Path(self.root) / 'docs' / 'authors.rst').read_text()
        authors = authors[:authors.index('A full list of contributors')]

        # The prose ends in a literal block, so the sections need a blank line
        # between them or the next one unindents into it.  That is an RST error
        # and PyPI rejects a description that fails to render.
        text = '\n'.join([prose, reference, authors])

        text = _RELATIVE_LINK.sub(rf'\1_:{REPO}/tree/main/\g<2>', text)
        text = _ISSUE_REF.sub(rf'#\1_: {REPO}/issues/\1', text)

        metadata['readme'] = {
            'content-type': 'text/x-rst',
            'text': text,
        }
