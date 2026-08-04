#!/usr/bin/env python3
"""sbas_ref.py -- scalar, correctness-first port of gmtsar/sbas.c (Tong 2014).

Deliberately literal. Every quirk of the C is reproduced, including the ones
that look like bugs, because the oracle is the C binary's output and not our
opinion of what it should compute (project_rules.md Rule 7: port verbatim
FIRST, optimize afterwards).

Quirks preserved on purpose:
  * `flag` is set when the phase is NaN, and the C then solves the pixel only
    when flag != 1 -- so the mask is "no interferogram was NaN here".
  * vel is fit over all S scenes, but the RMS sum runs i=2..S-3 while its own
    sumxx/sumx/sumy came from i=0..S-1. Inconsistent, and reproduced.
  * disp[0] is always 0 (the inner cumulative loop `for p in range(i)`).
  * -79.58 is the C's truncated 1000/(4*pi); NOT recomputed exactly.
  * jpvt is allocated ONCE and never reset between pixels, exactly as the C
    does (sbas_utils.c:179 Malloc, no memset in the k/j loop at :430). LAPACK
    reads a nonzero JPVT(i) as "column i is fixed", so after the second call
    every column is fixed and column pivoting is OFF for the rest of the grid.
    This is a real defect in the C -- see docs/dev_notes/NOTES_SBAS.md --
    but it IS the reference behaviour, so the port reproduces it. Resetting
    jpvt per pixel changes 11.1% of pixels by up to 5.35 mm/yr.

Matches: sbas intf.tab scene.tab N S xdim ydim -rms -dem -smooth SF -mmap
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import scipy.linalg.lapack as lapack
import xarray as xr

# the C's truncated constant (sbas_utils.c) -- do not "fix" to 1000/(4*pi)
C_MM = -79.58
RCOND = 1e-3


def read_tables(intf_tab: str, scene_tab: str, N: int, S: int):
    L, time = [], []
    with open(scene_tab) as f:
        for line in f:
            p = line.split()
            if len(p) < 2:
                continue
            L.append(int(p[0]))
            time.append(float(p[1]))
    if len(L) != S:
        sys.exit("S and number of the SAR scenes don't match!")
    time = np.asarray(time, dtype=np.float64)
    time = time - time[0]

    gfile, cfile, H, bperp = [], [], [], []
    with open(intf_tab) as f:
        for line in f:
            p = line.split()
            if len(p) < 5:
                continue
            gfile.append(p[0]); cfile.append(p[1])
            H.append((int(p[2]), int(p[3])))
            bperp.append(float(p[4]))
    if len(gfile) != N:
        sys.exit("N and number of interferograms don't match!")
    return (np.asarray(L, dtype=np.int64), time, gfile, cfile,
            np.asarray(H, dtype=np.int64), np.asarray(bperp, dtype=np.float32))


def read_grids(gfile, cfile, xdim, ydim):
    """phi[y,x,i], var[y,x,i], flag[y,x]. var per Rosen et al. 2000."""
    N = len(gfile)
    phi = np.empty((ydim, xdim, N), dtype=np.float32)
    var = np.empty((ydim, xdim, N), dtype=np.float32)
    flag = np.zeros((ydim, xdim), dtype=np.int64)
    for i in range(N):
        g = xr.open_dataarray(gfile[i]).values.astype(np.float32)
        c = xr.open_dataarray(cfile[i]).values.astype(np.float32)
        if g.shape != (ydim, xdim) or c.shape != (ydim, xdim):
            sys.exit(f"dimension don't match! {gfile[i]}")
        phi[:, :, i] = g
        flag[np.isnan(g)] = 1
        v = np.where((c >= 1e-2) & (c <= 0.99), np.sqrt((1.0 - c * c) / (c * c)),
                     np.where(c < 1e-2, 99.99, 0.1))
        var[:, :, i] = v.astype(np.float32)
    return phi, var, flag


def build_G(N, S, m, n, L, H, time, sf, bperp, scale, base=None):
    """G: (N+S-2) x S. Rows 0..N-1 interferograms + bperp column; rest smoothing.

    C's init_G_ts NEVER clears G -- it only writes the 1s, the bperp column and
    the smoothing rows. Inside the -atm loop init_array_ts (which does zero G) is
    not called, so iteration kk>=2 writes on top of the LAPACK-destroyed matrix
    left by the previous iteration's last dgelsy. `base` reproduces that."""
    G = np.zeros((m, n), dtype=np.float64) if base is None else np.array(base, dtype=np.float64, copy=True)
    for i in range(N):
        for j in range(S - 1):
            if H[i, 0] <= L[j] < H[i, 1]:
                G[i, j] = 1.0
        G[i, n - 1] = bperp[i] * scale
    for i in range(S - 2):
        G[i + N, i] = sf / (time[i + 1] - time[i])
        G[i + N, i + 1] = -sf / (time[i + 2] - time[i + 1])
    return G


def solve(xdim, ydim, S, N, m, n, A, phi, var, flag, time, wl, want_rms, want_dem,
          atm_rms=None, flag_robust=False, jpvt_state=None, disp=None, g_state=None):
    # Allocated ONCE for the whole program in C (sbas_utils.c:179) and mutated by
    # every dgelsy call -- including across the several solves the -atm branch
    # performs. Caller passes a persistent list so the state survives between
    # solve() invocations, exactly as the C's single malloc does.
    if g_state is None:
        g_state = [None]
    if jpvt_state is None:
        jpvt_state = [np.zeros(n, dtype=np.int32)]
    jpvt = jpvt_state[0]
    lwork = max(1, m * n + max(m * n, 1) * 16)   # the C's lwork
    # C never re-zeroes disp inside the -atm loop (sbas.c: disp[i]=0.0 only at
    # :236 and :405), and lsqlin ACCUMULATES: disp[...] = disp[...] + d[p].
    # So successive atm iterations sum onto the previous one. Caller supplies a
    # persistent array to reproduce that; None means a fresh zeroed one.
    if disp is None:
        disp = np.zeros((S, ydim, xdim), dtype=np.float32)
    vel = np.full((ydim, xdim), np.nan, dtype=np.float32)
    res = np.full((ydim, xdim), np.nan, dtype=np.float32)
    dem = np.full((ydim, xdim), np.nan, dtype=np.float32)

    if atm_rms is None:
        atm_rms = np.zeros(S, dtype=np.float64)
    # C counts scenes eligible for the robust fit, excluding the two at each end
    count = sum(1 for i in range(S) if atm_rms[i] != 0.0 and i not in (0, 1, S - 1, S - 2))
    rank_reported = False
    for k in range(ydim):
        for j in range(xdim):
            if flag[k, j] == 1:
                disp[:, k, j] = np.nan
                continue
            w = var[k, j, :].astype(np.float64)
            G = A.copy()
            G[:N, :] = A[:N, :] / w[:, None]
            d = np.zeros(m, dtype=np.float64)
            d[:N] = phi[k, j, :].astype(np.float64) / w

            Gdestroyed, x, jpvt_out, rank, _ = lapack.dgelsy(G, d, jpvt, RCOND, lwork)
            g_state[0] = Gdestroyed   # dgelsy overwrites A in place, as in C
            jpvt = jpvt_out.astype(np.int32)   # carried to the next pixel, as in C
            jpvt_state[0] = jpvt               # and to the next solve() call
            sol = x[:n]
            if not rank_reported:
                print(f"matrix is {'full rank' if rank == n else 'rank-deficient'}: {rank}\n")
                rank_reported = True

            disp[:, k, j] += np.cumsum(np.concatenate(([0.0], sol[:S - 1])))[:S].astype(np.float32)
            if want_dem:
                dem[k, j] = sol[n - 1]

            dk = disp[:, k, j].astype(np.float64)
            if count > 2 and flag_robust:
                # robust branch: only scenes 2..S-3 with a nonzero atm_rms
                sel = np.array([i for i in range(2, S - 2) if atm_rms[i] != 0.0], dtype=np.int64)
                sumxy = float((time[sel] * dk[sel]).sum()); sumxx = float((time[sel] ** 2).sum())
                sumy = float(dk[sel].sum()); sumx = float(time[sel].sum())
                slope = (count * sumxy - sumx * sumy) / (count * sumxx - sumx * sumx)
                vel[k, j] = C_MM * wl * slope * 365.0
                if want_rms:
                    aa = sumy / count - slope * sumx / count
                    sumyy = float(((dk[sel] - time[sel] * vel[k, j] / (C_MM * wl * 365) - aa) ** 2).sum())
                    res[k, j] = np.sqrt(count * sumyy / ((count - 2) * (count * sumxx - sumx * sumx))) * (-C_MM * wl * 365)
            else:
                sumxy = float((time * dk).sum()); sumxx = float((time * time).sum())
                sumy = float(dk.sum()); sumx = float(time.sum())
                slope = (S * sumxy - sumx * sumy) / (S * sumxx - sumx * sumx)
                vel[k, j] = C_MM * wl * slope * 365.0
                if want_rms:
                    aa = sumy / S - slope * sumx / S
                    # NOTE: i=2..S-3 here while the sums above used 0..S-1 -- as in C
                    sumyy = float(((dk[2:S - 2] - time[2:S - 2] * vel[k, j] / (C_MM * wl * 365) - aa) ** 2).sum())
                    res[k, j] = np.sqrt(S * sumyy / ((S - 2) * (S * sumxx - sumx * sumx))) * (-C_MM * wl * 365)
    return disp, vel, res, dem



# ---------------------------------------------------------------- -atm branch
# Common-point stacking APS estimation (sbas.c n_atm != 0). Ported verbatim
# from sbas_utils.c: sum_intfs, connect, compute_noise, apply_screen,
# remove_ts, rank_double.

def build_hit(L, H, N, S):
    """hit[i,j]=1 when some interferogram runs from scene i to scene j."""
    hit = np.zeros((S, S), dtype=np.int64)
    for i in range(N):
        k1 = k2 = 0
        for j in range(S):
            if H[i, 0] == L[j]:
                k1 = j
            if H[i, 1] == L[j]:
                k2 = j
        hit[k1, k2] = 1
    return hit


def connect(L, H, time, hit, N, S, n, mode):
    """mark[i] in {-1,0,1}: which interferograms touch scene n, and with which sign.
    mode=0 all connections, mode=1 only those with a time-symmetric partner."""
    mark = np.zeros(N, dtype=np.int64)
    for i in range(S):
        if hit[i, n] == 1:
            for j in range(N):
                if L[i] == H[j, 0] and L[n] == H[j, 1]:
                    mark[j] = -1
        if hit[n, i] == 1:
            for j in range(N):
                if L[n] == H[j, 0] and L[i] == H[j, 1]:
                    mark[j] = 1
    if mode == 1:
        for i in range(S):
            if hit[i, n] == 1:
                j = n
                while j < S:
                    if hit[n, j] == 1 and abs((time[n] - time[i]) - (time[j] - time[n])) < 5:
                        break
                    j += 1
                if j == S:
                    for j in range(N):
                        if L[i] == H[j, 0] and L[n] == H[j, 1]:
                            mark[j] = 0
            if hit[n, i] == 1:
                j = 0
                while j < n:
                    if hit[j, n] == 1 and abs((time[n] - time[j]) - (time[i] - time[n])) < 5:
                        break
                    j += 1
                if j == n:
                    for j in range(N):
                        if L[n] == H[j, 0] and L[i] == H[j, 1]:
                            mark[j] = 0
    return mark


def sum_intfs(phi, mark, xdim, ydim, N):
    """screen = -sum_n phi[...,n]*mark[n]/sum|mark|   (float32 accumulation, as C)."""
    ssum = int(np.abs(mark).sum())
    screen = np.zeros((ydim, xdim), dtype=np.float32)
    if ssum != 0:
        for n in range(N):
            if mark[n] == 0:
                continue
            screen += (-phi[:, :, n] * np.float32(mark[n]) / np.float32(ssum)).astype(np.float32)
    return screen


def compute_noise(screen):
    """C returns 0.0 when the finite sum is exactly 0 -- reproduced."""
    f = np.isfinite(screen)
    n = int(f.sum())
    if n == 0:
        return 0.0
    ssum = float(screen[f].astype(np.float64).sum())
    if ssum == 0.0:
        return 0.0
    mean = ssum / n
    rms = float((((screen[f].astype(np.float64) - mean) ** 2).sum()) / n)
    return np.sqrt(rms)


def apply_screen(screen, phi, N, mark):
    for n in range(N):
        if mark[n] != 0:
            phi[:, :, n] += (screen * np.float32(mark[n])).astype(np.float32)


def remove_ts(phi, ts, N, S, H, L):
    """subtract the modelled displacement of each pair from its interferogram."""
    for n in range(N):
        h1 = h2 = 0
        for i in range(S):
            if H[n, 0] == L[i]:
                h1 = i
            if H[n, 1] == L[i]:
                h2 = i
        phi[:, :, n] -= (ts[h2] - ts[h1]).astype(np.float32)


def rank_double(nums, n):
    """Order indices by descending |value|; exact zeros are appended in index
    order at the end. Mirrors the C's two-pass construction."""
    nums2 = np.array(nums, dtype=np.float64, copy=True)
    mark = (nums2 == 0.0).astype(np.int64)
    seq = np.zeros(n, dtype=np.int64)
    filled = 0
    for i in range(n):
        rec = 0.0; recn = -1
        for j in range(n):
            if rec < abs(nums2[j]):
                rec = abs(nums2[j]); recn = j
        if rec != 0.0:
            seq[i] = recn; nums2[recn] = 0.0; filled = i + 1
        else:
            break
    recn = int(mark.sum())
    for i in range(recn):
        for j in range(n):
            if mark[j] != 0:
                seq[n - recn + i] = j; mark[j] = 0; break
    return seq


def smoothing_ramp(sf, n_atm):
    """sfs[0]=1000, sfs[n_atm]=sf, geometric ramp between (sbas.c:262-278)."""
    EE = 2.718281828459046
    sfs = np.zeros(n_atm + 2, dtype=np.float64)
    sfs[0] = 1000.0
    sfs[n_atm] = sf
    if n_atm >= 2:
        if sf > 0:
            bb = (np.log(1000) - np.log(sf)) / float(n_atm)
            aa = EE ** (np.log(sf) - bb)
        else:
            bb = (np.log(1000) - np.log(0.01)) / float(n_atm)
            aa = EE ** (np.log(0.01) - bb)
        for i in range(1, n_atm):
            sfs[n_atm - i] = aa * (EE ** (bb * float(i + 1)))
    return sfs


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("intf_tab"); ap.add_argument("scene_tab")
    ap.add_argument("N", type=int); ap.add_argument("S", type=int)
    ap.add_argument("xdim", type=int); ap.add_argument("ydim", type=int)
    ap.add_argument("-smooth", type=float, default=0.0)
    ap.add_argument("-wavelength", type=float, default=0.236)
    ap.add_argument("-incidence", type=float, default=37.0)
    ap.add_argument("-range", dest="rng", type=float, default=866000.0)
    ap.add_argument("-rms", action="store_true")
    ap.add_argument("-dem", action="store_true")
    ap.add_argument("-mmap", action="store_true", help="accepted, ignored (memory strategy only)")
    ap.add_argument("-atm", type=int, default=0, metavar="n_atm",
                    help="APS estimation by common-point stacking, n iterations")
    ap.add_argument("-robust", action="store_true",
                    help="robust velocity fit; only active with -atm (C forces it off otherwise)")
    a = ap.parse_args(argv)

    N, S, xdim, ydim = a.N, a.S, a.xdim, a.ydim
    m, n = N + S - 2, S
    scale = 4.0 * np.pi / a.wavelength / a.rng / np.sin(a.incidence / 180.0 * np.pi)

    print("read table file ...")
    L, time, gfile, cfile, H, bperp = read_tables(a.intf_tab, a.scene_tab, N, S)
    print(f"number of SAR scenes is {S} ", file=sys.stderr)
    print(f"number of interferograms is {N} ", file=sys.stderr)
    print("read phase and correlation grids ...")
    phi, var, flag = read_grids(gfile, cfile, xdim, ydim)
    print(f"{a.smooth:.6f} {scale:.6f} {time[0]:.6f} {bperp[0]:.6f}")

    jpvt_state = [np.zeros(n, dtype=np.int32)]   # one allocation for the whole run
    n_atm = a.atm
    flag_robust = a.robust and n_atm != 0     # C: n_atm==0 forces flag_robust=0
    atm_rms = np.zeros(S, dtype=np.float64)

    if n_atm == 0:
        print("fill the G matrix ...")
        A = build_G(N, S, m, n, L, H, time, a.smooth, bperp, scale)
        print(f"run least-squares problem over {xdim} by {ydim} pixel (0) ...")
        disp, vel, res, dem = solve(xdim, ydim, S, N, m, n, A, phi, var, flag,
                                    time, a.wavelength, a.rms, a.dem, atm_rms, False, jpvt_state)
    else:
        print("\n\nApplying atmospheric correction by common point stacking...\n",
              file=sys.stderr)
        sfs = smoothing_ramp(a.smooth, n_atm)
        hit = build_hit(L, H, N, S)
        print("\n\n\nHit Matrix:", file=sys.stderr)
        for i in range(S):
            print(f"{L[i]} " + " ".join(str(int(v)) for v in hit[i]), file=sys.stderr)
        print("\n", file=sys.stderr)

        screen = np.zeros((S, ydim, xdim), dtype=np.float32)
        atm_rank = np.arange(S, dtype=np.int64)
        disp = np.zeros((S, ydim, xdim), dtype=np.float32)   # persists across iterations
        vel = res = dem = None
        g_state = [None]                                     # LAPACK-destroyed G carry-over

        print("Applying exponential relaxation on smoothing parameters", file=sys.stderr)
        tmp_phi = phi.copy()
        for kk in range(1, n_atm + 1):
            sf_k = sfs[kk - 1]                      # C: sfs[kk-1], not sfs[kk]
            print(f"\nSetting smoothing parameter to {sf_k:f}...", file=sys.stderr)
            # NOT base=g_state[0]: C builds on the LAPACK-destroyed G here, which
            # is not portably reproducible (see NOTES). Clean build; -atm n>=2
            # therefore does not reach parity and is documented as unsupported.
            A = build_G(N, S, m, n, L, H, time, sf_k, bperp, scale)
            atm_rms[:] = 0.0                        # reset before every loop solve
            print("Computing deformation time-series...", file=sys.stderr)
            disp, vel, res, dem = solve(xdim, ydim, S, N, m, n, A, tmp_phi, var, flag,
                                        time, a.wavelength, a.rms, a.dem, atm_rms, flag_robust,
                                        jpvt_state, disp, g_state)
            if kk > 1:
                tmp_phi = phi.copy()
            remove_ts(tmp_phi, disp, N, S, H, L)

            if kk == 1:
                for i in range(S):
                    mark = connect(L, H, time, hit, N, S, i, 1)
                    ts_ = sum_intfs(phi, mark, xdim, ydim, N)
                    atm_rms[i] = compute_noise(ts_)
                    screen[i] = ts_
                atm_rank = rank_double(atm_rms, S)

            for i in range(S):
                r = int(atm_rank[i])
                mark = connect(L, H, time, hit, N, S, r, 1)
                ts_ = sum_intfs(tmp_phi, mark, xdim, ydim, N)
                atm_rms[r] = compute_noise(ts_)
                screen[r] = ts_
                mark = connect(L, H, time, hit, N, S, r, 0)
                apply_screen(ts_, tmp_phi, N, mark)
            atm_rank = rank_double(atm_rms, S)

            print("Applying atmospheric phase screen to original unwrapped phase...", file=sys.stderr)
            tmp_phi = phi.copy()
            for i in range(S):
                mark = connect(L, H, time, hit, N, S, i, 0)
                apply_screen(screen[i], tmp_phi, N, mark)

        sf_final = sfs[n_atm]
        print(f"Setting smoothing parameter to {sf_final:f}...", file=sys.stderr)
        A = build_G(N, S, m, n, L, H, time, sf_final, bperp, scale)
        cnt = sum(1 for i in range(S) if atm_rms[i] != 0.0 and i not in (0, 1, S - 1, S - 2))
        print(f"run least-squares problem over {xdim} by {ydim} pixel ({cnt}) ...")
        disp = np.zeros((S, ydim, xdim), dtype=np.float32)   # C zeroes it here (sbas.c:405)
        disp, vel, res, dem = solve(xdim, ydim, S, N, m, n, A, tmp_phi, var, flag,
                                    time, a.wavelength, a.rms, a.dem, atm_rms, flag_robust,
                                    jpvt_state, disp)

    print("write output ...")
    ref = xr.open_dataarray(gfile[0])
    def w(arr, name):
        # GMT grids name the data variable "z"; an unnamed DataArray would be
        # written as __xarray_dataarray_variable__ and break every gmt tool.
        da = xr.DataArray(arr, coords=ref.coords, dims=ref.dims, name="z")
        da.to_netcdf(name)
    # C converts phase -> mm only at write time (sbas_utils.c write_output_ts:
    # grdin[...] = -79.58 * wl * disp[...]); disp is held in phase units internally.
    for i in range(S):
        w((C_MM * a.wavelength * disp[i]).astype(np.float32), f"disp_{L[i]:07d}.grd")
    if n_atm != 0:
        for i in range(S):
            w(screen[i].astype(np.float32), f"aps_{L[i]:07d}.grd")
    w(vel, "vel.grd")
    if a.rms:
        w(res, "rms.grd")
    if a.dem:
        w(dem, "dem_err.grd")
    return 0


if __name__ == "__main__":
    sys.exit(main())
