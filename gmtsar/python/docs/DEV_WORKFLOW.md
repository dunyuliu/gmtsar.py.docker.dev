# Development workflow: fork lane and upstream lane

Frozen 2026-09-29. Two kinds of contribution leave this one clone, and they must
not mix.

```
            upstream/master (gmtsar/gmtsar)
             |  ^                     ^
     sync    |  | lane A: C/csh PRs   | lane B: "framework update" PRs
     (merge) v  | (branch up/*)       | (one squashed commit, from master)
            origin/master  =  upstream/master + gmtsar/python/
             ^
             | python PRs (branch py/*)
        fork developers
```

Remotes: `origin` = `dunyuliu/gmtsar.py.docker.dev` (a GitHub fork of
`gmtsar/gmtsar`), `upstream` = `gmtsar/gmtsar`.

## Invariant

The fork's master differs from upstream only under `gmtsar/python/`, measured
against the last upstream commit merged into it:

```bash
git diff --stat "$(git merge-base master upstream/master)" master -- ':!gmtsar/python'
# must print nothing
```

Do not diff against `upstream/master` directly: whenever upstream is ahead, that
lists upstream's new commits as if they were ours.

## Lane A: upstream work (C, csh, build)

1. Branch from upstream, never from the fork:
   `git switch -c up/<topic> upstream/master`
   (or a separate worktree: `git worktree add ../gmtsar-upstream -b up/<topic> upstream/master`).
2. Touch only non-Python files. Exception: a fix that must change a C source and
   its Python port together (e.g. gmtsar/gmtsar#1127).
3. One commit per PR. Push to the fork, open against upstream:
   `git push origin up/<topic>` then
   `gh pr create --repo gmtsar/gmtsar --base master --head dunyuliu:up/<topic>`.
4. Never merge an `up/*` branch into the fork's master. The change arrives
   through the next sync once upstream merges it. Delete the branch then.

**Needed in the fork before upstream merges it?** Put the patched file in
`gmtsar/python/c_fixes/`, which the installer applies at build time. Every file
there must have an open upstream PR, and is deleted once that PR merges.

## Lane B: Python framework

1. Branch from the fork: `git switch -c py/<topic> origin/master`. Touch only
   `gmtsar/python/`. Fork developers open PRs into the fork's master.
2. To ship to upstream: sync first (below), then open one squashed
   "gmtsar/python: framework update vX -> vY" PR from the synced master.
   Upstream developers also edit `gmtsar/python/` directly, so a PR from an
   unsynced fork would silently revert their changes.

## Sync

```bash
git fetch upstream
git merge upstream/master        # merge, never rebase: the fork is public
# check the invariant above, run the unit tests
git push origin master
```

Sync the same day upstream merges a lane-B PR. Upstream squash-merges, so its
copy of `gmtsar/python/` is a snapshot of the fork. If the fork edits the same
lines again before syncing, the next merge conflicts. Resolve those by hand;
never with `-X ours`, which discards upstream contributors' Python edits.

## Guards

- The installer's `c_fixes` step leaves tracked upstream files modified in the
  working tree. Never `git add -A` / `git commit -a` on master; stage paths
  explicitly.
- Local hooks protect only this clone. Fork PRs need the invariant check in CI.
- Stale `worktree-agent-*` branches reached master by squash, so git reports them
  all unmerged. Check each with `git cherry master <branch>` before deleting.
