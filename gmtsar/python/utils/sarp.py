#! /usr/bin/env python3
"""
# sarp is part of GMTSAR. 
# It is migrated from sarp.csh, originally written by David Sandwell, Feb, 2010.
# Dunyu Liu, 20230424.

# Purpose: to focus SAR data and deal with negative yshift
# Syntax: ??
"""
import sys
import shutil
from gmtsar_lib import *


def sarp():
    """
    Usage: sarp.csh file.PRM

    Example: sarp.csh IMG-HH-ALPSRP049040660-H1.0__A.PRM
    """
    numOfArg = len(sys.argv)
    if numOfArg < 2:
        print(sarp.__doc__)
        sys.exit()
    slcfile = sys.argv[1][0:-3]+'SLC'
    print("SARP: slcfile is ", slcfile)

    esarp(sys.argv[1]+' '+slcfile+' > tmp_sarp')
    print("SARP: update the PRM file")

    with open(sys.argv[1], 'r') as f:
        lines = f.readlines()
    with open('tmp.PRM', 'w') as f:
        for line in lines:
            if 'SLC_file' not in line and 'dtype' not in line:
                f.write(line)

    shutil.move('tmp.PRM', sys.argv[1])
    with open(sys.argv[1], 'a') as f:
        f.write(f'SLC_file = {slcfile}\n')
        if numOfArg > 4 and sys.argv[3] == 'R4':
            f.write('dtype = c\n')
        else:
            f.write('dtype = a\n')

    print("SARP: put in dfact into PRM file")
    dfact = grep_value('tmp_sarp', 'I2SCALE', 2)
    update_prm(sys.argv[1]+' SLC_scale '+str(dfact))
    delete('tmp_sarp')
    print('SARP: Finishing sarp ... ...')


def _main_func(description):
    sarp()


if __name__ == "__main__":
    _main_func(__doc__)
