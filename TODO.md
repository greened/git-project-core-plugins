******
TODOs
******

* Add an "alias" command to allow new names for existing commands, e.g.:

    git project alias check build
    git project add check <command to check>

  This would work around some thorny issues with build flavors.  For example if
  we have a "release" flavor we have to do something like this:

    git project add build release <command to build>
    git project add build check-release <command to check>

  This causes special cases in various scripts because the flavor "release" has
  to be renamed to "cbheck-release" for an overloaded use of the build command.
  Aliasing the command type rather than the flavor is more natural.

* Remove "configure" and "install" commands in favor of aliases.  The code is
  almost entirely the same as for build and we really don't want to repeat it.

* Add a "help" command to allow customization of help.  For example users could
  document configuration parameters for commands:

    git project add build devrel "make -C {builddir} -j {buildwidth} devrel"
    git project config buildwidth 16
    git project add help buildwidth "Specify the build parallelism"
    git project add help check "Run tests"
    git project add help build devrel "Build a developer release flavor"

  Help would be stored in a special help section:

    [project "help"]
    buildwidth = Specify the build parallelism
    check = Run tests

    [project "help.build"]
    devrel = Build a developer release flavor

  We would to tie this into help output for commands when a command name is
  specified to the "help" command, e.g.:

    git project build --help
    <main help text>

    Build types:
    devrel - Build a developer release flavor

* Add "artifacts" that are deleted when some git config object is deleted, for
  example worktrees:

    git project artifact add worktree "{builddir}"

    [project "artifact"]
    worktree = {builddir}

    git project worktree rm mytree  # Deletes the corresponding build directory
