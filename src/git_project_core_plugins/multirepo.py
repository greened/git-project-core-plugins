#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2020-present David A. Greene <dag@obbligato.org>

# SPDX-License-Identifier: AGPL-3.0-or-later

# Copyright 2026 David A. Greene

# This file is part of git-project

# git-project is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

"""A plugin to add 'multirepo' and 'set' commands to git-project. The
multirepo command runs one git-project command in every repository of a set,
and the set command manages the sets.

Summary:

git-project multirepo [-j <n>] [--skip-missing] [--commit <member> <sha>]
                      <set> <command> [<arg>...]
git-project set list [<set>]
git-project set add <set> <member> [--url <url> --root <root>]
git-project set rm <set> <member>
git-project set clone <set>

"""

import argparse
import codecs
import contextlib
import fcntl
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pygit2
from git_project import Git, GitProjectError, Plugin, add_top_level_command

from git_project_core_plugins.common import (
    _GIT_REDIRECT_VARS,
    add_plugin_version_argument,
)
from git_project_core_plugins.worktree import (
    branch_name_for_path,
    default_branch_point,
    umbrella_of_store,
)

# No dots, so a subsection such as repo.<name> splits one way only.
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_SCHEME_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
_HEX = re.compile(r"[0-9a-fA-F]{4,64}")

_ALLOWED = (
    ("worktree", "add"),
    ("worktree", "rm"),
    ("worktree", "config"),
    ("branch", "status"),
    ("branch", "prune"),
    ("config",),
    ("run",),
)
_WORKTREE_ADD = ("worktree", "add")
_WORKTREE_RM = ("worktree", "rm")
_BRANCH_PRUNE = ("branch", "prune")
_RUN = ("run",)

# The options multirepo passes to worktree add and rm itself.
_RESERVED = ("--check", "--multirepo")

# The worktree add options that --commit knows how to pass on.
_ADD_DESTS = {"path", "committish", "branch", "check", "multirepo"}

_MAX_JOBS = 16
# How long a child has to exit after SIGTERM before it gets SIGKILL.
_KILL_GRACE = 5
_POLL = 0.05


# The set file


@dataclass
class _Member:
    name: str
    url: str
    root: str

    @property
    def path(self):
        return Path(os.path.expanduser(self.root))


@dataclass
class _SetFile:
    members: dict[str, _Member]
    sets: dict[str, list[str]]


def _global_configs():
    """Return the global configs that git itself would read."""
    # libgit2 ignores GIT_CONFIG_GLOBAL, and git reads only that file when
    # it is set.
    override = os.environ.get("GIT_CONFIG_GLOBAL")
    if override is not None:
        return [pygit2.Config(override)] if override else []
    configs = []
    for getter in (
        pygit2.Config.get_xdg_config,
        pygit2.Config.get_global_config,
    ):
        with contextlib.suppress(OSError):
            configs.append(getter())
    return configs


def _locate(ns):
    """Return the set file that <ns>.set.file names, and its resolved path."""
    key = f"{ns}.set.file"
    values = []
    for config in _global_configs():
        values += list(config.snapshot().get_multivar(key))
    if not values:
        raise GitProjectError(f"{key} is not set in the global git config")
    if len(values) > 1:
        raise GitProjectError(f"{key} has {len(values)} values, not one")
    if not values[0]:
        raise GitProjectError(f"{key} has no value")

    path = Path(os.path.expanduser(values[0]))
    if not path.is_absolute():
        raise GitProjectError(f"{key} is {values[0]}, not an absolute path")
    if not path.exists():
        raise GitProjectError(f"Set file {path} does not exist")
    if not path.is_file():
        raise GitProjectError(f"Set file {path} is not a regular file")
    return path, path.resolve()


def _url_is_absolute(url):
    if url.startswith("/") or _SCHEME_URL.match(url):
        return True
    # git reads host:path as scp-style when the colon comes before any slash.
    colon = url.find(":")
    slash = url.find("/")
    return 0 < colon < len(url) - 1 and (slash == -1 or colon < slash)


def _parse(config, ns, origin):
    """Validate the whole set file in config and return its contents. Raise
    GitProjectError listing every problem found.

    """
    errors = []
    urls: dict[str, list] = {}
    roots: dict[str, list] = {}
    sets: dict[str, list] = {}
    for entry in config:
        name = entry.name
        section, _, rest = name.partition(".")
        subsection, _, key = rest.rpartition(".")
        # git folds the case of section and key names, not subsections.
        if section != ns.lower():
            errors.append(f"unknown key {name}")
            continue
        if subsection == "set" and key == "file":
            # The locator, in a set file that the global config includes.
            continue
        kind, _, ident = subsection.partition(".")
        if kind == "repo" and key == "url":
            target = urls
        elif kind == "repo" and key == "root":
            target = roots
        elif kind == "set" and key == "repo":
            target = sets
        else:
            errors.append(f"unknown key {name}")
            continue
        if not _NAME.fullmatch(ident):
            errors.append(f"{name}: {ident!r} is not a valid name")
            continue
        target.setdefault(ident, []).append(entry.value)

    members = {}
    for ident in sorted(urls.keys() | roots.keys()):
        member_urls = urls.get(ident, [])
        member_roots = roots.get(ident, [])
        if len(member_urls) != 1 or len(member_urls[0] or "") == 0:
            errors.append(f"member {ident} needs exactly one url")
            continue
        if len(member_roots) != 1 or len(member_roots[0] or "") == 0:
            errors.append(f"member {ident} needs exactly one root")
            continue
        url, root = member_urls[0], member_roots[0]
        home = Path.home()
        expanded = Path(os.path.normpath(os.path.expanduser(root)))
        if not root.startswith("~/") or not expanded.is_relative_to(home):
            errors.append(f"member {ident}: root {root} must start with ~/")
            continue
        if expanded == home:
            errors.append(f"member {ident}: root {root} is the home directory")
            continue
        if not _url_is_absolute(url):
            errors.append(f"member {ident}: url {url} is a relative path")
            continue
        members[ident] = _Member(ident, url, root)

    seen_roots = {}
    for member in members.values():
        # Resolved, so a symlink cannot give one root two names.
        key = member.path.resolve()
        if key in seen_roots:
            errors.append(
                f"members {seen_roots[key]} and {member.name} have the same "
                f"root {member.root}"
            )
        else:
            seen_roots[key] = member.name

    # A set exists only through its repo keys, so none is empty. A section
    # with no keys is no set at all.
    for set_name, repos in sets.items():
        seen = set()
        for repo in repos:
            if repo is None or not _NAME.fullmatch(repo):
                errors.append(f"set {set_name}: {repo!r} is not a valid name")
                continue
            if repo in seen:
                errors.append(f"set {set_name} lists {repo} twice")
            seen.add(repo)
            if repo not in urls and repo not in roots:
                errors.append(f"set {set_name} lists undefined member {repo}")

    if errors:
        raise GitProjectError(
            f"Invalid set file {origin}:\n  " + "\n  ".join(errors)
        )
    return _SetFile(members, sets)


def _load(ns):
    """Read and validate the set file from one snapshot."""
    path, resolved = _locate(ns)
    return _parse(pygit2.Config(str(resolved)).snapshot(), ns, path)


def _check_name(kind, name):
    if not _NAME.fullmatch(name):
        raise GitProjectError(f"{name!r} is not a valid {kind} name")


def _get_set(setfile, name):
    if name not in setfile.sets:
        raise GitProjectError(f"No set named {name}")
    return setfile.sets[name]


def _edit_set_file(ns, edit):
    """Change the set file through edit(setfile, tmp), which edits a copy at
    tmp. Check the copy, then move it over the file. A lock keeps two
    writers from losing each other's change.

    """
    path, resolved = _locate(ns)
    # Not <file>.lock, which is git's own lock file name. Never removed,
    # since a waiter would then lock the old inode while a newcomer locks a
    # new one.
    lock_path = resolved.with_name(resolved.name + ".multirepo-lock")
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        fd, tmp = tempfile.mkstemp(
            dir=resolved.parent, prefix=f".{resolved.name}.", suffix=".tmp"
        )
        os.close(fd)
        try:
            shutil.copyfile(resolved, tmp)
            # From the copy, so the edit is decided on the text it changes.
            setfile = _parse(pygit2.Config(tmp).snapshot(), ns, path)
            edit(setfile, tmp)
            _parse(
                pygit2.Config(tmp).snapshot(), ns, f"{path} after the change"
            )
            # libgit2 writes through a rename, which drops the mode.
            shutil.copymode(resolved, tmp)
            with open(tmp, "rb") as written:
                os.fsync(written.fileno())
            # The resolved path, so a symlink into dotfiles stays a symlink.
            os.replace(tmp, resolved)
            tmp = None
            directory = os.open(resolved.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if tmp is not None:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(tmp)
    finally:
        os.close(lock)


# Members


@dataclass
class _Resolution:
    member: _Member
    # "ok", "missing" or "invalid"
    state: str
    reason: str = ""
    umbrella: Path | None = None
    store: Path | None = None


def _normalize_url(url):
    if url.endswith("/"):
        url = url[:-1]
    if url.endswith(".git"):
        url = url[:-4]
    return url


def _resolve(member):
    """Find out whether member's root is the umbrella of a clone of its url."""
    root = member.path
    if not os.path.lexists(root):
        return _Resolution(member, "missing", f"{root} does not exist")

    def invalid(reason):
        return _Resolution(member, "invalid", f"{root} {reason}")

    resolved = root.resolve()
    try:
        repo = pygit2.Repository(
            str(resolved), pygit2.enums.RepositoryOpenFlag.NO_SEARCH
        )
    except (pygit2.GitError, KeyError):
        return invalid("is not a git repository")

    store = Path(repo.path).resolve()
    if (
        not repo.is_bare
        or (store / "commondir").exists()
        or umbrella_of_store(store) != resolved
    ):
        return invalid("is not an umbrella")

    try:
        origin = repo.remotes["origin"].url
    except KeyError:
        return invalid("has no origin remote")
    # The urls may hold credentials, so name neither.
    if origin is None or _normalize_url(origin) != _normalize_url(member.url):
        return invalid(f"has an origin url other than member {member.name}'s")

    return _Resolution(member, "ok", umbrella=resolved, store=store)


def _resolve_set(setfile, name, allow_missing):
    """Resolve each member of set name, in set order. Raise GitProjectError
    for any invalid member, and for a missing one unless allow_missing.

    """
    resolutions = [
        _resolve(setfile.members[member]) for member in _get_set(setfile, name)
    ]
    problems = [
        f"{r.member.name}: {r.reason}"
        for r in resolutions
        if r.state == "invalid" or (r.state == "missing" and not allow_missing)
    ]
    if problems:
        raise GitProjectError(
            f"Cannot run in set {name}:\n  " + "\n  ".join(problems)
        )
    return resolutions


# Children


def _refuse_redirect_vars():
    found = [var for var in _GIT_REDIRECT_VARS if var in os.environ]
    if found:
        raise GitProjectError(f"Refusing to run with {', '.join(found)} set")


def _child_executable():
    """Return this program as an absolute path, so a child started in another
    directory runs it. Its name is kept, since the project comes from it.

    """
    exe = sys.argv[0]
    if os.sep not in exe:
        found = shutil.which(exe)
        if found is None:
            raise GitProjectError(f"Cannot find {exe} on PATH")
        exe = found
    exe = os.path.abspath(exe)
    if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
        raise GitProjectError(f"{exe} is not an executable file")
    return exe


@dataclass
class _Task:
    member: str
    argv: list[str]
    cwd: str
    rc: int | None = None
    error: str = ""
    output: object = None
    detail: str = ""

    def ok(self):
        return self.rc == 0

    def result(self):
        if self.error:
            return "failed to start"
        if self.rc is None:
            return "not run"
        if self.rc == 0:
            return "ok"
        if self.rc < 0:
            return f"killed by signal {-self.rc}"
        return f"failed ({self.rc})"


class _Cancel:
    """Record SIGINT, SIGTERM and SIGHUP while children run."""

    def __init__(self):
        self.signals = []
        self._old = {}

    def __enter__(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            self._old[signum] = signal.signal(signum, self._handle)
        return self

    def __exit__(self, *exc):
        for signum, handler in self._old.items():
            signal.signal(signum, handler)

    def _handle(self, signum, frame):
        self.signals.append(signum)

    @property
    def cancelled(self):
        return bool(self.signals)

    @property
    def terminated(self):
        # A -j child has a session of its own, so a hangup never reaches it.
        return any(
            signum in self.signals
            for signum in (signal.SIGTERM, signal.SIGHUP)
        )

    def exit_status(self):
        return 128 + self.signals[0]


def _print_output(task):
    """Print a child's spooled output without reading it all into memory."""
    out = task.output
    out.seek(0)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    while chunk := out.read(65536):
        sys.stdout.write(decoder.decode(chunk))
    sys.stdout.write(decoder.decode(b"", final=True))
    sys.stdout.flush()


def _start(task, capture, new_session):
    if capture:
        task.output = tempfile.TemporaryFile()
    sys.stdout.flush()
    try:
        return subprocess.Popen(
            task.argv,
            cwd=task.cwd,
            stdin=subprocess.DEVNULL if capture else None,
            stdout=task.output,
            stderr=subprocess.STDOUT if capture else None,
            start_new_session=new_session,
        )
    except OSError as exception:
        task.error = str(exception)
        return None


def _run_serial(tasks, cancel, capture):
    for task in tasks:
        if cancel.cancelled:
            break
        if not capture:
            print(f"== {task.member}")
        # The child shares the terminal's process group, so a Ctrl-C reaches
        # it without help.
        proc = _start(task, capture, new_session=False)
        if proc is None:
            continue
        if cancel.cancelled and not cancel.terminated:
            # A Ctrl-C that came after the check above may have missed it.
            proc.send_signal(signal.SIGINT)
        term_sent = None
        killed = False
        while True:
            try:
                task.rc = proc.wait(timeout=_POLL)
                break
            except subprocess.TimeoutExpired:
                pass
            # SIGTERM comes to the parent alone, so pass it on.
            if cancel.terminated:
                if term_sent is None:
                    proc.send_signal(signal.SIGTERM)
                    term_sent = time.monotonic()
                elif (
                    not killed and time.monotonic() - term_sent >= _KILL_GRACE
                ):
                    proc.kill()
                    killed = True


def _killpg(pgid, signum):
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signum)


def _group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _run_parallel(tasks, jobs, cancel, on_done):
    pending = deque(tasks)
    running = []
    # A group can outlive its leader, so keep each one signalled until it is
    # gone or has had SIGKILL.
    groups = []
    term_sent = None
    killed = False
    try:
        while pending or running or (groups and not killed):
            if cancel.cancelled:
                pending.clear()
            while pending and len(running) < jobs:
                task = pending.popleft()
                # Its own session, so the terminal's signals and input never
                # reach it.
                proc = _start(task, capture=True, new_session=True)
                if proc is not None:
                    running.append((task, proc))

            if cancel.cancelled and running and term_sent is None:
                # A Ctrl-C goes on as SIGINT, so a member's own interrupt
                # handling, such as the add's undo, runs.
                signum = signal.SIGTERM if cancel.terminated else signal.SIGINT
                for _task, proc in running:
                    _killpg(proc.pid, signum)
                    groups.append(proc.pid)
                term_sent = time.monotonic()
            if term_sent is not None and not killed:
                groups = [pgid for pgid in groups if _group_alive(pgid)]
                if time.monotonic() - term_sent >= _KILL_GRACE:
                    for pgid in groups:
                        _killpg(pgid, signal.SIGKILL)
                    killed = True

            for item in list(running):
                task, proc = item
                rc = proc.poll()
                if rc is not None:
                    running.remove(item)
                    task.rc = rc
                    if on_done is not None:
                        on_done(task)
            if running or (groups and not killed):
                time.sleep(_POLL)
    finally:
        # Only an error here leaves children behind.
        for _task, proc in running:
            _killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def _run(tasks, jobs, cancel, capture, on_done=None):
    """Run each task's child, serially or up to jobs at once. Stop starting
    children once cancel records a signal.

    """
    if jobs is None:
        _run_serial(tasks, cancel, capture)
    else:
        _run_parallel(tasks, jobs, cancel, on_done)


def _print_block(task):
    print(f"== {task.member}")
    _print_output(task)


def _print_summary(tasks, skipped=()):
    rows = [
        (task.member, task.result(), task.error or task.detail)
        for task in tasks
    ]
    rows += [(name, "skipped", reason) for name, reason in skipped]
    width = max([len("member")] + [len(row[0]) for row in rows])
    result_width = max([len("result")] + [len(row[1]) for row in rows])
    print()
    print(f"{'member':<{width}}  {'result':<{result_width}}  detail")
    for member, result, detail in rows:
        print(
            f"{member:<{width}}  {result:<{result_width}}  {detail}".rstrip()
        )


def _close_outputs(tasks):
    for task in tasks:
        if task.output is not None:
            task.output.close()


# multirepo


def _jobs(value):
    try:
        jobs = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a number") from None
    if not 1 <= jobs <= _MAX_JOBS:
        raise argparse.ArgumentTypeError(
            f"{value} is not from 1 to {_MAX_JOBS}"
        )
    return jobs


def _refuse_reserved(args):
    """Refuse any form of an option multirepo passes itself, wherever it
    appears, so a user's copy cannot replace it or ride along.

    """
    for arg in args:
        if not arg.startswith("--") or arg == "--":
            continue
        name = arg.partition("=")[0]
        for option in _RESERVED:
            # An abbreviation, as argparse accepts one.
            if option.startswith(name):
                raise GitProjectError(
                    f"multirepo passes {option} itself, so {arg} is refused"
                )


def _options(args):
    return args[: args.index("--")] if "--" in args else args


def _child_path(umbrella, path):
    """Return the path a child at umbrella gives worktree add's <path>."""
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = umbrella / path
    return path.resolve()


def _record_values(store, ns, name, key):
    config = pygit2.Config(str(store / "config")).snapshot()
    return list(config.get_multivar(f"{ns}.worktree.{name}.{key}"))


def _describe_add(resolution, ns, add_args, task):
    """Say how to undo a successful add, or what a failed one left."""
    name = Path(add_args.path).name
    try:
        if task.ok():
            created = _record_values(
                resolution.store, ns, name, "branchcreated"
            )
            if created == ["true"]:
                return f"undo: worktree rm {shlex.quote(name)}"
            return f"undo: worktree rm --keep-branch {shlex.quote(name)}"

        repo = pygit2.Repository(str(resolution.store))
        branch = add_args.branch or branch_name_for_path(add_args.path)
        path = _child_path(resolution.umbrella, add_args.path)
        config = pygit2.Config(str(resolution.store / "config")).snapshot()
        prefix = f"{ns}.worktree.{name}.".lower()
        has_record = any(
            entry.name.lower().startswith(prefix) for entry in config
        )

        def state(present):
            return "exists" if present else "absent"

        return ", ".join(
            [
                f"branch {branch} "
                + state(repo.branches.local.get(branch) is not None),
                f"record {state(has_record)}",
                f"worktree {state(name in repo.list_worktrees())}",
                f"path {state(os.path.lexists(path))}",
            ]
        )
    except (pygit2.GitError, KeyError, ValueError, OSError) as exception:
        return f"cannot inspect: {exception}"


def _store_branch_point(resolution, ns):
    """Return the commit a plain worktree add in the member branches from."""
    # Git finds the current worktree from the process cwd, even after reinit,
    # so stand where the child would.
    cwd = os.getcwd()
    try:
        os.chdir(resolution.umbrella)
        try:
            refname = default_branch_point(Git(), ns)
        finally:
            os.chdir(cwd)
        repo = pygit2.Repository(str(resolution.store))
        return repo.revparse_single(refname).peel(pygit2.Commit)
    except (KeyError, ValueError, pygit2.GitError):
        raise GitProjectError(
            f"Cannot find the commit worktree add would start from in "
            f"{resolution.member.name}"
        ) from None


def _map_commit(commit, set_name, setfile, active, ns, add_args):
    """Return the branch point OID for each active member, and the problems
    that preflight must report.

    """
    source, sha = commit
    by_name = {r.member.name: r for r in active}
    if source not in by_name:
        if source in setfile.sets[set_name]:
            raise GitProjectError(f"--commit member {source} was skipped")
        raise GitProjectError(f"{source} is not a member of set {set_name}")
    if not _HEX.fullmatch(sha):
        raise GitProjectError(f"{sha} is not a commit id")

    try:
        target = pygit2.Repository(str(by_name[source].store))[sha]
        target = target.peel(pygit2.Commit)
    except (KeyError, ValueError, pygit2.GitError):
        raise GitProjectError(f"{sha} is not a commit in {source}") from None
    when = target.author.time

    oids = {}
    no_candidate = []
    for resolution in active:
        name = resolution.member.name
        if name == source:
            oids[name] = str(target.id)
            continue
        # Author times need not rise along the history, so take the first
        # one in walk order rather than the newest by date.
        candidate = _store_branch_point(resolution, ns)
        while candidate is not None and candidate.author.time > when:
            candidate = candidate.parents[0] if candidate.parents else None
        if candidate is None:
            no_candidate.append(name)
        else:
            oids[name] = str(candidate.id)
    if no_candidate:
        raise GitProjectError(
            f"No commit at or before {sha}'s author date in "
            + ", ".join(no_candidate)
        )

    # worktree add reuses an existing branch, so one at another commit would
    # not start where the table says.
    problems = {}
    if not add_args.branch:
        branch = branch_name_for_path(add_args.path)
        for resolution in active:
            name = resolution.member.name
            repo = pygit2.Repository(str(resolution.store))
            existing = repo.branches.local.get(branch)
            if existing is not None and str(existing.target) != oids[name]:
                problems[name] = (
                    f"Branch {branch} exists at {existing.target}, not at "
                    f"{oids[name]}"
                )

    for resolution in active:
        name = resolution.member.name
        print(f"{name}: branch point {oids[name]}")
    return oids, problems


def _commit_args(add_args, parser, oid):
    """Return worktree add arguments that pass oid as the committish."""
    for dest, value in vars(add_args).items():
        if dest not in _ADD_DESTS and value != parser.get_default(dest):
            raise GitProjectError(
                f"--commit cannot pass on the worktree add option for {dest}"
            )
    args = ["-b", add_args.branch] if add_args.branch else []
    # After --, so a path that starts with - stays a path.
    return [*args, "--", add_args.path, oid]


def command_multirepo(git, gitproject, project, clargs):
    """Implement git-project multirepo."""
    ns = project.get_section()
    _refuse_redirect_vars()

    command = list(clargs.cmd)
    prefix = next((p for p in _ALLOWED if tuple(command[: len(p)]) == p), None)
    if prefix is None:
        allowed = ", ".join(" ".join(p) for p in _ALLOWED)
        hint = ""
        if command and command[0].startswith("-"):
            hint = " multirepo's options go before the set name."
        raise GitProjectError(
            f"multirepo cannot run {shlex.join(command) or 'nothing'}. "
            f"It runs: {allowed}.{hint}"
        )
    args = command[len(prefix) :]
    is_add = prefix == _WORKTREE_ADD
    is_rm = prefix == _WORKTREE_RM
    if is_add or is_rm:
        _refuse_reserved(args)

    if clargs.jobs is not None:
        if prefix == _RUN:
            raise GitProjectError("-j cannot be used with run")
        if prefix == _BRANCH_PRUNE and "--no-ask" not in _options(args):
            raise GitProjectError("-j needs --no-ask with branch prune")
    if clargs.commit is not None and not is_add:
        raise GitProjectError("--commit works only with worktree add")

    _check_name("set", clargs.set)
    exe = _child_executable()
    setfile = _load(ns)
    resolutions = _resolve_set(setfile, clargs.set, clargs.skip_missing)
    skipped = [
        (r.member.name, r.reason) for r in resolutions if r.state == "missing"
    ]
    for name, reason in skipped:
        print(f"Skipping {name}: {reason}")
    active = [r for r in resolutions if r.state == "ok"]
    if not active:
        raise GitProjectError(f"No member of set {clargs.set} can run")

    add_args = None
    if is_add:
        add_parser = clargs.worktree_add_parser.parser
        add_args = add_parser.parse_args(args)
        # Preflight checks each member alone, so it cannot see two of them
        # about to add the same path.
        seen = {}
        for r in active:
            path = _child_path(r.umbrella, add_args.path)
            if path in seen:
                raise GitProjectError(
                    f"Members {seen[path]} and {r.member.name} would both add "
                    f"a worktree at {path}"
                )
            seen[path] = r.member.name
    member_args = {r.member.name: list(args) for r in active}
    problems = {}
    if clargs.commit is not None:
        if add_args.committish:
            raise GitProjectError(
                "--commit cannot be used with a worktree add committish"
            )
        oids, problems = _map_commit(
            clargs.commit, clargs.set, setfile, active, ns, add_args
        )
        member_args = {
            name: _commit_args(add_args, add_parser, oid)
            for name, oid in oids.items()
        }

    injected = ["--multirepo", clargs.set] if is_add or is_rm else []

    def tasks(check):
        options = ["--check", *injected] if check else injected
        return [
            _Task(
                r.member.name,
                [exe, *prefix, *options, *member_args[r.member.name]],
                str(r.umbrella),
            )
            for r in active
        ]

    checks = []
    work = tasks(check=False)
    try:
        with _Cancel() as cancel:
            if is_add or is_rm:
                checks = tasks(check=True)
                _run(checks, clargs.jobs, cancel, capture=True)
                if cancel.cancelled:
                    _print_summary(checks, skipped)
                    return cancel.exit_status()
                failed = {
                    task.member for task in checks if not task.ok()
                } | set(problems)
                if failed:
                    for task in checks:
                        if task.member in problems:
                            print(f"== {task.member}")
                            print(problems[task.member])
                        if not task.ok():
                            _print_block(task)
                    raise GitProjectError(
                        f"Preflight failed in {len(failed)} of "
                        f"{len(checks)} members, so nothing ran"
                    )

            _run(
                work,
                clargs.jobs,
                cancel,
                capture=clargs.jobs is not None,
                on_done=_print_block,
            )
    finally:
        _close_outputs(checks)
        _close_outputs(work)

    if is_add:
        by_name = {r.member.name: r for r in active}
        for task in work:
            if task.rc is not None:
                task.detail = _describe_add(
                    by_name[task.member], ns, add_args, task
                )
    _print_summary(work, skipped)

    if cancel.cancelled:
        return cancel.exit_status()
    return 0 if all(task.ok() for task in work) else 1


# set


def command_set_list(git, gitproject, project, clargs):
    """Implement git-project set list."""
    setfile = _load(project.get_section())
    names = sorted(setfile.sets)
    if clargs.set is not None:
        _get_set(setfile, clargs.set)
        names = [clargs.set]
    for name in names:
        print(name)
        rows = []
        for member in setfile.sets[name]:
            resolution = _resolve(setfile.members[member])
            state = resolution.state
            if state == "invalid":
                state = f"invalid: {resolution.reason}"
            rows.append((member, setfile.members[member].root, state))
        width = max(len(row[0]) for row in rows)
        root_width = max(len(row[1]) for row in rows)
        for member, root, state in rows:
            print(f"  {member:<{width}}  {root:<{root_width}}  {state}")


def command_set_add(git, gitproject, project, clargs):
    """Implement git-project set add."""
    ns = project.get_section()
    _check_name("set", clargs.set)
    _check_name("member", clargs.member)
    if (clargs.url is None) != (clargs.root is None):
        raise GitProjectError("--url and --root go together")

    def edit(setfile, tmp):
        member = setfile.members.get(clargs.member)
        if member is None and clargs.url is None:
            raise GitProjectError(
                f"Member {clargs.member} is not defined, so give --url and "
                f"--root"
            )
        if (
            member is not None
            and clargs.url is not None
            and (clargs.url != member.url or clargs.root != member.root)
        ):
            # Every set that lists the member would change with it.
            raise GitProjectError(
                f"Member {clargs.member} is defined with another url or "
                f"root. Edit the set file to change it."
            )
        if clargs.member in setfile.sets.get(clargs.set, []):
            raise GitProjectError(
                f"Set {clargs.set} already lists {clargs.member}"
            )

        config = pygit2.Config(tmp)
        # Names hold no regex characters, so the pattern matches no existing
        # value and libgit2 appends the new one.
        config.set_multivar(
            f"{ns}.set.{clargs.set}.repo",
            f"^{clargs.member}$",
            clargs.member,
        )
        if member is None:
            config[f"{ns}.repo.{clargs.member}.url"] = clargs.url
            config[f"{ns}.repo.{clargs.member}.root"] = clargs.root

    _edit_set_file(ns, edit)


def command_set_rm(git, gitproject, project, clargs):
    """Implement git-project set rm."""
    ns = project.get_section()
    _check_name("set", clargs.set)
    _check_name("member", clargs.member)

    def edit(setfile, tmp):
        repos = _get_set(setfile, clargs.set)
        if clargs.member not in repos:
            raise GitProjectError(
                f"Set {clargs.set} does not list {clargs.member}"
            )
        if repos == [clargs.member]:
            # libgit2 leaves an empty section header behind.
            result = subprocess.run(
                [
                    "git",
                    "config",
                    "--file",
                    tmp,
                    "--remove-section",
                    f"{ns}.set.{clargs.set}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.returncode != 0:
                raise GitProjectError(
                    f"Cannot remove set {clargs.set}: {result.stderr.strip()}"
                )
        else:
            pygit2.Config(tmp).delete_multivar(
                f"{ns}.set.{clargs.set}.repo", f"^{clargs.member}$"
            )

    _edit_set_file(ns, edit)


def command_set_clone(git, gitproject, project, clargs):
    """Implement git-project set clone."""
    _refuse_redirect_vars()
    _check_name("set", clargs.set)
    exe = _child_executable()
    setfile = _load(project.get_section())
    resolutions = _resolve_set(setfile, clargs.set, allow_missing=True)

    tasks = []
    done = []
    for resolution in resolutions:
        member = resolution.member
        if resolution.state == "ok":
            done.append((member.name, "already cloned"))
            continue
        # From /, so the child finds no repository to write project defaults
        # into.
        tasks.append(
            _Task(
                member.name,
                [
                    exe,
                    "clone",
                    "--worktree",
                    "--",
                    member.url,
                    str(member.path),
                ],
                os.sep,
            )
        )

    with _Cancel() as cancel:
        _run(tasks, None, cancel, capture=False)

    _print_summary(tasks, done)
    if cancel.cancelled:
        return cancel.exit_status()
    return 0 if all(task.ok() for task in tasks) else 1


class MultirepoPlugin(Plugin):
    """
    The multirepo command runs one command in every repository of a set.

    Summary::

      git <project> multirepo [-j <n>] [--skip-missing]
                              [--commit <member> <sha>]
                              <set> <command> [<arg>...]

    ``mr`` and ``multi`` are aliases for ``multirepo``. The ``set`` command
    defines the sets. For each member of <set>, in the order the set lists
    them, multirepo runs ``git <project> <command> <arg>...`` as a separate
    process, in the member's umbrella. The commands it runs are ``worktree
    add``, ``worktree rm``, ``worktree config``, ``branch status``, ``branch
    prune``, ``config`` and ``run``. It refuses any other command before
    anything runs.

    Before anything runs, the root of every member must be an umbrella whose
    ``origin`` url is the member's url, ignoring one trailing ``/`` and one
    trailing ``.git``. A member whose root does not exist stops the command,
    unless ``--skip-missing`` is given, which skips the member with a notice.
    A root that exists and is anything else always stops it. multirepo also
    refuses to run while GIT_DIR or a variable like it is set, since each of
    them points git somewhere other than the member's umbrella.

    For ``worktree add`` and ``worktree rm``, multirepo first runs the
    command with ``--check`` in every member. When any check fails, it
    prints each failure and runs nothing. Before that, ``worktree add`` is
    refused when two members would add a worktree at the same path, as
    ``../<name>`` does in umbrellas that share a directory. multirepo also
    passes ``--multirepo <set>`` to both commands. ``worktree add`` records <set> in the new
    worktree, and ``worktree rm`` refuses a worktree that was not added for
    <set>, so a worktree of the same name in another repository is left
    alone. In that removal a member keeps its branch unless the add created
    it. The <arg>s may not hold ``--check`` or ``--multirepo`` in any form.

    Every member runs, even after one fails, and nothing is rolled back. At
    the end a table gives each member's result. For a successful ``worktree
    add`` it gives the ``worktree rm`` that undoes it. For a failed one it
    says which of the branch, the record, the worktree and its path exist.
    The exit status is non-zero when any member failed.

    The members run one at a time by default, attached to the terminal,
    each after a ``== <member>`` line. ``-j <n>`` runs up to <n> of them at
    once, from 1 to 16. They get no standard input, and each one's output is
    printed under its ``== <member>`` line when it finishes. ``-j`` is refused for ``run``, and for
    ``branch prune`` without ``--no-ask``, since either may ask a question.

    A Ctrl-C reaches the running member directly. multirepo then starts no
    more members, prints the table and exits with a failure status. SIGTERM
    does the same, and multirepo also sends SIGTERM to the running member,
    then SIGKILL if it has not exited after five seconds. SIGHUP is treated
    as SIGTERM. With ``-j``, multirepo sends SIGINT for a Ctrl-C, and
    SIGTERM for SIGTERM or SIGHUP, to the process group of each running
    member. It sends SIGKILL to any group left after five seconds.

    ``--commit <member> <sha>`` lines the new worktrees up in time. It works
    only with ``worktree add`` and no <committish>. In <member> the new
    branch starts at <sha>. In each other member it starts at the first
    commit, following first parents back from the branch a plain ``worktree
    add`` would start from, whose author date is at or before <sha>'s.
    multirepo prints each member's commit. It refuses when <member> is not
    in <set> or was skipped, when any member has no such commit, and when the
    worktree's branch already exists at another commit, since ``worktree
    add`` would use that branch as it is.

    For example::

      git <project> set add tools git-project \\
          --url https://github.com/greened/git-project.git \\
          --root ~/projects/git-project
      git <project> set add tools git-project-core-plugins \\
          --url https://github.com/greened/git-project-core-plugins.git \\
          --root ~/projects/git-project-core-plugins
      git <project> set clone tools
      git <project> multirepo tools worktree add topic
      git <project> mr tools worktree rm topic

    See also::

      set
      worktree

    """

    def __init__(self):
        super().__init__("multirepo")

    def add_arguments(
        self, git, gitproject, project, parser_manager, plugin_manager
    ):
        """Add arguments for 'git-project multirepo.'"""
        multirepo_parser = add_top_level_command(
            parser_manager,
            "multirepo",
            "multirepo",
            aliases=["mr", "multi"],
            help="Run a command in every repository of a set",
        )

        add_plugin_version_argument(multirepo_parser)

        # It may run where there is no repository to write defaults to.
        multirepo_parser.set_defaults(
            func=command_multirepo, write_project_defaults=False
        )

        multirepo_parser.add_argument(
            "-j",
            "--jobs",
            type=_jobs,
            metavar="N",
            help=f"Run up to N members at once, from 1 to {_MAX_JOBS}",
        )
        multirepo_parser.add_argument(
            "--skip-missing",
            action="store_true",
            help="Skip a member whose root does not exist",
        )
        multirepo_parser.add_argument(
            "--commit",
            nargs=2,
            metavar=("MEMBER", "SHA"),
            help="For worktree add, start MEMBER at SHA and the rest at the "
            "same date",
        )
        multirepo_parser.add_argument("set", help="Set to run in")
        multirepo_parser.add_argument(
            "cmd",
            nargs=argparse.REMAINDER,
            metavar="command",
            help="Command and arguments to run in each member",
        )

    def modify_arguments(
        self, git, gitproject, project, parser_manager, plugin_manager
    ):
        """Give 'git-project multirepo' the worktree add parser."""
        multirepo_parser = parser_manager.find_parser("multirepo")
        # It reads worktree add's arguments the way the children will.
        multirepo_parser.set_defaults(
            worktree_add_parser=parser_manager.find_parser("worktree-add")
        )


class SetPlugin(Plugin):
    """
    The set command manages the sets of repositories that ``multirepo`` runs
    in.

    Summary::

      git <project> set list [<set>]
      git <project> set add <set> <member> [--url <url> --root <root>]
      git <project> set rm <set> <member>
      git <project> set clone <set>

    The sets live in a file of their own, in git config syntax, outside any
    repository, so a dotfiles repository can carry them between machines.
    ``<project>.set.file`` in the global git config names the file. It must
    have exactly one value, an absolute path that may start with ``~``, and
    the file must exist. The global config is the file GIT_CONFIG_GLOBAL
    names when that is set, and otherwise ``~/.gitconfig`` and the XDG
    ``git/config``. The sets are read from the set file alone, so the
    file may be included in the global config, but need not be. For
    ``git dev``::

      git config --global dev.set.file ~/dotfiles/git-sets
      touch ~/dotfiles/git-sets

    The set file holds two kinds of section. A member is a repository,
    defined once, and any number of sets may list it. A set runs its members
    in the order it lists them::

      [dev "repo.git-project"]
          url = https://github.com/greened/git-project.git
          root = ~/projects/git-project
      [dev "set.tools"]
          repo = git-project
          repo = git-project-core-plugins

    Set and member names are 1 to 64 letters, digits, ``_`` and ``-``, and
    start with a letter or digit. Each command checks the whole file before
    it does anything. It refuses a key not shown above, a member without
    exactly one url and one root, two members with the same root, a root
    that does not start with ``~/`` or that leaves the home directory, a url
    that is a relative path, and a set that lists a member twice or one that
    is not defined. It accepts ``<project>.set.file`` too, which the set
    file may hold when the global config includes it. A url is an absolute
    path, ``<scheme>://...`` or ``<host>:<path>``.

    ``set list`` prints each set, or only <set>, with each member's root and
    its state: ``ok`` for an umbrella cloned from the member's url,
    ``missing`` when the root does not exist, and otherwise why it is
    invalid.

    ``set add`` adds <member> to the end of <set>, making the set if needed.
    With ``--url`` and ``--root`` it also defines the member. A member that
    is already defined must be given its own url and root, or neither, so a
    member that other sets list never changes under them. To change a
    definition, edit the file. ``set rm`` removes <member> from <set> and
    keeps its definition. Removing a set's last member removes the set.

    ``set add`` and ``set rm`` lock ``<file>.multirepo-lock``, which they
    leave in place beside the set file, so two of them never lose each
    other's change. Each edits a copy of the file, checks it and then moves
    it over the file, so a failure leaves the file as it was. A symlink to
    the set file stays a symlink.

    ``set clone`` clones each member whose root does not exist, as ``clone
    --worktree <url> <root>`` does, one at a time. Like ``clone``, it offers
    no ssh key, so give a member it must clone an https url. A member whose
    root is already an umbrella cloned from its url is left alone. A root
    that exists and is anything else stops the command before anything is
    cloned, so a clone that failed partway is never taken for a finished
    one. A failed clone does not stop the rest. Ctrl-C, SIGTERM and SIGHUP
    work as they do for ``multirepo`` without ``-j``. At the end a table
    gives each member's result, and the exit status is non-zero when any
    clone failed.

    See also::

      clone
      multirepo

    """

    def __init__(self):
        super().__init__("set")

    def add_arguments(
        self, git, gitproject, project, parser_manager, plugin_manager
    ):
        """Add arguments for 'git-project set.'"""
        set_parser = add_top_level_command(
            parser_manager, "set", "set", help="Manage multirepo sets"
        )

        add_plugin_version_argument(set_parser)

        # Sets live outside every repository.
        set_parser.set_defaults(write_project_defaults=False)

        set_subparser = parser_manager.add_subparser(
            set_parser, "set-command", help="set commands"
        )

        list_parser = parser_manager.add_parser(
            set_subparser, "list", "set-list", help="List sets"
        )
        list_parser.set_defaults(
            func=command_set_list, write_project_defaults=False
        )
        list_parser.add_argument("set", nargs="?", help="Set to list")

        add_parser = parser_manager.add_parser(
            set_subparser, "add", "set-add", help="Add a member to a set"
        )
        add_parser.set_defaults(
            func=command_set_add, write_project_defaults=False
        )
        add_parser.add_argument("set", help="Set to add to")
        add_parser.add_argument("member", help="Member to add")
        add_parser.add_argument(
            "--url", help="Define the member with this url"
        )
        add_parser.add_argument(
            "--root", help="Define the member with this root, under ~/"
        )

        rm_parser = parser_manager.add_parser(
            set_subparser, "rm", "set-rm", help="Remove a member from a set"
        )
        rm_parser.set_defaults(
            func=command_set_rm, write_project_defaults=False
        )
        rm_parser.add_argument("set", help="Set to remove from")
        rm_parser.add_argument("member", help="Member to remove")

        clone_parser = parser_manager.add_parser(
            set_subparser,
            "clone",
            "set-clone",
            help="Clone the members of a set that are missing",
        )
        clone_parser.set_defaults(
            func=command_set_clone, write_project_defaults=False
        )
        clone_parser.add_argument("set", help="Set to clone")
