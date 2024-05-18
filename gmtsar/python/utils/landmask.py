#! /usr/bin/env python3
"""
landmask is part of GMTSAR. 
This Python script is migrated from landmask.csh by Dunyu Liu on 20230914.
Purpose: to make a landmask
"""

import sys
from gmtsar_lib import *


def landmask():
    """
    Usage: landmask region_cut[0/10600/0/27648]

    make a landmask in radar coordinates, needs to run with trans.dat.

    NOTE: The region_cut can be specified in batch.config file.
    decimation - (1) better resolution, (2) smaller files
    """
    print('LANDMASK - START ... ...')
    n = len(sys.argv)
    if n != 2:
        print('FILTER: Wrong # of input arguments; # should be 1 ... ...')
        print(landmask.__doc__)

    print(' ')
    print("LANDMASK: check if ~/.quiet file exists ... ...")
    if check_file_report('~/.quiet') is True:  # FIXME: if check_file_report('~/.quiet'): is better.
        # Also, this seems to be something that is called quite frequently. It could be an environment
        # variable that gets evaluated when the module is imported.
        V = ''
    else:
        V = '-V'
    print('LANDMASK: flag V is ', V)

    print(' ')
    print('LANDMASK: require full resolution coastline from GMT ... ...')
    run("gmt grdlandmask -Glandmask.grd `gmt grdinfo -I- dem.grd` `gmt grdinfo -I dem.grd` "+str(V)+" -NNaN/1 -Df")
    run("proj_ll2ra.csh trans.dat landmask.grd landmask_ra.grd")
    run("gmt grdsample landmask_ra.grd -Gtmp.grd -R" +
        sys.argv[1]+" -I4/8 -nl+t0.1")
    file_shuttle('tmp.grd', 'landmask_ra.grd', 'mv')

    print(' ')
    print('LANDMASK: if the landmask region is smaller than the region_cut pad with NaN ... ...')
    run('gmt grd2xyz landmask_ra.grd -bo > landmask_ra.xyz')
    run("gmt xyz2grd landmask_ra.xyz -bi -r -R" +
        sys.argv[1]+" `gmt grdinfo -I landmask_ra.grd` -Gtmp.grd")
    file_shuttle('tmp.grd', 'landmask_ra.grd', 'mv')

    print(' ')
    print('LANDMASK: cleanup ... ...')
    delete('landmask.grd')
    delete('landmask_ra.xyz')

    print("LANDMASK - END ... ...")


def _main_func(description):
    landmask()


if __name__ == "__main__":  # FIXME: modify to accept function perameters and allow imports
    _main_func(__doc__)
