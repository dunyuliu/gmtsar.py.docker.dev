#! /usr/bin/env python3
"""
# snaphu.py is part of GMTSAR. 
# This Python script is migrated from snaphu.csh by Dunyu Liu on 20231109.
# snaphu.csh was originally written by X on X. 

# Purpose: to unwrap the phase.
"""

import sys
import subprocess
from gmtsar_lib import *


def snaphu():
    """
    snaphu.py - unwrap the phase.")
    if interp flag is invoked, unwrap the phase with nearest neighbor interpolating low coherence and blank pixels.
    Usage: snaphu.py correlation_threshold maximum_discontinuity interp [<rng0>/<rngf>/<azi0>/<azif>]

    correlation is reset to zero when < threshold 
    maximum_discontinuity enables phase jumps for earthquake ruptures, etc.
    set maximum_discontinuity = 0 for continuous phase such as interseismic
    interp=1, then calling nearest_grid to interpolate.

    Example: snaphu.py .12 40 1 1000/3000/24000/27000
    Reference:
    Chen C. W. and H. A. Zebker, Network approaches to two-dimensional phase unwrapping: intractability and two new algorithms, Journal of the Optical Society of America A, vol. 17, pp. 401-414 (2000).
    Agram, P. S., & Zebker, H. A. (2009). Sparse two-dimensional phase unwrapping using regular-grid methods. IEEE Geoscience and Remote Sensing Letters, 6(2), 327-331.
    """
    print('SNAPHU - START ... ...')
    n = len(sys.argv)
    print('SNAPHU: input arguments are ', sys.argv)

    if n == 1:
        print('SNAPHU: snaphu help information ... ...')
        print(snaphu.__doc__)
        sys.exit()

    if n < 4:
        print('FILTER: Wrong # of input arguments; # should be larger than 3 ... ...')
        print(snaphu.__doc__)

    interp = int(sys.argv[3])
    if interp == 1:
        print('SNAPHU: interp is activated; unwrap the phase with nearest neighbor interpolating low coherence and blank pixels.')
    else:
        print('SNAPHU: interp is NOT activated; unwrap the phase.')

    V = '-V'

    print('SNAPHU: prepare the files adding the correlation mask ... ...')
    if n == 5:
        grdcut('mask.grd -R'+sys.argv[4]+' -Gmask_patch.grd')
        grdcut('corr.grd -R'+sys.argv[4]+' -Gcorr_patch.grd')
        grdcut('phasefilt.grd -R'+sys.argv[4]+' -Gphase_patch.grd')
    else:
        file_shuttle('mask.grd', 'mask_patch.grd', 'link')
        file_shuttle('corr.grd', 'corr_patch.grd', 'link')
        file_shuttle('phasefilt.grd', 'phase_patch.grd', 'link')

    print(' ')
    print('SNAPHU: ceate landmask ... ...')

    if check_file_report('landmask_ra.grd') is True:
        if n == 5:
            par_tmp = subprocess.run(["gmt", "grdinfo", "-I", "phase_patch.grd"],
                                     stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
            print('SNAPHU: par_tmp is ', par_tmp)
            grdsample('landmask_ra.grd -R' +
                sys.argv[4]+' '+par_tmp+' -Glandmask_ra_patch.grd')
        else:
            if interp == 0:
                grdsample('landmask_ra.grd -Rphase_patch.grd -Glandmask_ra_patch.grd')
            elif interp == 1:
                par = catch_output_cmd(
                    ["gmt", "grdinfo", "-I", "phase_patch.grd"], False, -999, -100000)
                grdsample('landmask_ra.grd ' +
                    par+' -Glandmask_ra_patch.grd')
        print(' ')
        grdmath('phase_patch.grd landmask_ra_patch.grd MUL = phase_patch.grd '+V)

    print(' ')
    print('SNAPHU: user defined mask ... ...')

    if check_file_report('mask_def.grd') is True:
        if n == 5:
            grdcut('mask_def.grd -R' +
                sys.argv[4]+' -Gmask_def_patch.grd')
        else:
            file_shuttle('mask_def.grd', 'mask_def_patch.grd', 'cp')

        print(' ')
        grdmath('corr_patch.grd mask_def_patch.grd MUL = corr_patch.grd '+V)

    grdmath('corr_patch.grd ' +
        sys.argv[1]+' GE 0 NAN mask_patch.grd MUL = mask2_patch.grd')
    grdmath('corr_patch.grd 0. XOR 1. MIN  = corr_patch.grd')
    grdmath('mask2_patch.grd corr_patch.grd MUL = corr_tmp.grd')

    if interp == 0:
        grd2xyz('phase_patch.grd -ZTLf -do0 > phase.in')
    elif interp == 1:
        grdmath('mask2_patch.grd phase_patch.grd MUL = phase_tmp.grd')
        nearest_grid('phase_tmp.grd tmp.grd 300')
        file_shuttle('tmp.grd', 'phase_tmp.grd', 'mv')
        grd2xyz('phase_tmp.grd -ZTLf -do0 > phase.in')

    grd2xyz('corr_tmp.grd -ZTLf  -do0 > corr.in')

    print(' ')
    print('SNAPHU: run snaphu ... ...')

    sharedir = '/usr/local/GMTSAR/share/gmtsar'
    print(' ')
    print('SNAPHU: unwrapping phase with snaphu - higher threshold for faster unwrapping ... ...')

    par_tmp = catch_output_cmd(
        ["gmt", "grdinfo", "-C", "phase_patch.grd"], True, 10, -100000)
    # par_tmp = subprocess.run(["gmt","grdinfo","-C","phase_patch.grd"], stdout=subprocess.PIPE).stdout.decode('utf-8').strip().split()[9]
    print('SNAPHU: output from gmt grdinfo -C phase_patch.grd | cut -f 10 is ', par_tmp)

    if float(sys.argv[2]) == 0:
        run('snaphu phase.in '+par_tmp+' -f '+sharedir +  # FIXME: use arguments to make recursive call
            '/snaphu/config/snaphu.conf.brief -c corr.in -o unwrap.out -v -s -g conncomp.out')
    else:
        print('SNAPHU: replacing the line containing DEFOMAX_CYCLE to DEFOMAX_CYCLE $2 from snaphu.conf.brief... ...')
        file_shuttle(sharedir+'/snaphu/config/snaphu.conf.brief',
                     'snaphu.conf.brief', 'cp')
        replace_strings('snaphu.conf.brief', 'DEFOMAX_CYCLE',
                        'DEFOMAX_CYCLE '+sys.argv[2])
        run('snaphu phase.in '+par_tmp +
            ' -f snaphu.conf.brief -c corr.in -o unwrap.out -v -d -g conncomp.out')

    print(' ')
    print('SNAPHU: convert to grd ... ...')

    par1 = catch_output_cmd(
        ["gmt", "grdinfo", "-I-", "phase_patch.grd"], False, 0, -100000)
    par2 = catch_output_cmd(
        ["gmt", "grdinfo", "-I", "phase_patch.grd"], False, 0, -100000)
    print('SNAPHU: output from gmt grdinfo -I- phase_patch.grd is', par1)
    print('SNAPHU: output from gmt grdinfo -I phase_patch.grd is', par2)

    xyz2grd('unwrap.out -ZTLf -r '+par1+' '+par2+' -Gtmp.grd')
    print(' ')
    print('SNAPHU: generate connected component ... ...')
    xyz2grd('conncomp.out -ZTLu -r '+par1+' '+par2+' -Gconncomp.grd')
    grdmath('tmp.grd mask2_patch.grd MUL = tmp.grd')

    print(' ')
    print('SNAPHU: detrend the unwrapped if DEFOMAX = 0 for interseismic ... ...')
    file_shuttle('tmp.grd', 'unwrap.grd', 'mv')

    print(' ')
    print('SNAPHU: landmask ... ...')
    if check_file_report('landmask_ra.grd') is True:
        grdmath('unwrap.grd landmask_ra_patch.grd MUL = tmp.grd '+V)
        file_shuttle('tmp.grd', 'unwrap.grd', 'mv')

    print(' ')
    print('SNAPHU: user defined mask ... ...')
    if check_file_report('mask_def.grd') is True:
        grdmath('unwrap.grd mask_def_patch.grd MUL = tmp.grd '+V)
        file_shuttle('tmp.grd', 'unwrap.grd', 'mv')

    print(' ')
    print('SNAPHU: plot the unwrapped phase ... ...')

    grdgradient('unwrap.grd -Nt.9 -A0. -Gunwrap_grad.grd')
    tmp = catch_output_cmd(
        ["gmt", "grdinfo", "-C", "-L2", "unwrap.grd"], True, -999, -100000)
    print('SNAPHU: output from cmd gmt grdinfo -C -L2 unwrap.grd is',
          tmp, 'which should be a list')
    limitU = float(tmp[11])+float(tmp[12])*2.
    limitU = round(limitU, 1)
    limitL = float(tmp[11])-float(tmp[12])*2.
    limitL = round(limitL, 1)
    std = round(float(tmp[12]), 1)  # FIXME: variable is never used
    makecpt('-Cseis -I -Z -T'+'''"'''+str(limitL) +
        '''"/"'''+str(limitU)+'''"/1 -D > unwrap.cpt''')

    if interp == 1:
        tmp1 = catch_output_cmd(
            ["gmt", "grdinfo", "unwrap.grd", "-C"], True, -999, -100000)
        print('SNAPHU: output from cmd gmt grdinfo unwrap.grd -C is',
              tmp1, 'which should be a list')
        boundR = (float(tmp1[2])-float(tmp1[1]))/4  # FIXME: Varibles are not used
        boundA = (float(tmp1[4])-float(tmp1[3]))/4

    grdimage('unwrap.grd -Iunwrap_grad.grd -Cunwrap.cpt -JX6.5i -Bxaf+lRange -Byaf+lAzimuth -BWSen -X1.3i -Y3i -P -K > unwrap.ps')
    psscale('-Runwrap.grd -J -DJTC+w5/0.2+h+e -Cunwrap.cpt -Bxaf+l"Unwrapped phase" -By+lrad -O >> unwrap.ps''')
    psconvert('-Tf -P -A -Z unwrap.ps')

    print(' ')
    print('SNAPHU: unwrapped phase map: unwrap.pdf ... ...')

    print(' ')
    print('SNAPHU: clean up ... ...')

    run(' -f tmp.grd corr_tmp.grd unwrap.out tmp2.grd unwrap_grad.grd conncomp.out')
    run(' -f phase.in corr.in')

    if interp == 1:
        run(' -f phase_tmp.grd')
        file_shuttle('phase_patch.grd', 'phasefilt_interp.grd', 'mv')

    if n == 5:
        file_shuttle('corr_patch.grd', 'corr_cut.grd', 'mv')
    run(' -f mask_patch.grd mask3.grd mask3.out')
    run(' -f corr_cut.grd corr_patch.grd')

    print("SNAPHU - END ... ...")


def _main_func(description):
    snaphu()


if __name__ == "__main__":
    _main_func(__doc__)
