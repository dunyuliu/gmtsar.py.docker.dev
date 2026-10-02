# ALOS Indio SBAS — time-series solver only.
#
# Unlike every other case in the sweep, this one does NOT run p2p_processing.
# The tarball ships 88 already-unwrapped interferograms (cut_*.grd) with their
# correlation grids (corcut_*.grd), plus intf.tab and scene.tab. It therefore
# isolates `sbas` — the SBAS inversion — from all upstream processing.
#
# Python side: `sbas` resolves to utils/sbas, which dispatches to
# bin_py/sbas_py/sbas_ref.py. The csh side runs the same command with
# GMTSAR_SBAS_PY=0, forcing the C binary (CSH_ENTRY in case_runner.py runs the
# bundled runSBAS.csh).
#
# Flags match the bundled runSBAS.csh. -atm is deliberately absent: -atm n>=2
# has no reproducible reference in the C (docs/dev_notes/NOTES_SBAS.md).

sbas intf.tab scene.tab 88 28 700 1000 -rms -dem -smooth 1 -mmap
