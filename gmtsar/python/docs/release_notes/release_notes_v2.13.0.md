# v2.13.0 — `sbas` time-series solver ported to Python (8/9 flags bit-exact)

Scope: `v2.12.1..v2.13.0`. First time-series component in the Python
framework. Everything upstream of `sbas` (pair selection, baselines,
interferogram formation) was already ported but is still unverified against
csh; this release covers the solver only.

## What landed

`bin_py/sbas_py/sbas_ref.py` — literal, correctness-first port of
`gmtsar/sbas.c` + `sbas_utils.c` (Tong 2014), wired in behind `utils/sbas`.

Oracle: the `sbas` C binary on the ALOS Indio SBAS set (88 interferograms,
28 scenes, 700x1000), which ships its own `vel.grd`/`rms.grd`. A fresh C run
reproduced those shipped grids to 3.6e-07, so the oracle itself was checked
before anything was compared against it.

Scored with `tests/compare.py`'s own `DEFAULT_GRD_RMS = 1e-2`, not a metric
invented for this port (Rule 12b):

| flags | grids | worst rms |
|---|---|---|
| `-rms -dem -smooth 1` | 31 | 1.9e-06 |
| `-rms -dem -smooth 0` | 31 | 2.2e-06 |
| `-rms -smooth 1` | 30 | 1.9e-06 |
| `-dem -smooth 1` | 30 | 1.9e-06 |
| `-wavelength .055 -incidence 39 -range 8e5` | 31 | 5.2e-07 |
| `-atm 1` | 59 | 1.9e-06 |

`-atm 1` exercises all six APS helpers end to end. The four that print
diagnostics were additionally unit-checked against the C's own `atm_noise`
output: identical to 6 decimals, identical rank order.

Runtime 48 s vs the C's 28 s. No optimisation attempted (Rule 7).

## Not supported: `-atm n>=2`

`utils/sbas` routes it to the C and says so. This is not a porting gap.
`init_G_ts` never clears G, and `init_array_ts` — the function that does — is
not called inside the atm loop, so iteration 2 builds its design matrix on top
of the QR factorization `dgelsy` left in G from iteration 1's last pixel. The
result depends on scan order and on the LAPACK build; emulating the debris in
Python made agreement worse, because the C links the conda env's libopenblas
while scipy ships its own openblas64. **Two builds of the C would not agree
either.**

## Three defects found in the C

Not yet filed upstream. Full writeup in `docs/dev_notes/NOTES_SBAS.md`.

1. **`-atm n>=2` uninitialized design matrix**, above.
2. **`jpvt` never reset** (`sbas_utils.c:179`, plain `malloc`; loop at `:430`).
   LAPACK reads nonzero `JPVT(i)` as "column fixed", so pivoting is off after
   the first pixel; the first call reads uninitialized heap. Rank returns 28
   instead of 27 on ~19.5% of pixels; 11.1% differ in velocity, up to
   5.35 mm/yr. **Do not fix alone** — the matrix is never truly rank-deficient
   (sigma_min = 1.2085e-02, constant to 0.18%, a floor from the smoothing
   rows), and `rcond` is relative while sigma_max tracks coherence
   (`corr = -0.797`), so restoring pivoting truncates a well-determined
   direction on the *best* pixels.
3. **`sbas_utils.c:50` defines `Malloc` as `malloc`; `sbas_parallel.c:67` as
   `calloc`** — the two binaries disagree on the first pixel.

## Verification

- `bin_py/tests/test_sbas_py.py`: 14 new guards, all pass.
- Full `bin_py/tests/`: **600 passed, 60 skipped**. The single failure in the
  first run (`test_dem2topo_ra` mode1) was `rc=127 command not found` from
  `bin_py` missing from PATH in that shell; re-run with PATH set gives 11
  passed. Not a regression — this release adds only new files plus one docs
  edit.
- `sweep.py --full` NOT re-run: no existing pipeline calls `sbas`, so no
  swept case exercises this code. Adding an Indio sweep case is tracked as
  open in `PATHWAY_FORWARD.md`.

## Open

- File the three C defects upstream.
- Sweep case for Indio (needs the 1.1 GB dataset cached).
- Second dataset; only Indio verified. `-smooth 0/1` only.
- `sbas_parallel` untested.
- Rest of the SBAS chain (`get_baseline_table`, `baseline_table`,
  `select_pairs`, `prep_sbas`, `intf_batch`, `intf_tops`,
  `preproc_batch_tops`, `stack_corr`) ported but never run against csh.
