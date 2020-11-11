************************
git-project-core-plugins
************************

Plugins for `git-project <http://www.github.com/greened/git-project>`_

This is a set of basic plugins to manage several aspects of projects kept within
git repositories.  These plugins include commands to:

#. Configure git-project and its various plugins
#. Clone repositories
#. Manage branches
#. Manage worktrees
#. Configure builds
#. Perform builds
#. Install the project

Setup
=====

``pip3 install git-project-core-plugins``

Commands
========

These plugins add a number of commands to git-project.  Each command has an
associated ``--help`` option to describe its function and options.

* ``git <project> config``

  Configure git-project or any git config sections added by projects.  This will
  add ``config`` subcommands to plugin commands that manipulate git config
  sections (e.g. ``git project build config``).

* ``git <project> clone``

  Clone a repository.  Other plugins may hook into this command to provide
  additional functionality.

* ``git <project> branch status``

  Report whether local branches are merged to a project branch and whether the
  local branch head is pushed to a remote.

* ``git <project> branch prune``

  Delete branches that are merged to a project branch and pushed to a remote.

* ``git <project> configure``

  Configure a build for the project.  Adds configure values to project and
  worktree git config sections.  Projects and worktrees use unique build trees
  such that switching among projects and worktrees does not result in
  "rebuilding the world."

* ``git <project> build``

  Run a build on the project.  Adds build values to project and worktree git
  config sections.

* ``git <project> install``

  Install a built project.  Adds install values to project git config sections.

* ``git <project> worktree``

  Create and manage worktrees for the project.  This plugin causes ``git
  <project> clone`` to create a special directory layout and a master worktree
  when performing a bare clone.  It also adds a ``git <project> clone`` option
  to disable the worktree clone functionality.

  Worktrees set up their own build trees such that switching from worktree to
  worktree does not result in "rebuilding the world."
