# insarhub-api — GMTSAR processor backend for InSARHub

**Status: v0, staged for testing (2026-07-20). Not yet run against a
real InSARHub install or real Sentinel-1 data.** This directory is a
scoping exercise made concrete as real code, not a finished integration.
Read this file before trusting anything in `gmtsar_s1.py`.

## Why this exists

[InSARHub](https://github.com/jldz9/InSARHub) (Jiawei Li, Colorado State)
is a plugin-architected Python framework: Downloader → Processor →
Analyzer. It currently supports two `Processor` backends — `Hyp3_S1`
(cloud) and `ISCE_S1` (local/HPC) — both Sentinel-1-only, both driving
someone else's SAR engine (HyP3's API, ISCE2's `stackSentinel.py`) rather
than doing SAR compute itself.

GMTSAR is the actual compute engine his architecture is designed to plug
things like this into — this is a `GMTSAR_S1` processor implementing his
real `LocalProcessor` interface (`submit`/`refresh`/`retry`/`watch`/`save`),
modeled directly on his existing `ISCE_S1` implementation for interface
conventions (status constants, job JSON, per-pair parallel execution).

## Why output normalization needs zero new code

I checked MintPy's own `prep_gmtsar.py` (upstream, `mintpy/prep_gmtsar.py`)
directly. It globs `{corr,phase,phasefilt,unwrap}_ll*.grd` and two
digit-named `*.PRM` files per interferogram directory — which is *exactly*
GMTSAR's native `intf/<ref>_<sec>/` output layout, unmodified. So once
InSARHub's existing `Mintpy_SBAS_Base_Analyzer` has `GMTSAR_S1` added to
its `compatible_processor` list (a one-line change on his side, not here),
it should be able to consume a GMTSAR case directory as-is.

## What's real vs. assumed in this v0

**Verified against real sources** (not guessed):
- `insarhub.core.LocalProcessor`'s abstract interface (5 methods) — read
  directly from `src/insarhub/core/base.py` upstream.
- `ISCE_S1`'s conventions (status constants, job JSON shape, per-step
  parallel execution model) — read directly from
  `src/insarhub/processor/isce_s1.py` and `isce_base.py` upstream.
- `p2p_processing`'s real CLI contract: `p2p_processing SAT ref sec
  [config.py]`, one pair per invocation, valid `SAT` values including
  `S1_TOPS` — read directly from `utils/p2p_processing` in this repo.
- MintPy's `prep_gmtsar.py` input expectations — read directly from
  `mintpy/prep_gmtsar.py` upstream.

**Assumed / not yet verified — needs a real test before this is trustworthy:**
1. **Pre-processing gap.** `_stage_case()` assumes `slc_dir` already
   contains whatever `p2p_processing` expects as `ref`/`sec` identifiers.
   It's unconfirmed whether `p2p_processing` internally runs
   `make_slc_s1a`-equivalent preprocessing on raw `.SAFE`/`.zip` input, or
   expects already-focused SLCs. This is the single biggest unknown —
   needs tracing `p2p_stages.py`'s stage 1 against a real S1 `.SAFE`
   input before trusting `submit()` end-to-end.
2. **DEM handling is unimplemented**, not just untested. `dem_path=None`
   raises `NotImplementedError` rather than auto-downloading like
   `ISCE_S1` does (GLO-30 via `dem_stitcher`). GMTSAR has its own DEM
   tooling (`make_dem`) that should be wired here instead of
   reinventing ISCE_S1's approach — not started.
3. **No HPC/SLURM support.** `ISCE_S1` has a real `hpc_mode` path
   (sbatch templates, per-step SLURM config); this v0 only does local
   `ThreadPoolExecutor` concurrency. Deliberately out of scope for a
   first test, not forgotten.
4. **Never imported against the real `insarhub` package.** The
   `LocalProcessor` import has a fallback shim (see top of
   `gmtsar_s1.py`) so this module is at least syntactically valid and
   unit-testable without `insarhub` installed — but the real interface
   might have details (return types, extra hooks) the public README/repo
   browse didn't surface. First real test must be inside an actual
   InSARHub dev environment.
5. **One shared `case_dir` for the whole pair stack** — GMTSAR's
   `config.py`/`raw/`/`topo/` convention is per-case, not per-pair, so
   all pairs in one `GMTSAR_S1(pairs=...)` call share one case directory.
   Untested with real concurrent `p2p_processing` invocations sharing
   staged `raw/`/`topo/` — need to confirm GMTSAR's stage functions don't
   have any single-case-at-a-time assumptions that would break under
   `max_workers > 1`.

## Before this goes anywhere near a PR to jldz9/InSARHub

1. Test #1 above against one real Sentinel-1 pair, in this dev
   environment, using an existing `S1_TOPS` case from
   `gmtsar/python/tests/cases.py` as ground truth for what `raw/`
   actually needs to contain.
2. Once `submit()` → `intf/<ref>_<sec>/` is proven end-to-end, run
   MintPy's real `prep_gmtsar.py` against the output directory and
   confirm it parses cleanly (this is the "zero new code" claim above —
   verify it, don't just trust the source read).
3. Decide with Jiawei where this code should actually live long-term:
   contributed directly into `jldz9/InSARHub` as
   `src/insarhub/processor/gmtsar_s1.py` (matching where `isce_s1.py`
   lives), or maintained here and installed as a separate package
   InSARHub discovers via its registry. That's a design conversation,
   not a decision made unilaterally by writing code in one place first.
