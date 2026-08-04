# sbas_py — Python port of GMTSAR's `sbas` time-series solver

`sbas_ref.py` is a literal, correctness-first port of `gmtsar/sbas.c` +
`sbas_utils.c` (Tong 2014). Oracle is the C binary; see
[`../../docs/dev_notes/NOTES_SBAS.md`](../../docs/dev_notes/NOTES_SBAS.md).

## Usage

Same CLI as the C:

    python sbas_ref.py intf.tab scene.tab N S xdim ydim \
        [-smooth sf] [-wavelength wl] [-incidence theta] [-range rng] \
        [-atm n] [-robust] [-rms] [-dem] [-mmap]

## Verified

Bit-parity against the C on the ALOS Indio SBAS set (88 interferograms,
28 scenes, 700x1000), scored with `tests/compare.py`'s own
`DEFAULT_GRD_RMS = 1e-2`:

| flags | grids | worst rms |
|---|---|---|
| `-rms -dem -smooth 1` | 31 | 1.9e-06 |
| `-rms -dem -smooth 0` | 31 | 2.2e-06 |
| `-rms -smooth 1` | 30 | 1.9e-06 |
| `-dem -smooth 1` | 30 | 1.9e-06 |
| `-wavelength .055 -incidence 39 -range 8e5` | 31 | 5.2e-07 |
| `-atm 1` | 59 | 1.9e-06 |

## Not supported

`-atm n>=2`. Not a porting gap: the C's `init_G_ts` never clears G and
`init_array_ts` is not called inside the atm loop, so iteration 2 builds its
design matrix on the QR factorization `dgelsy` left behind. The C's own output
is not reproducible across LAPACK builds. Detail in NOTES_SBAS.md.

## Performance

48 s vs the C's 28 s on the Indio set. No optimisation attempted —
project_rules.md Rule 7 (port verbatim first).
