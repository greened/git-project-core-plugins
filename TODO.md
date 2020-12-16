******
TODOs
******

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

* Add ConfigObject identity substitution:

    [run "test"]
    command = make -C {path}/../{worktree}

  Here `{worktree}` would be replaced by the identity of the active worktrree.
  Substitutions should match the subsection of a ConfigObject and be replaced by
  its identity.
