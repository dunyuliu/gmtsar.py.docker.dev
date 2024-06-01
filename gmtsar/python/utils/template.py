#! /usr/bin/env python3
"""
# landmask is part of GMTSAR. 
# This Python script is migrated from landmask.csh by Dunyu Liu on 20230914.
# Purpose: to make a landmask
"""

import sys
from gmtsar_lib import *


def landmask():
    """
    Usage: landmask region_cut[0/10600/0/27648]")

     make a landmask in radar coordinates, needs to run with trans.dat.")

     NOTE: The region_cut can be specified in batch.config file.")
     decimation - (1) better resolution, (2) smaller files")
    """
    print('LANDMASK - START ... ...')
    n = len(sys.argv)
    if n != 2:
        print('FILTER: Wrong # of input arguments; # should be 1 ... ...')
        print(landmask.__doc__)

    print("LANDMASK - END ... ...")


def _main_func(description):
    landmask()


if __name__ == "__main__":
    _main_func(__doc__)
