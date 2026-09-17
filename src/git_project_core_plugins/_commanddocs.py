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

"""Build the command reference from the plugin classes.

Each ``<Name>Plugin`` class documents its own command, so that docstring is the
only place the command is described.  This module renders those docstrings as
an RST section, which the package docstring appends at import time and the
build appends to the PyPI description.  A hand-maintained copy drifted from the
classes it was copied from, which is the failure this replaces.

Two extractors, one formatter.  ``from_classes`` introspects imported
classes and serves the runtime docstring.  ``from_source`` parses the
sources with ``ast`` and serves the build, where importing the package would
require its dependencies to be installed first.
"""

import ast
import inspect
import re
from pathlib import Path

HEADING = 'Command Reference'

#: A plugin class named ``WorktreePlugin`` documents the ``worktree`` command.
_PLUGIN_CLASS = re.compile(r'(\w+)Plugin$')


def _command_name(class_name):
    """Return the command a plugin class documents, or None if it is not one."""
    match = _PLUGIN_CLASS.fullmatch(class_name)
    return match.group(1).lower() if match else None


def format_reference(commands):
    """Render a command -> docstring mapping as the RST reference section.

    commands: A mapping of command name to that command's docstring.

    """
    if not commands:
        return ''

    out = ['', HEADING, '=' * len(HEADING), '']
    for name in sorted(commands):
        body = inspect.cleandoc(commands[name]).rstrip()
        if not body:
            continue
        out += [name, '-' * len(name), '', body, '']
    return '\n'.join(out) + '\n'


def from_classes(namespace):
    """Collect command docstrings from the plugin classes in a namespace.

    namespace: A mapping of name to object, normally ``globals()``.

    """
    commands = {}
    for name, obj in namespace.items():
        command = _command_name(name) if isinstance(obj, type) else None
        if command and obj.__doc__:
            commands[command] = obj.__doc__
    return commands


def from_source(package_dir):
    """Collect command docstrings by parsing the sources, without importing them.

    package_dir: Path to the directory holding the plugin modules.

    """
    commands = {}
    for path in sorted(Path(package_dir).glob('*.py')):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            command = _command_name(node.name)
            doc = ast.get_docstring(node, clean=False)
            if command and doc:
                commands[command] = doc
    return commands
