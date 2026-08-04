# NOTES_SBAS.md — porting `sbas` to Python, and three defects in the C

Status 2026-08-04. Port: `bin_py/sbas_py/sbas_ref.py` (scalar, literal).
Oracle: the `sbas` C binary on the ALOS Indio SBAS set
(`http://topex.ucsd.edu/gmtsar/tar/ALOS_Indio_SBAS.tar.gz`, 1.1 GB, 88
interferograms, 28 scenes, 700x1000, ships its own `vel.grd`/`rms.grd`).

Metric throughout is `tests/compare.py`'s own `DEFAULT_GRD_RMS = 1e-2`
(project_rules.md Rule 12b — do not invent a second definition of "pass").

## Parity achieved

| mode | grids | worst rms |
|---|---|---|
| `-rms -dem -smooth 1 -mmap` | 31 | 1.9e-06 |
| `-rms -dem -smooth 0 -mmap` | 31 | 2.2e-06 |
| `-rms -smooth 1 -mmap` | 30 | 1.9e-06 |
| `-dem -smooth 1 -mmap` | 30 | 1.9e-06 |
| `-wavelength .055 -incidence 39 -range 8e5` | 31 | 5.2e-07 |
| `-atm 1` (exercises all six APS helpers) | 59 | 1.9e-06 |

8 of 9 flags. `-atm 1` covers `connect`, `sum_intfs`, `compute_noise`,
`apply_screen`, `remove_ts`, `rank_double` end to end. The four that print
diagnostics were additionally unit-checked against the C's own `atm_noise`
output: identical to 6 decimals, identical rank order.

Runtime 48 s vs the C's 28 s on the Indio set.

## NOT supported: `-atm n>=2`

Not a porting gap — the C's output is not well defined. See defect 1.

## Defects found in the C

### 1. `-atm n>=2` builds its design matrix on LAPACK debris

`init_G_ts` (sbas_utils.c:358) never clears G. It writes only the 1s, the
`bperp*scale` column, and the smoothing rows. Inside the atm loop
(sbas.c:323-399) only `init_G_ts` is called; `init_array_ts` — the function
that zeroes G — runs at sbas.c:400, *after* the loop. But `lsqlin_sov_ts`
hands G to `dgelsy`, which overwrites it in place with the QR factorization.

So iteration 2's design matrix is part SBAS operator, part LAPACK internals
left by iteration 1's **last pixel**. It depends on scan order and on the
LAPACK build.

Evidence: `-atm 1` reaches parity (G was zeroed before the loop);
`-atm 2` does not. Emulating the destroyed-G carry-over in Python made
agreement *worse* (disp worst rms 1.55 -> 3.22), because a different LAPACK
leaves different residue. **Two builds of the C itself would not agree.**

### 2. `jpvt` never reset — column pivoting silently disabled

`jpvt = Malloc(int64_t, n)` (sbas_utils.c:179, plain `malloc`), never reset in
the pixel loop at :430. LAPACK reads nonzero `JPVT(i)` as "column i is fixed",
so after the second call every column is fixed and no pivoting happens for the
rest of the grid. The first call reads uninitialized heap — formally UB, works
only because fresh pages arrive zeroed.

Measured: rank 28 instead of 27 on ~19.5% of pixels; 11.1% differ in velocity,
up to 5.35 mm/yr.

**Do not fix alone.** The matrix is never truly rank-deficient:
sigma_min = 1.2085e-02, constant to 0.18% across the grid — a floor set by the
smoothing rows. `rcond=1e-3` is *relative*, and sigma_max varies 3.8 -> 24.8
with the per-pixel coherence weights (`corr(sigma_max, var) = -0.797`). So
restoring pivoting truncates a well-determined direction, preferentially on the
**highest-coherence** pixels — divergent pixels had median weight 1.451 vs
1.917 for identical ones. The current behaviour is the more defensible one.
The real issue is a relative `rcond` applied to a matrix whose scale is set by
per-pixel data weights.

Reproduced in the port deliberately (`jpvt_state` threaded through `solve()`),
because the C is the oracle.

### 3. `sbas` and `sbas_parallel` can disagree

`sbas_utils.c:50` defines `Malloc` as `malloc`; `sbas_parallel.c:67` defines it
as `calloc`, with the `malloc` version commented out at :64. The parallel build
zeroes `jpvt`, the serial one does not — different first pixel. Looks like
defect 2 was hit once, patched in one file, missed in the other.

## C quirks reproduced on purpose

- `jpvt` persistence, above.
- `disp` accumulates across atm iterations: `lsqlin` does
  `disp[...] = disp[...] + d[p]` and nothing zeroes it inside the loop
  (`disp[i]=0.0` only at sbas.c:236 and :405).
- `disp` is held in phase units and converted with `-79.58*wl` only at write
  time (`write_output_ts`). `-79.58` is the C's truncated 1000/(4*pi); not
  recomputed exactly.
- `compute_noise` returns 0.0 when the finite sum is exactly zero.
- `sum_intfs` accumulates in float32, not float64.
- The RMS branch sums `i=2..S-3` while its own sumxx/sumx/sumy came from
  `i=0..S-1`. Inconsistent, reproduced.
- `disp[0]` is always 0 (inner loop is `for p in range(i)`).

## Bugs in the port itself, found only because parity was the bar

1. `jpvt` not persisted across pixels — 11% of pixels wrong.
2. `jpvt` not persisted across `solve()` calls (the atm branch calls it n+1
   times).
3. `disp` re-zeroed per `solve()` instead of accumulating.
4. atm loop order: solve comes *first*, `sf = sfs[kk-1]` not `sfs[kk]`,
   `atm_rms` zeroed before each loop solve, `tmp_phi` reset only when `kk>1`.
5. `disp` written in phase units, missing the mm conversion.
6. Grid variable named `__xarray_dataarray_variable__` instead of `z` — would
   have broken every downstream GMT tool.

## Open

- `-atm n>=2`: unsupported, see defect 1. Report upstream.
- Defects 1-3 not yet filed upstream.
- Only one dataset. `-smooth 0/1` only; the sigma_min analysis depends on the
  smoothing rows existing.
- `sbas_parallel` untested.
- Port is 48 s vs 28 s; no optimisation attempted (Rule 7: verbatim first).
- Not wired into `utils/`, not in the sweep, no `tests/` entry yet.
- Rest of the SBAS chain (`get_baseline_table`, `baseline_table`,
  `select_pairs`, `prep_sbas`, `intf_batch`, `intf_tops`,
  `preproc_batch_tops`, `stack_corr`) is ported but has never been run against
  csh.
