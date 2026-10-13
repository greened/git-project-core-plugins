``worktree add`` checks the path, branch and record before it changes
anything, and refuses with a clear message where it used to fail part
way or overwrite a stale record. An add that fails partway removes the
branch, worktree and record it made. ``worktree rm`` checks every
artifact path before it removes any. Both commands take a new
``--check`` option that runs the checks alone, and a new ``--multirepo``
option that ties the worktree to a multirepo set.
