#! /usr/bin/env python3
"""
grd2kml is part of GMTSAR. 
This Python script is migrated from grd2kml.csh by Dunyu Liu on 20231109.
grd2kml.csh was originally written by David Sandwell on 20100210. 

Purpose: to convert a grd file to a kml file for Google Earth.
"""

import sys
import subprocess
from gmtsar_lib import *

# FIXME: Remove unused imports


def grd2kml():
    """
    "Usage: grd2kml.csh grd_file_stem cptfile [-R<west>/<east>/<south>/<north>]

    Example: grd2kml.csh phase phase.cpt
    """

    print('GRD2KML - START ... ...')
    n = len(sys.argv)
    print('GRD2KML: input arguments are ', sys.argv)

    if n < 3 or n > 4:  # FIXME: If the function is implimented to take its own parameters, it will never need this
        print('GRD2KML: Wrong # of input arguments; # should be less 2/3 ... ...')
        print(grd2kml.__doc__)

    V = '-V'
    VS = '-S -V'

    DX = subprocess.run(["gmt", "grdinfo", sys.argv[1]+".grd", "-C"],
                        stdout=subprocess.PIPE).stdout.decode('utf-8').strip().split()[7]
    print('GRD2KML: DX is ', DX)
    DPI = subprocess.run(["gmt", "gmtmath", "-Q", DX, "INV", "RINT", "="],
                         stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
    print('GRD2KML: DPI is ', DPI)

    gmtset('COLOR_MODEL = hsv')
    gmtset('PS_MEDIA = A2')

    if n == 4:
        grdimage(sys.argv[1]+'.grd -C'+sys.argv[2]+' ' +
            sys.argv[3]+' -Jx1id -P -Y2i -X2i -Q '+V+' > '+sys.argv[1]+'.ps')
    elif n == 3:
        grdimage(sys.argv[1]+'.grd -C'+sys.argv[2] +
            ' -Jx1id -P -Y2i -X2i -Q '+V+' > '+sys.argv[1]+'.ps')

    print('GRD2KML: now make the kml and png ... ...')
    print('GRD2KML: make '+sys.argv[1]+'.kml and '+sys.argv[1]+'.png ... ...')

    psconvert(sys.argv[1]+'.ps -W+k+t'+'''"''' +
        sys.argv[1]+'''"'''+' -E'+DPI+' -TG -P '+VS+' -F'+sys.argv[1])
    run('rm -f '+sys.argv[1]+'.ps grad.grd ps2raster* psconvert*')  # FIXME replace with os.remove

    print("GRD2KML - END ... ...")


def _main_func(description):
    grd2kml()


if __name__ == "__main__": # FIXME: Change function to take parameters
    _main_func(__doc__)
