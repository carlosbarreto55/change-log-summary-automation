## Context

The workflow currently loads a release marker, runs `git fetch --prune` and `git rebase @{u}` in the configured repository, and then reads `<marker-hash>..HEAD`. This couples analysis to the checked-out branch, changes repository state before the requested range is known, and makes results depend on refs that can move while the workflow is running. Temporary diff files are also written to a configured path without proving that the path is outside the analyzed worktree.

The repository can be dirty, detached, ahead of or behind its upstream, or based on stale remote-tracking data. Those conditions are useful diagnostics but do not prevent object-level analysis when both range boundaries are explicit. CI and developer runs therefore need the same safe default: inspect the repository, freeze a range, and read objects without changing `HEAD`, the index, tracked or untracked worktree files, or repository refs.

The runtime entry point continues to receive a JSON configuration path. Existing marker configuration remains available as one lower-boundary selector, but implicit `HEAD` and mandatory synchronization are removed. A network refresh and the old in-place synchronization behavior remain distinct, explicit modes because they have different mutation and failure characteristics.

## Goals / Non-Goals

**Goals:**

- Require an explicit head ref and exactly one explicit base ref or marker selector.
- Resolve the selected boundaries to full commit SHAs once, after any explicitly requested update, and use only those SHAs throughout analysis.
- Bound marker lookup by the frozen head SHA.
- Make the default path free of fetch, rebase, checkout, and writes to the analyzed repository's `HEAD`, index, worktree, and refs.
- Report dirty, detached, ahead, behind, diverged, uncomparable, and unknown-freshness states without making a dirty checkout block read-only analysis.
- Support an explicit, ref-scoped remote refresh that does not check out or rebase a branch.
- Keep legacy in-place synchronization only as an explicit mode guarded by a clean attached worktree and a resolvable upstream.
- Keep temporary analysis data and read-only-mode output outside the source worktree.

**Non-Goals:**

- Proving that a remote has not changed without contacting it.
- Automatically selecting a head ref, base ref, remote, or upstream for the user.
- Creating a temporary clone or temporary Git worktree for ordinary object analysis.
- Changing commit filtering, module classification, AI summarization, or PDF contents.
- Making legacy synchronization safe for a dirty, detached, or upstream-less checkout.

## Decisions

### Make boundaries and repository update mode explicit in JSON

Runtime JSON will require `head_ref` and exactly one of `base_ref` or the existing `release_marker_config_path`. A marker path selects marker mode and must still load a non-empty `marker` string. Empty values, both lower-boundary selectors, or neither selector are configuration errors detected before any Git update or output write.

`repository_update_mode` will be an enum with these values:

- `read_only`: the default when the field is omitted; performs no network or repository update.
- `refresh_remote_refs`: requires an explicit remote and non-empty refspec list whose destinations are remote-tracking refs.
- `legacy_in_place_sync`: preserves the former fetch/rebase behavior only after its guards pass.

This single mode avoids ambiguous combinations of independent fetch and rebase booleans. Requiring refs in every mode also prevents legacy synchronization from reintroducing an implicit analysis boundary: synchronization happens first, then the configured refs are frozen.

Alternatives considered:

- Continuing to infer the head from the checked-out `HEAD` was rejected because detached and non-checked-out ref analysis must be deliberate and reproducible.
- Treating `base_ref` as an override while silently retaining a configured marker was rejected because configuration would no longer identify one unambiguous lower boundary.
- Fetch and rebase booleans were rejected because combinations such as rebase without a refresh are difficult to explain and validate.

### Separate non-mutating diagnostics from update behavior

Configuration and path validation run first. A preflight then inspects the checked-out worktree independently of the configured analysis head. Messages must identify that distinction when `head_ref` does not name the checkout.

The read-only Git runner will set `GIT_OPTIONAL_LOCKS=0` for every inspection, resolution, log, and show command. Using Git's equivalent `--no-optional-locks` global option is acceptable. This prevents optional index refreshes and lock-backed maintenance during commands such as status. Representative commands are:

```text
GIT_OPTIONAL_LOCKS=0 git -C <repo> rev-parse --show-toplevel
GIT_OPTIONAL_LOCKS=0 git -C <repo> status --porcelain=v2 --branch --untracked-files=normal
GIT_OPTIONAL_LOCKS=0 git -C <repo> symbolic-ref --quiet --short HEAD
GIT_OPTIONAL_LOCKS=0 git -C <repo> rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'
GIT_OPTIONAL_LOCKS=0 git -C <repo> rev-list --left-right --count 'HEAD...@{upstream}'
```

Porcelain status records identify staged, unstaged, and untracked changes. Failure of `symbolic-ref` identifies a detached checkout. When an upstream exists, the left/right counts classify the checked-out branch as ahead, behind, diverged, or equal to the available remote-tracking ref. A missing upstream, missing tracking ref, or failed comparison produces a warning that the relationship cannot be determined rather than a guessed status.

Remote freshness is a separate fact from local ahead/behind counts. In `read_only` mode, diagnostics always state that remote freshness is unknown, including when the checkout equals its local remote-tracking ref. A successful explicit refresh establishes freshness only for the refs named by that refresh and only as of that fetch; other relevant refs remain unknown.

Dirty and detached states are warnings in `read_only` and `refresh_remote_refs` modes because SHA-based object reads do not need a clean attached checkout. Diagnostics become guards only for `legacy_in_place_sync`.

Alternatives considered:

- Running `git status` without disabling optional locks was rejected because status can refresh the index even though the workflow only needs diagnostics.
- Treating equality with a local remote-tracking ref as proof of remote freshness was rejected because the remote-tracking ref can itself be stale.
- Blocking read-only analysis on a dirty checkout was rejected because it provides no safety benefit when no checkout files are read or changed.

### Scope explicit refresh to named remote refs

`refresh_remote_refs` runs before boundary resolution. It fetches only the configured remote/refspecs, writes destinations under that remote's tracking namespace, and suppresses `FETCH_HEAD` updates where supported:

```text
git -C <repo> fetch --no-tags --no-write-fetch-head <remote> <source-ref>:<remote-tracking-ref> [...]
```

The fetch can add objects and update the explicitly named remote-tracking refs, so it is not the default read-only mode. It does not invoke checkout, switch, reset, merge, pull, or rebase and therefore leaves `HEAD`, the index, and worktree files unchanged. A failed requested refresh is an error and stops analysis rather than silently falling back to stale refs.

Raw remote fetch defaults were rejected because they can update more refs than the user intended. Fetching into local branch refs was rejected because it can conflict with or indirectly alter the checked-out branch; refresh destinations are remote-tracking refs only.

### Guard the legacy in-place mode before any mutation

`legacy_in_place_sync` first uses the non-mutating preflight to require all of the following:

- An attached checked-out branch.
- No staged, unstaged, or untracked worktree changes.
- A configured and resolvable upstream for that branch.

If any guard fails, the workflow exits before fetch or rebase. After the guards pass, the mode preserves the existing sequence:

```text
git -C <repo> fetch --prune
git -C <repo> rebase '@{upstream}'
```

Fetch failure prevents rebase and downstream work. Rebase failure preserves the original error, attempts `git rebase --abort`, reports abort failure separately, and stops downstream work. Boundary SHAs are resolved only after successful synchronization.

This mode is intentionally named as legacy and in-place rather than `sync` so configuration makes its mutation risk visible. Automatically moving legacy users into this mode was rejected because opt-in must be deliberate.

### Freeze one SHA pair and pass it through all Git reads

After the selected update mode completes, the head is resolved once to a full commit SHA. An explicit base is then resolved once, or marker lookup walks only commits reachable from that frozen head SHA and returns the newest commit whose subject contains the marker. Representative commands are:

```text
GIT_OPTIONAL_LOCKS=0 git -C <repo> rev-parse --verify --end-of-options '<head-ref>^{commit}'
GIT_OPTIONAL_LOCKS=0 git -C <repo> rev-parse --verify --end-of-options '<base-ref>^{commit}'
GIT_OPTIONAL_LOCKS=0 git -C <repo> log <head-sha> --fixed-strings --grep=<marker> --format='%H%x1f%s' --
GIT_OPTIONAL_LOCKS=0 git -C <repo> log --reverse --format='%H%x1f%ae%x1f%aI%x1f%s' <base-sha>..<head-sha> --
GIT_OPTIONAL_LOCKS=0 git -C <repo> show --no-ext-diff --no-textconv <commit-sha> --
```

Marker candidates are checked against their subject after Git's fixed-string filtering so a body-only match is not accepted. The resulting immutable range value contains only `base_sha` and `head_sha`. Commit extraction, filtering, diff generation, report context, and diagnostics that describe the analyzed range receive that value or commit SHAs derived from it; they do not resolve the configured refs again and do not use ambient `HEAD`.

These commands document the intended implementation, not the specification contract. A Git library or equivalent plumbing is acceptable if it preserves the same bounded lookup, one-time SHA resolution, ordering, and mutation guarantees.

Alternatives considered:

- Resolving refs separately in marker lookup, commit extraction, and diff generation was rejected because a concurrent ref update could combine different repository states in one report.
- Searching marker history from ambient `HEAD` was rejected because it can select a boundary unrelated to the explicit analysis head.
- Checking out either boundary was rejected because Git can read commits and blobs directly from object IDs.

### Keep workflow-created files out of the source worktree

The workflow obtains the source worktree root from Git and compares canonical paths before creating files. The temporary analysis root must resolve outside that root in every mode. In `read_only` and `refresh_remote_refs` modes, the final output path must also resolve outside the source worktree so the no-worktree-modification guarantee remains literal. Existing atomic output behavior may use a sibling temporary file beside the external output, but it must not fall back to the repository.

Containment checks account for symlinks and are repeated after creating an external temporary directory when necessary. A configured path equal to or below the source root is rejected before diff, AI, or PDF work. No temporary clone or worktree is required because all Git data is read from frozen object IDs.

Allowing an explicitly configured temporary path inside the repository was rejected because generated or partially cleaned-up files would still alter status and could be consumed by later runs. Allowing read-only-mode output inside the source tree was rejected because an explicit filename does not change the worktree immutability claim.

## Risks / Trade-offs

- [Default analysis can use stale local refs] -> Always report unknown remote freshness and provide explicit ref-scoped refresh.
- [A ref can move or be deleted during analysis] -> Retain the resolved SHAs and fail clearly if an object becomes unavailable; never re-resolve and silently change ranges.
- [Status on a very large worktree has a cost] -> Run one porcelain preflight and reuse its result for warnings and legacy guards.
- [Explicit refresh still mutates Git metadata] -> Keep it out of the default, scope destinations to named remote-tracking refs, and report exactly which refs were refreshed.
- [Legacy rebase can still conflict after clean preflight] -> Attempt abort, preserve both errors when abort fails, and produce no downstream artifacts.
- [Symlinked output paths can bypass lexical containment checks] -> Compare canonical existing ancestors and validate the resulting directory before writing.
- [The new boundary fields break existing runtime JSON] -> Fail with a configuration error that names the required selectors and provide a direct marker-mode migration.

## Migration Plan

1. Add `head_ref` to every runtime JSON file. Use a full remote-tracking ref or commit SHA in CI when reproducibility is important.
2. Choose exactly one lower boundary. Keep `release_marker_config_path` and omit `base_ref` for existing marker behavior, or replace the marker path with an explicit `base_ref`.
3. Move `temp_diff_dir`, and any read-only-mode `output_path` inside the analyzed worktree, to an external directory.
4. Omit `repository_update_mode` to adopt the read-only default. Runs that require current remote data select `refresh_remote_refs` and list the exact remote refspecs to refresh.
5. Only users that require the former checked-out-branch rebase select `legacy_in_place_sync`; they must run from a clean attached branch with a configured upstream.
6. Update operational checks to treat status and freshness messages as warnings, while treating invalid selectors, requested-refresh failure, legacy guard failure, and unresolved boundaries as errors.

Rollback requires restoring the previous application version and its runtime JSON shape together. Before rollback, verify that no legacy synchronization has an in-progress rebase; abort or recover it explicitly if needed. Restore configurations that rely on `release_marker_config_path`, `temp_diff_dir`, and implicit `HEAD`, then communicate that the rolled-back default again performs in-place fetch/rebase. Read-only and refresh runs create no repository state that needs reversal; external temporary/output directories can be removed independently.

## Open Questions

None. The default, selector exclusivity, refresh scope, legacy guards, one-time SHA resolution, marker bound, and path guarantees are defined by this design.
