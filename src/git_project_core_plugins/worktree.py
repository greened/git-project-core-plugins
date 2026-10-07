#!/usr/bin/env python3
#
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
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.

# You should have received a copy of the GNU Affero General Public License along
# with git-project. If not, see <https://www.gnu.org/licenses/>.

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from git_project import (
    ConfigObject,
    GitProjectError,
    Plugin,
    Project,
    ScopedConfigObject,
    add_top_level_command,
    capture_command,
)

from git_project_core_plugins.common import add_plugin_version_argument


def normalize_path(git, path):
    """Find an appropriate repository-relative path. A relative path that does
    not start with '..' is placed under the current directory in a bare
    repository, and under the root of the current working copy otherwise. A
    path that starts with '..' is resolved from the current directory.

    path: A string path

    """
    path = Path(path).expanduser()

    if not path.is_absolute() and path.parts[0] != "..":
        # In a bare repository, put it under the current directory.
        # Otherwise put it under the root of the current working copy.
        if git.is_bare_repository():
            path = Path.cwd() / path
        else:
            path = Path(git.get_working_copy_root()) / path

    path = path.resolve()

    return str(path)


# Some source trees (i.e. go) don't work well with worktrees
# alongside a directory named ".git" so instead create a hidden
# directory that incorporates the last component of the url, with
# ",git" appended if necessary.
def get_hidden_gitdir_name(url: str):
    result = urllib.parse.urlparse(url)
    urlpath = Path(result.path)

    # If .git is the suffix, remove it.  If ".git" is the last
    # component, use the parent name.
    urlname = urlpath.name
    if urlname == ".git":
        urlname = urlpath.parent.name

    if not urlname.endswith(".git"):
        urlname += ".git"

    return "." + urlname


# Without this the container is not a repository, so anything
# that stands there and asks git a question gets nothing. It
# has to be a file. A symlink or a directory named ".git"
# brings back the go problem the hidden name avoids, because
# go's VCS search follows a ".git" that resolves to a
# directory and then runs "git status" against a bare clone.
# Go walks past a ".git" file, while git and pygit2 honour it.
def write_container_gitdir(container: Path, gitdir_name: str):
    # Keep the pointer relative so the container still moves.
    (container / ".git").write_text(f"gitdir: {gitdir_name}\n")


# Determine a path and committish from args.
def get_name_branch_path_and_refname(git, gp, clargs):
    """Given a Project and worktree command-line arguments <name-or-path> and
    <committish>, determine an appropriate worktree name, a branch for the
    worktree, a path based on the name and refname based on the name. The
    path is required. With no <committish>, the refname is HEAD's.

    """
    if not getattr(clargs, "path", None):
        raise GitProjectError("worktree add requires a path")

    name = str(Path(clargs.path).name)
    branch = name
    # If the path is not absolute, try creating a branch named as a subpath,
    # starting either from the top or after the last .. component.
    namepath = Path(clargs.path)
    if not namepath.is_absolute():
        parts = namepath.parts
        for i, v in enumerate(reversed(parts)):
            if v == "..":
                oi = len(parts) - i - 1
                namepath = Path(parts[oi + 1])
                for j in range(oi + 2, len(parts)):
                    namepath = namepath.joinpath(parts[j])
                break
        branch = str(namepath)
    path = normalize_path(git, clargs.path)
    refname = git.committish_to_refname("HEAD")
    if hasattr(clargs, "committish") and clargs.committish:
        # A committish may resolve to a commit with no ref (bare SHA);
        # committish_to_refname would fail there, so fall back to the
        # committish itself and let create_branch branch at that commit.
        ref = git.committish_to_ref(clargs.committish)
        refname = ref.name if ref is not None else clargs.committish

    return name, branch, path, refname


# worktree add
def command_worktree_add(git, gitproject, project, clargs):
    """Implement git-project worktree add."""
    name, newbranch, path, refname = get_name_branch_path_and_refname(
        git, gitproject, clargs
    )

    branch = git.refname_to_branch_name(refname)
    branch_point = refname

    if not git.committish_exists(branch_point):
        raise GitProjectError(
            f"Branch point {branch_point} does not exist for worktree add"
        )

    # Either use the branch the user gave us or create a branch (if needed)
    # named after the given name.
    if hasattr(clargs, "branch") and clargs.branch:
        branch = clargs.branch
        git.create_branch(branch, branch_point)
    elif newbranch != branch:
        branch = newbranch
        if not git.committish_exists(branch):
            git.create_branch(branch, branch_point)

    worktree = Worktree.get(git, project, name, path=path, committish=branch)
    worktree.add()

    return worktree


def command_worktree_rm(git, gitproject, project, clargs):
    """Implement git-project worktree rm."""
    name = clargs.name
    worktree = Worktree.get(git, project, name)

    # The merge check protects the branch's commits, so it applies only when we
    # are going to delete the branch.  --keep-branch leaves the branch in place
    # both locally and on remotes, so the merge state cannot cost anything.
    # --keep-remote-branch still deletes the local branch, so it still applies.
    if (
        not clargs.keep_branch
        and not project.branch_is_merged(worktree.committish)
        and not clargs.force
    ):
        raise GitProjectError(
            f"Worktree branch {worktree.committish} is not merged, use -f to force"
        )

    worktree.rm(
        keep_branch=clargs.keep_branch,
        keep_remote_branch=clargs.keep_remote_branch,
    )


class Worktree(ScopedConfigObject):
    """A ScopedConfigObject to manage worktree git configs."""

    class Path(ConfigObject):
        """A ConfigObject to manage worktree paths.  Each worktree config section has an
        associated worktreepath config section to allow fast mapping from a
        worktree path to its Worktree ConfigObject.

        """

        def __init__(self, git, project_section, subsection, ident, **kwargs):
            """Path construction.

            cls: The derived class being constructed.

            git: An object to query the repository and make config changes.

            project_section: git config section of the active project.

            subsection: An arbitrarily-long subsection appended to project_section

            ident: The name of this specific Build.

            **kwargs: Keyword arguments of property values to set upon construction.

            """
            super().__init__(git, project_section, subsection, ident, **kwargs)

        @classmethod
        def subsection(cls):
            """ConfigObject protocol subsection."""
            return "worktreepath"

        @classmethod
        def get(cls, git, project_section, path, **kwargs):
            """Factory to construct a worktree Path object.

            git: An object to query the repository and make config changes.

            project_section: git config section of the active project.

            path: The path to reference this Path..

            **kwargs: Keyword arguments of property values to set upon
                      construction.

            """
            return super().get(
                git, project_section, cls.subsection(), path, **kwargs
            )

    def __init__(self, git, project_section, subsection, ident, **kwargs):
        """Worktree construction.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project_section: git config section of the active project.

        subsection: An arbitrarily-long subsection appended to project_section

        ident: The name of this specific Build.

        **kwargs: Keyword arguments of property values to set upon construction.

        """
        super().__init__(git, project_section, subsection, ident, **kwargs)
        self._pathsection = self.Path.get(
            git, project_section, self.path, worktree=ident
        )

    @staticmethod
    def subsection():
        """ConfigObject protocol subsection."""
        return "worktree"

    @classmethod
    def get(cls, git, project, name, **kwargs):
        """Factory to construct Worktrees.

        cls: The derived class being constructed.

        git: An object to query the repository and make config changes.

        project: The currently active Project.

        name: Name of the worktree to construct.

        """
        worktree = super().get(
            git, project.get_section(), cls.subsection(), name, **kwargs
        )
        project.push_scope(worktree)
        return worktree

    @classmethod
    def get_managing_command(cls):
        return "worktree"

    @classmethod
    def get_by_path(cls, git, project, path):
        """Given a Project section and a path, get the associated Worktree."""
        pathsection = cls.Path.get(git, project.get_section(), path)
        if hasattr(pathsection, "worktree"):
            assert pathsection.worktree
            return cls.get(git, project, pathsection.worktree, path=path)
        return None

    def add(self):
        """Create a new worktree"""
        self._git.add_worktree(self.get_ident(), self.path, self.committish)

    def rm(self, keep_branch=False, keep_remote_branch=False):
        """Remove a worktree, deleting its workarea, builds and installs.

        keep_branch: If True, leave the worktree's branch alone, both locally
        and on any remotes.

        keep_remote_branch: If True, delete the local branch but leave it in
        place on every remote.  Implied by keep_branch.

        """
        # Read what the steps below need first, because removing the config
        # section also removes these attributes.
        path = self.path
        trees = [
            getattr(self, name, None)
            for name in ("builddir", "prefix", "installdir")
        ]
        ident = self.get_ident()
        committish = self.committish

        # Remove the config section first. An artifact hook on rm may refuse a
        # path, and it must do so before the workarea or branch is gone.
        super().rm()
        self._pathsection.rm()

        # Remove each tree on its own, so one that is missing or unset does not
        # leave the rest behind.
        for tree in [path, *trees]:
            if tree:
                shutil.rmtree(tree, ignore_errors=True)

        self._git.prune_worktree(ident)

        project = Project.get(self._git, self._project_section)

        if not keep_branch:
            for branch in project.iterbranches():
                if branch not in self._git.iterbranches():
                    continue
                branch_name = self._git.committish_to_refname(branch)
                committish_name = self._git.committish_to_refname(committish)
                if branch_name == committish_name:
                    break
            else:
                project.prune_branch(
                    committish, keep_remote_branch=keep_remote_branch
                )


# worktree migrate

_MIGRATE_MANIFEST = "git-project-migrate.json"

# Each of these points git somewhere other than the clone being migrated.
_GIT_REDIRECT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_NAMESPACE",
)

# Files and directories git leaves in a gitdir while an operation is under
# way. Moving a worktree in that state can strand the operation.
_IN_PROGRESS = (
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "rebase-merge",
    "rebase-apply",
    "sequencer",
)

_REFS_FORMAT = "--format=%(objectname) %(refname)"

# Long enough for a hook that sets up a virtualenv, short enough that a hung
# hook does not hold the terminal forever.
_POST_TIMEOUT = 600
# A day. Popen.wait overflows on a huge value, and that would only show
# after the migration.
_POST_TIMEOUT_MAX = 86400

# How long a hook has to exit after SIGTERM before it gets SIGKILL.
_POST_KILL_GRACE = 5


@dataclass
class _MigrateWorktree:
    old: Path
    new: Path
    branch: str
    name: str


@dataclass
class _MigratePlan:
    top: Path = Path()
    store_old: Path = Path()
    store_new: Path = Path()
    main: _MigrateWorktree | None = None
    main_entries: list[str] = field(default_factory=list)
    linked: list[_MigrateWorktree] = field(default_factory=list)
    # (key, new value, prior value or None)
    config_writes: list[tuple[str, str, str | None]] = field(
        default_factory=list
    )
    stale_config: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    ref_snapshot: list[str] = field(default_factory=list)
    core_bare: str | None = None
    head_oid: str = ""
    # A store already bare at <top>/.git, with its worktrees in <top>.
    bare_at_root: bool = False
    # (commondir file, its absolute value), each rewritten as ../..
    commondirs: list[tuple[Path, str]] = field(default_factory=list)
    # (branch, commits not on base or None when git cannot tell, base)
    unpushed: list[tuple[str, int | None, str]] = field(default_factory=list)
    post_key: str = ""
    post_hook: list[str] = field(default_factory=list)
    post_origin: str = ""
    post_timeout: int = _POST_TIMEOUT


def _git(*args):
    """Run git with an argument list, no shell, and return its output."""
    return capture_command(["git", *args], show_error=False).decode()


def _git_or_none(*args):
    """Like _git, but return None when git exits with an error."""
    try:
        return _git(*args)
    except Exception:
        return None


def _parse_worktree_list(output):
    """Parse ``git worktree list --porcelain -z``, one dict per worktree."""
    records = []
    record: dict[str, str] = {}
    for item in output.split("\0"):
        if not item:
            if record:
                records.append(record)
            record = {}
            continue
        key, _, value = item.partition(" ")
        record[key] = value
    if record:
        records.append(record)
    return records


def _migrate_dir_name(branch):
    return branch.replace("/", "-")


def _status(path):
    """Return the porcelain status of the worktree at path, or None when git
    fails. The precheck and verify share it, so both agree on clean.

    """
    return _git_or_none(
        "-C",
        str(path),
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )


def _status_paths(status):
    """Return the paths in ``git status --porcelain=v1 -z`` output."""
    paths = []
    entries = iter(status.split("\0"))
    for entry in entries:
        if not entry:
            continue
        paths.append(entry[3:])
        # A rename or copy, in the index or the worktree, is followed by its
        # source path.
        if "R" in entry[:2] or "C" in entry[:2]:
            next(entries, None)
    return paths


def _check_worktree(plan, path, record, top, inside_top=False):
    """Add a refusal for each reason the worktree at path cannot migrate. With
    inside_top, the worktree stays where it is and must be inside top.

    """
    refusals = plan.refusals
    if "locked" in record:
        refusals.append(f"{path} is locked")
    if "prunable" in record:
        refusals.append(f"{path} is prunable")
    if not path.is_dir():
        refusals.append(f"{path} is missing")
        return
    if "branch" not in record:
        refusals.append(f"{path} has a detached HEAD")

    status = _status(path)
    if status is None:
        refusals.append(f"{path}: cannot read git status")
    elif status:
        refusals.append(f"{path} has uncommitted changes or untracked files")

    gitdir = _git_or_none("-C", str(path), "rev-parse", "--absolute-git-dir")
    if gitdir is None:
        refusals.append(f"{path}: cannot find its git directory")
    else:
        gitdir_path = Path(gitdir.strip())
        for name in _IN_PROGRESS:
            if os.path.lexists(gitdir_path / name):
                refusals.append(
                    f"{path} has {name}, finish or abort that operation first"
                )
        # It would keep naming the old path. The main worktree's file is
        # checked with the store's config.
        config_worktree = gitdir_path / "config.worktree"
        if path != top and config_worktree.is_file():
            if _git_or_none(
                "config", "-f", str(config_worktree), "core.worktree"
            ):
                refusals.append(f"{config_worktree} sets core.worktree")

    if os.path.lexists(path / ".gitmodules"):
        refusals.append(f"{path} has submodules")
    if inside_top:
        # Nothing moves and no index is reset, so these checks below do not
        # apply.
        if not path.is_relative_to(top):
            refusals.append(f"{path} is outside {top}")
        return

    sparse = _git_or_none(
        "-C", str(path), "config", "--bool", "core.sparseCheckout"
    )
    if sparse is not None and sparse.strip() == "true":
        refusals.append(f"{path} has a sparse checkout")
    # The index reset in the new main worktree drops these bits.
    tags = _git_or_none("-C", str(path), "ls-files", "-v", "-z")
    if tags is None:
        refusals.append(f"{path}: cannot list the index")
    elif any(
        item[:1].islower() or item[:1] == "S" for item in tags.split("\0")
    ):
        refusals.append(f"{path} has assume-unchanged or skip-worktree files")

    if path != top:
        if path.is_relative_to(top):
            refusals.append(f"{path} is inside {top}")
        if path.stat().st_dev != top.stat().st_dev:
            refusals.append(f"{path} is on a different filesystem from {top}")


def _plan_store_new(plan, ns, gitdir_args):
    """Name the new store for the project remote. Return False on a refusal
    that stops the plan.

    """
    top = plan.top
    remotes = _git_or_none(*gitdir_args, "config", "--get-all", f"{ns}.remote")
    remote = remotes.splitlines()[0].strip() if remotes else "origin"
    # The url can hold a credential, so it is never printed or stored.
    url = _git_or_none(*gitdir_args, "config", "--get", f"remote.{remote}.url")
    if not url or not url.strip():
        plan.refusals.append(f"remote {remote} has no url")
        return False
    store_name = get_hidden_gitdir_name(url.strip())
    store_new = top / store_name
    if store_name in (".", "..", ".git") or store_new.resolve().parent != top:
        plan.refusals.append(
            f"remote {remote} gives an unusable directory name"
        )
        return False
    plan.store_new = store_new
    if os.path.lexists(store_new):
        plan.refusals.append(f"{store_new} already exists")
    return True


def _plan_bare_at_root(git, project, plan, gitdir_args):
    """Plan the rename of a store already bare at <top>/.git. No worktree
    moves, so no worktree config changes.

    """
    top = plan.top
    store_old = plan.store_old
    records = _parse_worktree_list(
        _git(*gitdir_args, "worktree", "list", "--porcelain", "-z")
    )
    # git lists a bare store named .git as its parent directory.
    if (
        not records
        or Path(records[0]["worktree"]).resolve() not in (store_old, top)
        or "bare" not in records[0]
    ):
        plan.refusals.append(f"{store_old} is not listed as bare")
        return
    if len(records) == 1:
        plan.refusals.append(f"{store_old} has no worktrees")
        return
    # A store with core.bare set by hand can still have a checkout in top,
    # which nothing here would carry over.
    if (store_old / "index").exists():
        plan.refusals.append(f"{store_old} has an index")
    # Walk each directory from top down to each worktree. Anything there
    # that is not a dotfile or on the way to a worktree could be a checkout.
    paths = {Path(record["worktree"]).resolve() for record in records[1:]}
    on_path = set()
    for path in paths:
        if path.is_relative_to(top) and not path.is_relative_to(store_old):
            on_path.add(path)
            on_path.update(path.parents)
    for directory in sorted(on_path - paths):
        if not directory.is_relative_to(top):
            continue
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            plan.refusals.append(f"cannot read {directory}")
            continue
        for entry in entries:
            if not entry.startswith(".") and directory / entry not in on_path:
                plan.refusals.append(f"{directory / entry} is not a worktree")

    admin_root = store_old / "worktrees"
    for record in records[1:]:
        path = Path(record["worktree"]).resolve()
        # The rename would carry it into the new store.
        if path.is_relative_to(store_old):
            plan.refusals.append(f"{path} is inside {store_old}")
            continue
        _check_worktree(plan, path, record, top, inside_top=True)
        branch = git.refname_to_branch_name(record.get("branch", ""))
        plan.linked.append(_MigrateWorktree(path, path, branch, path.name))

        gitdir = _git_or_none(
            "-C", str(path), "rev-parse", "--absolute-git-dir"
        )
        if gitdir is None:
            continue
        admin = Path(gitdir.strip()).resolve()
        if admin.parent != admin_root:
            plan.refusals.append(f"{path}: {admin} is not in {admin_root}")
            continue
        # The repair rewrites only the two gitdir links. An absolute
        # commondir keeps naming the old store, which is gone after the rename.
        commondir = admin / "commondir"
        try:
            value = commondir.read_text().strip()
        except OSError:
            plan.refusals.append(f"{path}: cannot read {commondir}")
            continue
        target = Path(value)
        if not target.is_absolute():
            target = admin / target
        if target.resolve() != store_old:
            plan.refusals.append(f"{commondir} names another repository")
        elif Path(value).is_absolute():
            plan.commondirs.append((commondir, value))

    if not _plan_store_new(plan, project.get_section(), gitdir_args):
        return

    plan.ref_snapshot = sorted(
        _git(*gitdir_args, "for-each-ref", _REFS_FORMAT).splitlines()
    )


def _find_unpushed(plan, gitdir_args, main_branch):
    """Record each local branch with commits that its upstream lacks. A branch
    with no upstream, or one that is gone, is compared with the main branch.
    When main_branch is None, such a branch is skipped.

    """
    heads = _git_or_none(
        *gitdir_args,
        "for-each-ref",
        # Not :short, which gives heads/<name> when a tag has the same name.
        "--format=%(refname)%00%(refname:lstrip=2)%00%(upstream)"
        "%00%(upstream:lstrip=2)",
        "refs/heads",
    )
    for line in (heads or "").splitlines():
        refname, branch, upstream, upstream_short = line.split("\0")
        if upstream and (
            _git_or_none(
                *gitdir_args, "rev-parse", "--verify", "--quiet", upstream
            )
            is not None
        ):
            base, base_short = upstream, upstream_short
        elif main_branch is None or branch == main_branch:
            continue
        else:
            base, base_short = f"refs/heads/{main_branch}", main_branch
        # A "-" line is a commit the base has under another id, as after a
        # rebase or cherry-pick, so only "+" lines count.
        cherry = _git_or_none(*gitdir_args, "cherry", base, refname)
        count = (
            None
            if cherry is None
            else sum(entry.startswith("+") for entry in cherry.splitlines())
        )
        if count != 0:
            plan.unpushed.append((branch, count, base_short))


def _find_main_branch(git, ns, gitdir_args):
    """Return the main branch, or None when there is none."""
    main_branch = None
    for value in (
        _git_or_none(*gitdir_args, "config", "--get-all", f"{ns}.branch") or ""
    ).splitlines():
        branch = git.refname_to_branch_name(value.strip())
        if (
            _git_or_none(
                *gitdir_args,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            )
            is not None
        ):
            main_branch = branch
            break
    if main_branch is None:
        refname = git.get_main_branch()
        if refname:
            main_branch = git.refname_to_branch_name(refname)
    return main_branch


def _plan_unpushed_and_hook(plan, ns, gitdir_args, main_branch):
    """List unpushed branches and plan the hook, for either form."""
    _find_unpushed(plan, gitdir_args, main_branch)

    # A key on the project section, outside the sections that worktrees and
    # run objects own. A run alias named postmigrate would share it.
    plan.post_key = f"{ns}.postmigrate"
    hook = _git_or_none(*gitdir_args, "config", "--get", plan.post_key)
    if hook is not None:
        origin = _git_or_none(
            *gitdir_args, "config", "--show-origin", "--get", plan.post_key
        )
        plan.post_origin = (origin or "").partition("\t")[0]
        # Refuse now, while nothing has changed, rather than migrate and then
        # fail to run the hook.
        try:
            plan.post_hook = shlex.split(hook)
        except ValueError:
            plan.refusals.append(f"{plan.post_key} is not a valid command")
        else:
            if not plan.post_hook:
                plan.refusals.append(f"{plan.post_key} is empty")
    timeout_key = f"{ns}.postmigratetimeout"
    timeout = _git_or_none(*gitdir_args, "config", "--get", timeout_key)
    if timeout is not None:
        if (
            re.fullmatch(r"[0-9]+", timeout.strip())
            and 0 < int(timeout) <= _POST_TIMEOUT_MAX
        ):
            plan.post_timeout = int(timeout)
        else:
            plan.refusals.append(
                f"{timeout_key} is not a whole number of seconds from 1 to "
                f"{_POST_TIMEOUT_MAX}"
            )


def _plan_migration(git, project):
    """Work out every step of a migration without changing anything. Collect
    every reason to refuse that it finds. Some basic checks stop early.

    """
    plan = _MigratePlan()

    for var in _GIT_REDIRECT_VARS:
        if var in os.environ:
            plan.refusals.append(f"{var} is set")
    if plan.refusals:
        return plan

    version = re.search(r"(\d+)\.(\d+)", _git("version"))
    if not version or (int(version[1]), int(version[2])) < (2, 36):
        plan.refusals.append("git 2.36 or later is required")
        return plan

    common = _git_or_none(
        "-C",
        os.getcwd(),
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
    )
    if common is None:
        plan.refusals.append("not in a git repository")
        return plan
    store_old = Path(common.strip()).resolve()
    top = store_old.parent
    bare = _git_or_none(
        "--git-dir", str(store_old), "config", "--bool", "core.bare"
    )
    if store_old.name != ".git" or not store_old.is_dir():
        plan.refusals.append("already converted or not a main clone")
        return plan
    plan.top = top
    plan.store_old = store_old
    plan.core_bare = bare.strip() if bare is not None else None
    plan.bare_at_root = plan.core_bare == "true"
    gitdir_args = ("--git-dir", str(store_old))

    # Either would keep the store non-bare after the migration sets core.bare.
    config = store_old / "config"
    if _git_or_none("config", "-f", str(config), "core.worktree"):
        plan.refusals.append(f"{config} sets core.worktree")
    config_worktree = store_old / "config.worktree"
    if config_worktree.is_file():
        for key in ("core.bare", "core.worktree"):
            # git sparse-checkout moves core.bare here, which is what makes
            # a bare store bare.
            if key == "core.bare" and plan.bare_at_root:
                continue
            if _git_or_none("config", "-f", str(config_worktree), key):
                plan.refusals.append(f"{config_worktree} sets {key}")
    # The repair writes absolute links, which would silently drop the mode.
    for key in ("extensions.relativeWorktrees", "worktree.useRelativePaths"):
        value = _git_or_none(*gitdir_args, "config", "--get", key)
        if value is None:
            continue
        flag = _git_or_none(*gitdir_args, "config", "--bool", "--get", key)
        if flag is None:
            plan.refusals.append(f"{key} is not a boolean")
        elif flag.strip() != "false":
            plan.refusals.append(f"{key} is true")

    if plan.bare_at_root:
        _plan_bare_at_root(git, project, plan, gitdir_args)
        # A bare store needs no main branch, so a missing one is no refusal.
        ns = project.get_section()
        main_branch = _find_main_branch(git, ns, gitdir_args)
        _plan_unpushed_and_hook(plan, ns, gitdir_args, main_branch)
        return plan

    records = _parse_worktree_list(
        _git("-C", str(top), "worktree", "list", "--porcelain", "-z")
    )
    if not records or Path(records[0]["worktree"]).resolve() != top:
        plan.refusals.append(f"{top} is not the main worktree")
        return plan
    for record in records:
        _check_worktree(plan, Path(record["worktree"]).resolve(), record, top)

    ns = project.get_section()

    main_branch = _find_main_branch(git, ns, gitdir_args)
    if main_branch is None:
        plan.refusals.append("cannot determine the main branch")
        return plan
    _plan_unpushed_and_hook(plan, ns, gitdir_args, main_branch)

    main_ref = records[0].get("branch")
    if main_ref is not None and main_ref != f"refs/heads/{main_branch}":
        plan.refusals.append(
            f"main clone has {git.refname_to_branch_name(main_ref)} "
            f"checked out, not {main_branch}"
        )

    if not _plan_store_new(plan, ns, gitdir_args):
        return plan
    store_name = plan.store_new.name

    worktrees = [(top, main_branch, _migrate_dir_name(main_branch))]
    prefix = f"{top.name}-"
    for record in records[1:]:
        path = Path(record["worktree"]).resolve()
        branch = git.refname_to_branch_name(record.get("branch", ""))
        if path.name.startswith(prefix) and len(path.name) > len(prefix):
            dirname = path.name[len(prefix) :]
        else:
            dirname = _migrate_dir_name(branch)
        worktrees.append((path, branch, dirname))

    dirnames: set[str] = set()
    names: set[str] = set()
    for old, branch, dirname in worktrees:
        new = top / dirname
        if (
            not dirname
            or dirname in (".", "..", ".git", store_name)
            or "/" in dirname
            or new.resolve().parent != top
        ):
            plan.refusals.append(
                f"cannot use {dirname!r} as the directory for {old}"
            )
            continue
        if dirname in dirnames:
            plan.refusals.append(f"{new} is the target of two worktrees")
        dirnames.add(dirname)
        if os.path.lexists(new):
            plan.refusals.append(f"{new} already exists")

        pathsection = f"{ns}.worktreepath.{old}"
        name = git.config.get_item(pathsection, "worktree")
        if name:
            plan.stale_config.append(f"{pathsection}.worktree")
        else:
            name = dirname
        if name in names:
            plan.refusals.append(f"worktree name {name} is used twice")
        names.add(name)
        section = f"{ns}.worktree.{name}"
        prior_path = git.config.get_item(section, "path")
        if prior_path is not None and Path(prior_path).resolve() != old:
            plan.refusals.append(
                f"{section}.path already names another worktree"
            )
        newsection = f"{ns}.worktreepath.{new}"
        plan.config_writes += [
            (f"{section}.path", str(new), prior_path),
            (
                f"{section}.committish",
                branch,
                git.config.get_item(section, "committish"),
            ),
            (
                f"{newsection}.worktree",
                name,
                git.config.get_item(newsection, "worktree"),
            ),
        ]

        worktree = _MigrateWorktree(old, new, branch, name)
        if old == top:
            plan.main = worktree
        else:
            plan.linked.append(worktree)

    if plan.main is None:
        return plan

    plan.main_entries = sorted(set(os.listdir(top)) - {".git"})
    top_dev = top.stat().st_dev
    for entry in plan.main_entries:
        if os.lstat(top / entry).st_dev != top_dev:
            plan.refusals.append(f"{top / entry} is a mount point")

    # A value naming an old path keeps naming it after the move. Report the
    # key only, since a value may hold a credential. Match whole paths, also
    # after a flag such as -I, so /x/proj does not match /x/proj-topic or
    # /y/x/proj.
    olds = [
        (
            str(old),
            re.compile(
                r"(?:(?<![^\s:;,=\"'])|(?<=(?<![^\s:;,=\"'])-[A-Za-z]))"
                + re.escape(str(old))
                + r"(?![^/\s:;,=)\"'])"
            ),
        )
        for old, _, _ in worktrees
    ]
    lowns = ns.lower()
    config_list = _git_or_none(*gitdir_args, "config", "--local", "-z", "-l")
    for item in (config_list or "").split("\0"):
        key, _, value = item.partition("\n")
        lowkey = key.lower()
        # Migrate rewrites these or reports them as stale.
        if (
            not lowkey.startswith(f"{lowns}.")
            or lowkey.startswith(f"{lowns}.worktreepath.")
            or (
                lowkey.startswith(f"{lowns}.worktree.")
                and lowkey.endswith(".path")
            )
        ):
            continue
        for old, pattern in olds:
            if pattern.search(value):
                plan.warnings.append(f"{key} holds the old path {old}")
                break

    plan.ref_snapshot = sorted(
        _git(*gitdir_args, "for-each-ref", _REFS_FORMAT).splitlines()
    )
    plan.head_oid = _git(*gitdir_args, "rev-parse", "HEAD").strip()

    return plan


def _plan_steps(plan, main):
    """Return the steps of a plan as printable lines."""
    top = plan.top
    lines = [f"write {plan.store_old / _MIGRATE_MANIFEST}"]
    for worktree in plan.linked:
        lines.append(
            shlex.join(
                [
                    "git",
                    "-C",
                    str(top),
                    "worktree",
                    "move",
                    str(worktree.old),
                    str(worktree.new),
                ]
            )
        )
    lines.append(
        shlex.join(
            [
                "git",
                "-C",
                str(top),
                "worktree",
                "add",
                "--force",
                "--no-checkout",
                str(main.new),
                main.branch,
            ]
        )
    )
    for name in ("config.worktree", "logs/HEAD"):
        if (plan.store_old / name).is_file():
            lines.append(
                f"copy {plan.store_old / name} -> "
                f"the git directory of {main.new}"
            )
    for entry in plan.main_entries:
        lines.append(f"rename {top / entry} -> {main.new / entry}")
    lines.append(shlex.join(["git", "-C", str(main.new), "reset", "-q"]))
    gitdir = f"--git-dir={plan.store_old}"
    lines.append(shlex.join(["git", gitdir, "config", "core.bare", "true"]))
    lines.append(
        shlex.join(
            [
                "git",
                gitdir,
                "update-ref",
                "--no-deref",
                "-m",
                "worktree migrate",
                "HEAD",
                plan.head_oid,
            ]
        )
    )
    lines.append(f"rename {plan.store_old} -> {plan.store_new}")
    lines.append(f"write {top / '.git'}: gitdir: {plan.store_new.name}")
    lines.append(
        shlex.join(
            [
                "git",
                f"--git-dir={plan.store_new}",
                "worktree",
                "repair",
                str(main.new),
                *[str(worktree.new) for worktree in plan.linked],
            ]
        )
    )
    for key, value, _ in plan.config_writes:
        lines.append(f"set {key} = {value}")
    return lines + _post_step(plan)


def _post_step(plan):
    # The key and not the command, which may hold a credential.
    if not plan.post_hook:
        return []
    origin = f" from {plan.post_origin}" if plan.post_origin else ""
    return [f"run the command in {plan.post_key}{origin}, in {plan.top}"]


def _bare_plan_steps(plan):
    """Return the steps of a bare-at-root plan as printable lines."""
    lines = [f"write {plan.store_old / _MIGRATE_MANIFEST}"]
    for commondir, _ in plan.commondirs:
        lines.append(f"write {commondir}: ../..")
    lines.append(f"rename {plan.store_old} -> {plan.store_new}")
    lines.append(f"write {plan.top / '.git'}: gitdir: {plan.store_new.name}")
    lines.append(
        shlex.join(
            [
                "git",
                f"--git-dir={plan.store_new}",
                "worktree",
                "repair",
                *[str(worktree.new) for worktree in plan.linked],
            ]
        )
    )
    return lines + _post_step(plan)


def _print_plan(plan):
    if plan.bare_at_root:
        if not plan.refusals:
            for line in _bare_plan_steps(plan):
                print(line)
    elif plan.main is not None:
        for line in _plan_steps(plan, plan.main):
            print(line)
    for branch, count, base in plan.unpushed:
        if count is None:
            print(f"unpushed: cannot compare {branch} with {base}")
        else:
            commits = "commit" if count == 1 else "commits"
            print(f"unpushed: {branch} has {count} {commits} not on {base}")
    for key in plan.stale_config:
        print(f"stale: {key} names an old path and is left in place")
    for warning in plan.warnings:
        print(f"warn: {warning}")
    for refusal in plan.refusals:
        print(f"refuse: {refusal}")


def _write_manifest(path, manifest):
    """Replace the manifest at path in one step, never half written."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as file:
        file.write(json.dumps(manifest, indent=2) + "\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(tmp, path)


def _worktree_record(worktree):
    return {
        "old": str(worktree.old),
        "new": str(worktree.new),
        "branch": worktree.branch,
        "name": worktree.name,
    }


_DIRTY_PATHS_SHOWN = 10


def _verify(plan, worktrees):
    """Raise GitProjectError unless the migrated layout matches the plan."""
    store = str(plan.store_new)
    problems = []

    bare = _git_or_none(
        "--git-dir", store, "rev-parse", "--is-bare-repository"
    )
    if bare is None or bare.strip() != "true":
        problems.append(f"{store} is not bare")

    records = _parse_worktree_list(
        _git("--git-dir", store, "worktree", "list", "--porcelain", "-z")
    )
    found = {
        Path(record["worktree"]).resolve(): record.get("branch")
        for record in records
    }
    expected: dict[Path, str | None] = {plan.store_new: None}
    for worktree in worktrees:
        expected[worktree.new] = f"refs/heads/{worktree.branch}"
    if found != expected:
        problems.append("the worktree list does not match the plan")

    for worktree in worktrees:
        status = _status(worktree.new)
        if status is None:
            problems.append(f"{worktree.new}: cannot read git status")
        elif status:
            paths = _status_paths(status)
            shown = ", ".join(paths[:_DIRTY_PATHS_SHOWN])
            if len(paths) > _DIRTY_PATHS_SHOWN:
                shown += f" and {len(paths) - _DIRTY_PATHS_SHOWN} more"
            problems.append(f"{worktree.new} is not clean: {shown}")

    refs = sorted(
        _git("--git-dir", store, "for-each-ref", _REFS_FORMAT).splitlines()
    )
    if refs != plan.ref_snapshot:
        problems.append("the refs changed")

    if problems:
        raise GitProjectError("verify failed: " + "; ".join(problems))


def _apply(plan, main, git, project):
    """Carry out a plan, journaling each step into the manifest. Stop at the
    first failure.

    """
    top = plan.top
    store_new = plan.store_new
    worktrees = [main, *plan.linked]
    manifest_path = plan.store_old / _MIGRATE_MANIFEST
    manifest: dict = {
        "version": 1,
        "top": str(top),
        "store_old": str(plan.store_old),
        "store_new": str(store_new),
        "core_bare": plan.core_bare,
        "head_ref": f"refs/heads/{main.branch}",
        "head_oid": plan.head_oid,
        "main": _worktree_record(main),
        "linked": [_worktree_record(worktree) for worktree in plan.linked],
        "main_entries": plan.main_entries,
        "config_writes": [
            {"key": key, "value": value, "prior": prior}
            for key, value, prior in plan.config_writes
        ],
        "current_step": None,
        "steps_done": [],
        "complete": False,
    }

    # Journal a step before it runs, so a hard stop still names the step
    # that may be half done.
    def start(step):
        manifest["current_step"] = step
        _write_manifest(manifest_path, manifest)

    def done(step):
        manifest["steps_done"].append(step)
        manifest["current_step"] = None
        _write_manifest(manifest_path, manifest)

    step = "manifest"
    # BaseException, so a Ctrl-C mid-step still records where it stopped.
    try:
        _write_manifest(manifest_path, manifest)

        for worktree in plan.linked:
            step = f"move_linked {worktree.new.name}"
            start(step)
            _git(
                "-C",
                str(top),
                "worktree",
                "move",
                str(worktree.old),
                str(worktree.new),
            )
            done(step)

        step = "add_main"
        start(step)
        _git(
            "-C",
            str(top),
            "worktree",
            "add",
            "--force",
            "--no-checkout",
            str(main.new),
            main.branch,
        )
        done(step)

        step = "copy_main_state"
        start(step)
        admin = Path(
            _git(
                "-C", str(main.new), "rev-parse", "--absolute-git-dir"
            ).strip()
        )
        # The main worktree's own config and HEAD reflog live in the store,
        # which is about to become bare. Carry them to the new worktree.
        if (plan.store_old / "config.worktree").is_file():
            shutil.copy2(
                plan.store_old / "config.worktree", admin / "config.worktree"
            )
        if (plan.store_old / "logs" / "HEAD").is_file():
            (admin / "logs").mkdir(exist_ok=True)
            shutil.copy2(
                plan.store_old / "logs" / "HEAD", admin / "logs" / "HEAD"
            )
        done(step)

        for entry in plan.main_entries:
            step = f"move_entry {entry}"
            start(step)
            os.rename(top / entry, main.new / entry)
            done(step)

        step = "reset_index"
        start(step)
        _git("-C", str(main.new), "reset", "-q")
        done(step)

        gitdir = f"--git-dir={plan.store_old}"
        step = "set_bare"
        start(step)
        _git(gitdir, "config", "core.bare", "true")
        done(step)

        step = "detach_head"
        start(step)
        _git(
            gitdir,
            "update-ref",
            "--no-deref",
            "-m",
            "worktree migrate",
            "HEAD",
            plan.head_oid,
        )
        done(step)

        step = "rename_store"
        start(step)
        # Set first, so a stop after the rename still finds the manifest.
        manifest_path = store_new / _MIGRATE_MANIFEST
        os.rename(plan.store_old, store_new)
        done(step)

        step = "write_pointer"
        start(step)
        write_container_gitdir(top, store_new.name)
        done(step)

        # repair finds each admin dir by the name in the worktree's .git
        # file. _verify catches a worktree it could not reconnect.
        step = "repair"
        start(step)
        _git(
            "--git-dir",
            str(store_new),
            "worktree",
            "repair",
            *[str(worktree.new) for worktree in worktrees],
        )
        done(step)

        step = "write_config"
        start(step)
        git.reinit(store_new)
        git.validate_config()
        section = project.get_section()
        for worktree in worktrees:
            # A fresh Project each time, so each worktree scopes only itself.
            Worktree.get(
                git,
                Project.get(git, section),
                worktree.name,
                path=str(worktree.new),
                committish=worktree.branch,
            )
        done(step)

        step = "verify"
        start(step)
        _verify(plan, worktrees)
        manifest["complete"] = True
        done(step)
    except BaseException as exception:
        message = _record_failure(
            plan, manifest, manifest_path, step, exception
        )
        if not isinstance(exception, Exception):
            print(message)
            raise
        raise GitProjectError(message) from exception


def _record_failure(plan, manifest, manifest_path, step, exception):
    """Journal the failed step and return an error message that names the
    manifest.

    """
    manifest["failed_step"] = step
    manifest["error"] = str(exception)
    if not manifest_path.parent.is_dir():
        # The stop came inside rename_store, before the rename.
        manifest_path = plan.store_old / _MIGRATE_MANIFEST
    try:
        _write_manifest(manifest_path, manifest)
    except OSError:
        pass
    steps = ", ".join(manifest["steps_done"]) or "none"
    reason = f": {exception}" if str(exception) else ""
    message = (
        f"worktree migrate failed at step {step}{reason}. "
        f"Steps done: {steps}. "
        f"The manifest is {manifest_path}. To undo the steps done, see "
        "Manual rollback in the worktree help."
    )
    return message


def _apply_bare_at_root(plan, git):
    """Carry out a bare-at-root plan, journaling each step into the
    manifest. Stop at the first failure.

    """
    store_new = plan.store_new
    manifest_path = plan.store_old / _MIGRATE_MANIFEST
    manifest: dict = {
        "version": 1,
        "form": "bare_at_root",
        "top": str(plan.top),
        "store_old": str(plan.store_old),
        "store_new": str(store_new),
        "linked": [_worktree_record(worktree) for worktree in plan.linked],
        "commondirs": [
            {"path": str(path), "prior": prior}
            for path, prior in plan.commondirs
        ],
        "current_step": None,
        "steps_done": [],
        "complete": False,
    }

    def start(step):
        manifest["current_step"] = step
        _write_manifest(manifest_path, manifest)

    def done(step):
        manifest["steps_done"].append(step)
        manifest["current_step"] = None
        _write_manifest(manifest_path, manifest)

    step = "manifest"
    try:
        _write_manifest(manifest_path, manifest)

        # ../.. names the store before and after the rename, so these
        # need no undo.
        for commondir, _ in plan.commondirs:
            step = f"rewrite_commondir {commondir.parent.name}"
            start(step)
            tmp = commondir.with_name(commondir.name + ".tmp")
            try:
                tmp.write_text("../..\n")
                os.replace(tmp, commondir)
            finally:
                tmp.unlink(missing_ok=True)
            done(step)

        step = "rename_store"
        start(step)
        # Set first, so a stop after the rename still finds the manifest.
        manifest_path = store_new / _MIGRATE_MANIFEST
        os.rename(plan.store_old, store_new)
        done(step)

        step = "write_pointer"
        start(step)
        write_container_gitdir(plan.top, store_new.name)
        done(step)

        step = "repair"
        start(step)
        _git(
            "--git-dir",
            str(store_new),
            "worktree",
            "repair",
            *[str(worktree.new) for worktree in plan.linked],
        )
        # git-project checks the config after the command, and the old
        # path is gone.
        git.reinit(store_new)
        done(step)

        step = "verify"
        start(step)
        _verify(plan, plan.linked)
        manifest["complete"] = True
        done(step)
    except BaseException as exception:
        message = _record_failure(
            plan, manifest, manifest_path, step, exception
        )
        if not isinstance(exception, Exception):
            print(message)
            raise
        raise GitProjectError(message) from exception


def _kill_post_hook(process):
    """Stop the hook's process group: SIGTERM, a grace period, then SIGKILL."""
    deadline = time.monotonic() + _POST_KILL_GRACE
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=_POST_KILL_GRACE)
        # The leader is gone, but the rest of the group gets the same grace.
        while time.monotonic() < deadline:
            os.killpg(process.pid, 0)
            time.sleep(0.05)
    # A second Ctrl-C cuts the grace short. It must not skip the SIGKILL.
    except (ProcessLookupError, subprocess.TimeoutExpired, KeyboardInterrupt):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _run_post_hook(plan):
    """Run the post-migration command in <top>. Return None on success, and
    otherwise what went wrong.

    """
    try:
        # No stdin, so a hook that prompts fails rather than waits for the
        # timeout. Its own session, so a kill reaches its children too.
        process = subprocess.Popen(
            plan.post_hook,
            cwd=plan.top,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exception:
        return f"could not start: {exception.strerror}"
    try:
        returncode = process.wait(timeout=plan.post_timeout)
    except subprocess.TimeoutExpired:
        _kill_post_hook(process)
        return f"timed out after {plan.post_timeout} seconds"
    except KeyboardInterrupt:
        # The terminal's Ctrl-C does not reach the hook's session.
        _kill_post_hook(process)
        return "was interrupted"
    if returncode < 0:
        return f"was killed by signal {-returncode}"
    if returncode != 0:
        return f"failed with status {returncode}"
    return None


def command_worktree_migrate(git, gitproject, project, clargs):
    """Implement git-project worktree migrate."""
    plan = _plan_migration(git, project)
    _print_plan(plan)

    if plan.refusals:
        raise GitProjectError(
            "worktree migrate refused: " + "; ".join(plan.refusals)
        )

    if not clargs.apply:
        ns = project.get_section()
        print(
            "Dry run, the migration changed nothing. git-project itself may "
            f"have set {ns}.branch and {ns}.remote, if they were unset. Run "
            "with --apply to migrate."
        )
        return 0

    if plan.bare_at_root:
        _apply_bare_at_root(plan, git)
    elif plan.main is None:
        raise GitProjectError("worktree migrate found no main worktree")
    else:
        _apply(plan, plan.main, git, project)
    # Flush, so the hook's output follows this line.
    print(
        f"Migrated {plan.top}. The manifest is in {plan.store_new}.",
        flush=True,
    )
    if plan.post_hook:
        error = _run_post_hook(plan)
        manifest_path = plan.store_new / _MIGRATE_MANIFEST
        try:
            manifest = json.loads(manifest_path.read_text())
            if not isinstance(manifest, dict):
                raise ValueError("the manifest is not an object")
            manifest["post"] = {"status": error or "ok"}
            _write_manifest(manifest_path, manifest)
        except (OSError, ValueError):
            print(f"warn: cannot record the hook result in {manifest_path}")
        if error is not None:
            raise GitProjectError(
                f"worktree migrate is complete, but the command in "
                f"{plan.post_key} {error}. The migration stays. Run the "
                f"command again by hand in {plan.top}."
            )
    return 0


class WorktreePlugin(Plugin):
    """
    The worktree command manages worktrees and connects them to projects.

    Summary::

      git <project> worktree add [-b <branch>] <name-or-path> [<committish>]
      git <project> worktree rm [-f] [--keep-branch] [--keep-remote-branch]
                                <name>
      git <project> worktree config <ident> [--add] [--unset] <name> [<value>]
      git <project> worktree migrate [--apply]

    ``worktree add`` creates a worktree at <name-or-path> and checks out a
    branch in it. The worktree's name is the last component of <name-or-path>.
    The branch is named after <name-or-path>: a simple name gives a branch of
    that name, and a relative path such as ``../user/topic`` gives
    ``user/topic``, the part after any ``..``. That branch is created at
    <committish>, or at HEAD, when it does not exist yet. An existing branch is
    checked out as it is, and <committish> is then ignored. With -b <branch>,
    the new branch <branch> is created at <committish> or HEAD and checked out
    instead.

    A relative path that does not start with ``..`` is placed under the root of
    the current worktree, or under the current directory in a bare repository.
    A path that starts with ``..`` is taken from the current directory. So
    ``worktree add ../topic``, run in the main worktree, puts the new worktree
    beside it, and ``worktree add topic`` puts it inside.

    To keep things simple, we'll usually always name worktrees similarly (or
    identically) to the branches they reference, though it is not strictly
    necessary to do so.

    ``worktree rm`` removes a worktree and its workarea. It first removes the
    paths that ``artifact`` associates with the worktree, and if one of those is
    refused, nothing is removed. The branch is deleted too, locally and on each
    project remote, unless a flag says otherwise: ``--keep-branch`` leaves the
    branch alone everywhere, and ``--keep-remote-branch`` deletes only the
    local copy.  A branch the project configures is never deleted, whatever the
    flags say.  Removing a worktree whose branch is unmerged requires ``-f``,
    unless ``--keep-branch`` means the branch survives anyway.

    The key idea behind project worktrees is that they are connected to various
    ``artifacts``.  Worktrees are managed together with these artifacts to
    provide a project-level view of various tasks.  For example, a ``run``
    command can create artifacts associated with a worktree.  Removing the
    worktree implicitly removes these artifacts, making build cleanups easy and
    convenient.  Commands may use the {worktree} substitution to create
    worktree-unique artifacts.  Other substitutions may also reference
    {worktree} in a recursive manner.

    Here is a concrete example::

      git <project> config srcdir "{path}"
      git <project> config builddir "{srcdir}/build/{worktree}"
      git <project> config make "make -C {srcdir} BUILDDIR={builddir} {build}"
      git <project> run --make-alias build
      git <project> add build release "{make}"

    Assuming the build system uses BUILDDIR to determine where build artifacts
    go, each worktree will get a unique set of build artifacts, via the
    {builddir} and, recursively, {worktree} substitutions.  When we delete the
    worktree, we'll also delete the associated build directory.

    We associate artifacts with worktrees via the artifact commands.

    Another important benefit of worktrees and associated builds is that
    switching to work on a new worktree (by simply editing sources in a
    different worktree directory) will not result in build artifacts from the
    previous worktree being overwritten.  Thus we avoid the ``rebuild the
    world`` problems of switching branches within the same workarea.  Generally,
    each created branch will have its own worktree and we will rarely, if ever,
    switch branches within a worktree.

    A worktree layers a config scope on top of the global project scope, so that
    configuring a key in the worktree with the same name as a key in the project
    will cause the worktree key's value to override the project key's value::

      git <project> config buildwidth 16
      git <project> worktree config myworktree buildwidth 32

    The worktree to configure is named explicitly, so myworktree gets
    buildwidth=32 while the project keeps 16.

    Inside myworktree, wherever {buildwidth} appears (say, in a run command),
    32 is substituted instead of 16. Outside myworktree, or in a worktree with
    no buildwidth of its own, {buildwidth} gives 16. The Scopes section of the
    git-project documentation describes the rule:
    https://pypi.org/project/git-project/

    The worktree plugin also adds a --worktree option to the clone and init
    commands.  Both set up the ``worktree layout`` described in the package
    documentation.  The bare repository is a hidden child directory named for
    the last component of the remote url, such as ``.myrepo.git``.  The
    top-level directory holds it alongside the worktrees.

    ``clone --worktree`` clones bare, then rewrites the fetch refspec and sets
    the main branch to track its remote branch, so fetch and pull behave as
    they do in a regular clone.  The refs/heads and refs/remotes namespaces
    remain, and every other local branch is deleted. Add ``--bare`` to skip
    the refspec rewrite. The clone still gets the ``.git`` file and the main
    worktree. With no <path>, ``clone --worktree`` uses the current directory
    itself as the top-level directory, where a plain clone makes a new one.

    ``init --worktree`` converts an existing clone in place.  The workarea must
    be clean.  The conversion deletes every file in the top-level directory
    except the git directory, so preserve anything there that is not part of
    the repository.  Only the main branch gets a worktree, so a different
    checked-out branch gets none, though one is easy to add afterward. To
    convert a clone you work in, with its branches and linked worktrees, use
    ``worktree migrate`` instead.

    On a repository that is already bare, ``init --worktree`` deletes nothing.
    It refuses to run while a branch other than the main one exists, because it
    cannot know which remote each branch should go to.

    ``worktree migrate`` converts a flat clone, one whose ``.git`` is a
    directory, to the worktree layout. Every branch, ref, stash and config
    value stays. Each linked worktree moves into the top-level directory. The
    files of the main worktree, ignored ones too, move into a worktree named
    for the main branch. Without ``--apply`` it prints each step and changes
    nothing. One exception applies to every git-project command: before the
    command runs, git-project may set ``<project>.branch`` and
    ``<project>.remote`` when they are unset.

    The main branch is the first branch the project configures that exists
    locally. Failing that, it is ``main``, then ``master``, then the only
    local branch. The main clone must have it checked out. A linked worktree
    named ``<top>-<rest>``, where <top> is the name of the top-level
    directory, moves to ``<rest>``. Any other moves to a directory named for
    its branch, with each ``/`` turned into ``-``. So ``proj-topic`` beside
    ``proj`` becomes ``proj/topic``, and a worktree on ``user/feature``
    becomes ``proj/user-feature``.

    It refuses when a worktree has changes or untracked files, is locked,
    prunable or missing, or has a detached HEAD. It refuses during a merge,
    cherry-pick, revert, rebase or bisect. It refuses a worktree with
    submodules, a sparse checkout, or assume-unchanged or skip-worktree
    files. It refuses a linked worktree inside <top> or on another
    filesystem, and a mount point in <top>. It refuses when two worktrees
    get the same target directory or worktree name, and when a target
    directory exists. It refuses when ``core.worktree`` is set, or when the
    main worktree's ``config.worktree`` sets ``core.bare``. It refuses when
    ``extensions.relativeWorktrees`` or ``worktree.useRelativePaths`` is
    true, because the repair writes absolute links. It also refuses when the
    project remote has no url, when GIT_DIR or a variable like it is set,
    with git older than 2.36, and on a clone already converted. It reports
    every reason it finds and makes no change of its own. Some basic checks,
    such as the git version, stop it before the rest run.

    Each worktree's config moves with it. A ``worktreepath`` entry for an
    old path stays and is reported, so remove it by hand. A project value
    that holds an old path, such as ``<project>.builddir`` set to
    ``<old>/build``, gets a warning that names its key and not its value. The
    warning does not stop the migration, so fix the value by hand. A tool
    that records absolute paths, such as a Python virtualenv, may need to be
    made again.

    ``worktree migrate`` also converts a store that is already bare at
    <top>/.git, with its worktrees inside <top>. It renames the store to the
    hidden name, writes the ``.git`` file and repairs each worktree. A
    worktree's ``commondir`` file that holds an absolute path is rewritten
    as ``../..``, because the repair leaves it naming the old store. No
    worktree moves and no config changes. The checks above apply to each
    worktree, except the sparse checkout, assume-unchanged, skip-worktree and
    filesystem checks. Those matter only when files move or an index is
    reset. It also refuses a worktree outside <top> or inside the store, and
    a store with no worktrees. It refuses a store with an index. It looks in
    <top> and in each directory between <top> and a worktree, and refuses
    an entry there that holds no worktree, unless its name starts with
    ``.``. An index or such an entry can mean a checkout that ``core.bare``
    hides. It refuses a ``commondir`` that names another repository. A
    ``core.bare`` in the store's ``config.worktree`` is allowed, since
    ``git sparse-checkout`` puts it there.

    For a flat clone or a bare store, the plan lists each local branch
    with commits its upstream lacks, and how many. A commit the upstream
    has under another id, as after a rebase or cherry-pick, does not count.
    A branch with no upstream, or an upstream that is gone, is compared
    with the main branch. A bare store with no main branch lists only
    branches with an upstream. The list is for information and does not
    stop the migration.

    After a successful ``--apply`` of either kind, migrate runs the
    command in ``<project>.postmigrate``, if it is set, in <top>. The value
    is split into words as a shell would split it, but no shell runs it, so
    pipes, redirections and variables do not work. The command runs in its
    own session and gets no standard input. It has the number of seconds in
    ``<project>.postmigratetimeout`` to finish, 600 when that is unset. On
    a timeout or a Ctrl-C, migrate sends SIGTERM to the command's process
    group, then SIGKILL after five seconds. A process that starts its own
    session or process group is not stopped. Only a Ctrl-C or the timeout
    stops the command. A hangup or a SIGTERM to migrate does not reach it.
    The result goes in ``post.status`` in the manifest, ``ok`` or the
    reason it failed. When the command fails or is interrupted, the
    migration stays done and migrate exits with a failure status. The dry
    run shows the step and the config file that sets the command, but does
    not run it. Migrate refuses a command it cannot split, an empty one,
    and a timeout that is not a whole number from 1 to 86400.

    ``--apply`` writes the plan to ``git-project-migrate.json`` in the git
    directory. Before each step runs, its name goes in ``current_step``.
    When the step finishes, it is added to the ``steps_done`` list. The
    migration stops at the first failure and names the step in
    ``failed_step``. A hard stop, such as a kill, leaves no
    ``failed_step``, so read ``current_step``. The error names the
    failed step, its reason and the manifest. After a stop in
    ``rename_store`` the manifest is at either <top>/.git or <store_new>.
    When ``verify`` finds a worktree that is not clean, it names the first
    10 changed or untracked paths and counts the rest.

    Manual rollback. Undo the steps that ``steps_done`` lists, in the order
    below. The failed step, or the current step after a hard stop, may be
    fully done, partly done, or not done. Check it as its comment below
    says, and undo it when it is done or partly done. Take <top>,
    <store_new>, <main> and the other values from the manifest. <main> is
    ``main.new`` and each <new> and <old> is a ``linked`` entry. The steps
    ``verify``, ``repair``, ``reset_index`` and ``copy_main_state`` need
    nothing::

      # write_pointer: done when <top>/.git is a file
      rm <top>/.git
      # rename_store: done when <store_new> exists
      mv <store_new> <top>/.git
      git -C <top> worktree repair <new>...
      # detach_head: undo it either way
      git --git-dir=<top>/.git symbolic-ref HEAD <head_ref>
      # set_bare: done when this prints true
      git --git-dir=<top>/.git config core.bare
      # set_bare, when core_bare is not null
      git --git-dir=<top>/.git config core.bare <core_bare>
      # set_bare, when core_bare is null
      git --git-dir=<top>/.git config --unset core.bare
      # each move_entry <entry>: done when <main>/<entry> exists
      mv <main>/<entry> <top>/<entry>
      # add_main: done when <main> exists
      rm -f <main>/.git
      rmdir <main>
      git -C <top> worktree prune
      # each move_linked: done when <new> exists
      git -C <top> worktree repair <new>
      git -C <top> worktree move <new> <old>
      # then, if any move_linked was undone
      git -C <top> worktree repair <old>...
      # write_config: undo it either way. Set each config_writes key
      # back to its prior value, or unset it when prior is null.
      # last, remove the manifest
      rm -f <top>/.git/git-project-migrate.json
      rm -f <top>/.git/git-project-migrate.json.tmp

    A bare store at <top>/.git has a manifest with ``form`` set to
    ``bare_at_root``. Each <path> is a ``linked`` entry. The ``verify`` step
    needs no undo. The repair command below undoes ``repair``. The
    ``rewrite_commondir`` steps need no undo, since ``../..`` names the store
    at either path::

      # write_pointer: done when <top>/.git is a file
      rm <top>/.git
      # rename_store: done when <store_new> exists
      mv <store_new> <top>/.git
      git --git-dir=<top>/.git worktree repair <path>...
      # last, remove the manifest
      rm -f <top>/.git/git-project-migrate.json
      rm -f <top>/.git/git-project-migrate.json.tmp

    See also::

      artifact
      config
      run

    """

    def __init__(self):
        super().__init__("worktree")

    def initialize(self, git, gitproject, project, plugin_manager):
        """Instantiate a Worktree if we are in a worktree path, providing scoping for
        Project config variables.

        git: A Git object to examine the repository.

        gitproject: A GitProject object to explore and manipulate the active
                    project.

        project: The active Project.

        plugin_manager: The active  PluginManager.

        """
        path = Path.cwd().resolve()
        while True:
            if ConfigObject.exists(
                git,
                project.get_section(),
                Worktree.Path.subsection(),
                str(path),
            ):
                Worktree.get_by_path(git, project, str(path))
                break
            parent = path.parent
            if parent == path:
                break
            path = parent

    def add_arguments(
        self, git, gitproject, project, parser_manager, plugin_manage
    ):
        """Add arguments for 'git-project worktree.'"""

        # worktree
        worktree_parser = add_top_level_command(
            parser_manager,
            Worktree.get_managing_command(),
            Worktree.get_managing_command(),
            help="Manage worktrees",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        add_plugin_version_argument(worktree_parser)

        worktree_subparser = parser_manager.add_subparser(
            worktree_parser, "worktree-command", help="worktree commands"
        )

        # worktree add
        worktree_add_parser = parser_manager.add_parser(
            worktree_subparser,
            "add",
            "worktree-add",
            help="Create a worktree",
            epilog="The path is required. The committish defaults to HEAD.",
        )

        worktree_add_parser.set_defaults(func=command_worktree_add)

        worktree_add_parser.add_argument(
            "path", help="Path for worktree checkout"
        )
        worktree_add_parser.add_argument(
            "committish", nargs="?", help="Branch point for worktree"
        )
        worktree_add_parser.add_argument(
            "-b",
            "--branch",
            metavar="BRANCH",
            help="Create BRANCH for the worktree",
        )

        # worktree rm
        worktree_rm_parser = parser_manager.add_parser(
            worktree_subparser, "rm", "worktree-rm", help="Remove a worktree"
        )

        worktree_rm_parser.set_defaults(func=command_worktree_rm)

        worktree_rm_parser.add_argument("name", help="Worktree to remove")
        worktree_rm_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Remove even if branch is not merged",
        )
        worktree_rm_parser.add_argument(
            "--keep-branch",
            action="store_true",
            help="Keep the branch, locally and on remotes",
        )
        worktree_rm_parser.add_argument(
            "--keep-remote-branch",
            action="store_true",
            help="Keep the branch on remotes, deleting only the local copy",
        )

        # worktree migrate
        worktree_migrate_parser = parser_manager.add_parser(
            worktree_subparser,
            "migrate",
            "worktree-migrate",
            help="Convert a flat clone to the worktree layout",
        )

        worktree_migrate_parser.set_defaults(func=command_worktree_migrate)

        worktree_migrate_parser.add_argument(
            "--apply",
            action="store_true",
            help="Make the changes, instead of only printing them",
        )

        # add a clone option to create a worktree layout.
        clone_parser = parser_manager.find_parser("clone")
        if clone_parser:
            clone_parser.add_argument(
                "--worktree",
                action="store_true",
                help="Create a layout convenient for worktree use",
            )

        # add an init option to create a worktree layout.
        init_parser = parser_manager.find_parser("init")
        if init_parser:
            init_parser.add_argument(
                "--worktree",
                action="store_true",
                help="Create a layout convenient for worktree use",
            )

    def _choose_main_branch(self, git):
        """Return the refname of the main branch.  Ask the user if we cannot determine a
        unique main branch.

        """
        main = git.get_main_branch()
        if main:
            return git.branch_name_to_refname(main)

        branches = list(git.iterrefnames(["refs/heads"]))
        while True:
            for refname in branches:
                print(git.refname_to_branch_name(refname))
            main = input(
                "No unique main branch found, enter branch to use as main: "
            )
            if git.branch_name_to_refname(main) in branches:
                break

        return git.branch_name_to_refname(main)

    def _rewrite_bare_refspects(self, p_git):
        """Modify refspects to convert from a bare repository so that we merge origin
        branches to local branches.  Return he refname of the main branch.

        """
        assert p_git.is_bare_repository()

        p_git.set_remote_fetch_refspecs(
            "origin", ["+refs/heads/*:refs/remotes/origin/*"]
        )
        p_git.fetch_remote("origin")

        main = self._choose_main_branch(p_git)

        for refname in p_git.iterrefnames(["refs/heads"]):
            if refname == main:
                remote_refname = p_git.get_remote_fetch_refname(
                    refname, "origin"
                )
                p_git.set_branch_upstream(refname, remote_refname)
            else:
                p_git.delete_branch(refname)

        return main

    def _setup_main_worktree(
        self, main, p_git, p_gitproject, p_project, path, clargs
    ):
        """Create a main woorktree for a newly-created worktree layout."""
        # Set up a main worktree.
        main_branch = p_git.refname_to_branch_name(main)

        main_path = path / main_branch
        clargs.committish = main_branch
        clargs.path = str(main_path)

        command_worktree_add(p_git, p_gitproject, p_project, clargs)

    def modify_arguments(
        self, git, gitproject, project, parser_manager, plugin_manager
    ):
        """Modify arguments for 'git-project worktree.'"""

        # If a clone is done, set up a main worktree if told to.
        clone_parser = parser_manager.find_parser("clone")
        if clone_parser:
            command_clone = clone_parser.get_default("func")

            def worktree_command_clone(p_git, p_gitproject, p_project, clargs):
                if clargs.worktree:
                    path = Path.cwd()
                    if hasattr(clargs, "path") and clargs.path:
                        path = Path(clargs.path)

                    assert hasattr(clargs, "url")

                    path = path / get_hidden_gitdir_name(clargs.url)

                    bare_specified = clargs.bare

                    clargs.path = str(path)
                    clargs.bare = True

                    # Bare clone to the hidden directory.
                    path = command_clone(
                        p_git, p_gitproject, p_project, clargs
                    )

                    # If the user did not ask for a bare repo, rewrite refspecs,
                    # fetch remote refs and rewrite existing refs (just main)
                    # to track the remote ref.  Delete other "local" branches.
                    main = ""
                    if not bare_specified:
                        main = self._rewrite_bare_refspects(p_git)

                    if not main:
                        main = self._choose_main_branch(p_git)

                    write_container_gitdir(Path(path).parent, Path(path).name)

                    # Detach HEAD so we can worktree main.
                    p_git.detach_head()

                    self._setup_main_worktree(
                        main,
                        p_git,
                        p_gitproject,
                        p_project,
                        Path(path).parent,
                        clargs,
                    )
                else:
                    path = command_clone(
                        p_git, p_gitproject, p_project, clargs
                    )

                return path

            clone_parser.set_defaults(func=worktree_command_clone)

        # If an init is done, set up a main worktree layout if told to.
        init_parser = parser_manager.find_parser("init")
        if init_parser:
            command_init = init_parser.get_default("func")

            def worktree_command_init(p_git, p_gitproject, p_project, clargs):
                path = command_init(p_git, p_gitproject, p_project, clargs)

                if clargs.worktree:
                    was_bare = p_git.is_bare_repository()

                    # A bare repository rewrites origin's refspecs. Otherwise
                    # the project remote's url names the hidden git directory.
                    # Check first, so a missing remote changes nothing.
                    remote = "origin"
                    if not was_bare:
                        remote = next(p_project.iterremotes(), remote)
                    try:
                        p_git.get_remote_url(remote)
                    except KeyError:
                        raise GitProjectError(
                            f"Cannot initialize worktree layout, no remote named {remote}"
                        ) from None

                    main = self._choose_main_branch(p_git)

                    # If it's not already, convert the current workarea to a bare repository.
                    if not p_git.is_bare_repository():
                        if not p_git.workarea_is_clean():
                            raise GitProjectError(
                                "Cannot initialize worktree layout, working copy not clean"
                            )

                        gitdir = Path(p_git.get_gitdir())
                        workarea_root = Path(p_git.get_working_copy_root())
                        assert workarea_root.exists()

                        if gitdir != workarea_root / ".git":
                            raise GitProjectError(
                                "Not creating worktree layout -- are you in a worktree?"
                            )

                        # Set bare and detach before removing files so they
                        # don't come back.  If we detach later, files will be
                        # checkout out.
                        p_git.config.set_item("core", "bare", "true")
                        p_git.detach_head()

                        # Remove everything except .git.
                        for filename in os.listdir(workarea_root):
                            if filename == ".git":
                                continue
                            path = workarea_root / filename
                            if os.path.isfile(path) or os.path.islink(path):
                                os.unlink(path)
                                assert not os.path.exists(path)
                            elif os.path.isdir(path):
                                shutil.rmtree(path)
                                assert not os.path.exists(path)

                        # Rename .git to something else (see
                        # get_hidden_gitdir_name).
                        assert gitdir.is_dir()
                        assert gitdir.name == ".git"

                        remote = next(p_project.iterremotes())
                        newgitdir = gitdir.parent / get_hidden_gitdir_name(
                            p_git.get_remote_url(remote)
                        )
                        gitdir.rename(newgitdir)
                        assert newgitdir.exists()
                        assert not gitdir.exists()

                        # Update the git object so main can continue.
                        p_git.reinit(newgitdir)
                        assert Path(p_git.get_gitdir()) == newgitdir
                        p_git.validate_config()

                        # After the reinit, so discovery resolves the clone
                        # the same way it did before. The already-bare path
                        # below keeps its .git as the clone itself, so only
                        # the renamed case gets a pointer.
                        write_container_gitdir(workarea_root, newgitdir.name)

                    if was_bare:
                        workarea_root = Path(p_git.get_gitdir()).parent

                        # Note that since this is a bare repository, we may have
                        # branches besides main that are not pushed to
                        # whatever remote they should go to.  In general we
                        # cannot know which branches should go where so just
                        # punt and tell the user to clean them up.
                        for refname in p_git.iterrefnames(["refs/heads"]):
                            if refname != main:
                                raise GitProjectError(
                                    "Non-main branches detected, please push and/or delete them and try again."
                                )

                        newmain = self._rewrite_bare_refspects(p_git)
                        assert newmain == main

                    self._setup_main_worktree(
                        main,
                        p_git,
                        p_gitproject,
                        p_project,
                        workarea_root,
                        clargs,
                    )

            init_parser.set_defaults(func=worktree_command_init)

    def iterclasses(self):
        """Iterate over public classes for git-project worktree."""
        yield Worktree
