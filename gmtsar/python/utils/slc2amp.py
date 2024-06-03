#! /usr/bin/env python3
"""
slc2amp is part of GMTSAR. 
slc2amp is migrated from slc2amp.csh by Dunyu Liu on 20231110.
slc2amp.csh was originally written on 20091123 by Xiaopeng Tong.

Purpose: to convert a complex SLC file to a real amplitude grd
  file using optional filter and a PRM file. 
"""

import sys
from gmtsar_lib import *


def slc2amp():
    """
    Usage: slc2amp.csh filein.PRM rng_dec fileout.grd

     run_dec is range decimation
     e.g., 1 for ERS ENVISAT ALOS FBD
           2 for ALOS FBS
           4 for TSX

    Example: slc2amp IMG-HH-ALPSRP055750660-H1.0__A.PRM 2 amp-ALPSRP055750660-H1.0__A.grd
    """
    print('SLC2AMP - START ... ...')
    print('SLC2AMP: input arguments are ', sys.argv)

    n = len(sys.argv)
    if n != 4:
        print('FILTER: Wrong # of input arguments; # should be 3 ... ...')
        print(slc2amp.__doc__)
        sys.exit()

    sharedir = '/usr/local/GMTSAR/share/gmtsar'
    filt1 = sharedir + '/filters/gauss5x3'
    filt2 = sharedir + '/filters/gauss9x5'
    print('SLC2AMP: define the filters, which are ', filt1, filt2)

    print(' SLC2AMP: filter the amplitudes done in conv ... ...')
    print(' SLC2AMP: check the input and output filename before ... ...')

    if (sys.argv[1].find('PRM') >= 0 or sys.argv[1].find('prm') >= 0) and sys.argv[3].find('grd') >= 0:
        print(' ')
        print('SLC2AMP: range decimation is ', sys.argv[2])
        conv('4 '+sys.argv[2]+' '+filt1+' ' +  # FIXME: Undefined variable
            sys.argv[1]+' '+sys.argv[3]+'=bf')
    else:
        print('SLC2AMP: wrong filename, exiting ... ...')

    print('SLC2AMP: get the zmin and zmax values ... ...')
    grdmath(sys.argv[3]+'=bf 1 MUL = '+sys.argv[3])

    print("SLC2AMP - END ... ...")


def _main_func(description):
    slc2amp()


if __name__ == "__main__":
    _main_func(__doc__)
