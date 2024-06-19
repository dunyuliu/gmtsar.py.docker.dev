#! /usr/bin/env python3
"""
intf is part of GMTSAR. 
It is migrated from intf.csh.
Originally written by Xiaopeng Tong Feb 4 2021, 
then by Matt Wei May 4 2010 for ENVISAT,
then add in TSX, Jan 10, 2014.

Dunyu Liu, 20230426.

Purpose: to make the interferogram
Syntax: ??
"""

import sys
import subprocess
from gmtsar_lib import *


def extractSatBaselineOutputToPrm(refPrm, repPrm):
    # csh command: SAT_baseline $1 $2 | tail -n9 >> $2
    out = subprocess.run(['SAT_baseline', refPrm, repPrm],
                         stdout=subprocess.PIPE)
    output = out.stdout.decode('utf-8').split('\n')[-10:]
    print('INTF: SAT_baseline $1 $2 output is ', out)
    print('INTF: tail -n9 the above output is ', output)
    print('INTF: insert the tail results to file ', repPrm)
    with open(repPrm, 'a') as f:
        f.write('\n'.join(output))

    # csh command: SAT_baseline $1 $1 | grep height >> $1
    out = subprocess.run(['SAT_baseline', refPrm, refPrm],
                         stdout=subprocess.PIPE)
    output = out.stdout.decode('utf-8')
    output = '\n'.join(line for line in output.split('\n') if 'height' in line)
    with open(refPrm, 'a') as f:
        f.write(output)


def intf():
    """
    Usage: intf ref.PRM rep.PRM [-topo topogrd] [-model modelgrd]

    The dimensions of topogrd and modelgrd should be compatible with SLC file.

    Example: intf IMG-HH-ALPSRP055750660-H1.0__A.PRM IMG-HH-ALPSRP049040660-H1.0__A.PRM -topo topo_ra.grd
    """
    gmtset('IO_NC4_CHUNK_SIZE classic')

    n = len(sys.argv)
    arg = sys.argv[1:]  # put all the arguments to a list, arg
    # if the # of args is less than 2 (which is n==3 in Python), print error message.
    if n < 3:
        print('FILTER: Wrong # of input arguments; # should be <2 ... ...')
        print(intf.__doc__)
    refPrm = sys.argv[1]
    repPrm = sys.argv[2]

    SC = int(grep_value(refPrm, 'SC_identity', 3))
    print('INTF: Retrieve SC_identity = ', SC,
          ' from the 1st arg ref.PRM ... ...')
    print('INTF: dealing scenarios with different SC ... ...')

    if SC in (1, 2, 4, 5, 6):
        file_shuttle(repPrm, repPrm+'0', 'cp')
        file_shuttle(refPrm, refPrm+'0', 'cp')
        extractSatBaselineOutputToPrm(refPrm, repPrm)
    elif SC > 6:
        file_shuttle(repPrm, repPrm+'0', 'cp')
        file_shuttle(refPrm, refPrm+'0', 'cp')
        extractSatBaselineOutputToPrm(refPrm, repPrm)
    else:
        print('INTF: ERROR: incorrect satellite id in prm file ... ...')

    print('INTF: form the interferogram optionally using topo_ra and modelphase ... ...')
    if n in (3, 5, 7):
        phasediff(' '.join(arg[:n-1]))
    else:
        print(intf.__doc__)

    file_shuttle(refPrm+'0', refPrm, 'mv')
    file_shuttle(repPrm+'0', repPrm, 'mv')
    print("INTF: finishing intf ... ...")


def _main_func(description):
    intf()


if __name__ == "__main__":  # FIXME: This should be changed to work as a funciton call to intf()
    _main_func(__doc__)
