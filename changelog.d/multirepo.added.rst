New ``multirepo`` command, with aliases ``mr`` and ``multi``, that runs
``worktree add``, ``worktree rm``, ``worktree config``, ``branch
status``, ``branch prune``, ``config`` or ``run`` in every repository of
a named set. A worktree set is created, checked and removed together.
New ``set`` command to list, edit and clone sets, which live in a file
named by ``<project>.set.file`` outside every member repository.
