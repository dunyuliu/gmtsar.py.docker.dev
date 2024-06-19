#! /usr/bin/env python3
"""
geocode is part of GMTSAR. 
This Python script is migrated from geocode.csh by Dunyu Liu on 20230914.
geocode.csh was written by David Sandwell on 20100210, and updated by Kurt Feigl on
  20150811 adding annotation to grd files.

Purpose: to make a geocode
"""

import sys
import subprocess
from gmtsar_lib import *


def geocode():
    """
    Usage: geocode correlation_threshold

    phase is masked when correlation is less than correlation_threshold

    Example: geocode 0.12
    """

    print('GEOCODE - START ... ...')
    n = len(sys.argv)
    print('GEOCODE: input arguments are ', sys.argv)

    if n < 2:
        print('GEOCODE: Wrong # of input arguments; # should be 1 ... ...')
        print(geocode.__doc__)

    if check_file_report('~/.quiet') is True:
        V = ''
    else:
        V = '-V'

    print('GEOCODE: first mask the phase and phase gradient using the correlation ... ...')
    print(' ')
    grdmath(f'corr.grd {sys.argv[1]} GE 0 NAN mask.grd MUL = mask2.grd {V}')
    # cmd = 'gmt grdmath corr.grd ' + \
    #     sys.argv[1]+' GE 0 NAN mask.grd MUL = mask2.grd '+V
    # run(cmd)  # FIXME: update to use wrapper

    grdmath('phase.grd mask2.grd MUL = phase_mask.grd')
    # cmd = 'gmt grdmath phase.grd mask2.grd MUL = phase_mask.grd'
    # run(cmd)  # FIXME: See above

    if check_file_report('xphase.grd') is True:
        print('reached line 50 where xphase.grd exists')
        print(os.listdir())
        grdmath('xphase.grd mask2.grd MUL = xphase_mask.grd')
        grdmath('yphase.grd mask2.grd MUL = yphase_mask.grd')

    if check_file_report('unwrap.grd') is True:
        grdsample('mask2.grd `gmt grdinfo unwrap.grd -I-` `gmt grdinfo unwrap.grd -I` -Gmask3.grd')
        grdmath('unwrap.grd mask3.grd MUL = unwrap_mask.grd')

    if check_file_report('phasefilt.grd') is True:
        grdmath('phasefilt.grd mask2.grd MUL = phasefilt_mask.grd')

    print(' ')
    print('GEOCODE: look at the masked phase ... ...')
    grdimage('phase_mask.grd -JX6.5i -Cphase.cpt -Bxaf+lRange -Byaf+lAzimuth -BWSen -X1.3i -Y3i -P -K > phase_mask.ps')
    psscale('-Rphase_mask.grd -J -DJTC+w5i/0.2i+h -Cphase.cpt -Bxa1.57+l"Phase" -By+lrad -O >> phase_mask.ps')
    psconvert('-Tf -P -A -Z phase_mask.ps')

    print(' ')
    print('GEOCODE: maksed phase map: phase_mask,pdf ... ...')

    if check_file_report('xphase_mask.grd') is True:
        makecpt('-Cgray -T-.3/.3/.1 -N -Z > xphase.cpt')
        grdimage('xphase_mask.grd -JX8i -Cxphase.cpt -X.2i -Y.5i -P -K > xphase_mask.ps')
        psscale('-Rxphase_mask.grd -J -DJTC+w5i/0.2i+h -Cxphase.cpt -Bxa0.1+l"Phase" -By+lrad -O >> xphase_mask.ps')
        psconvert('-Tf -P -A -Z xphase_mask.ps')

        print(' ')
        print('GEOCODE: masked x phase map: xphase_mask.pdf ... ...')

        makecpt('-Cgray -T-.6/.6/.1 -N -Z > yphase.cpt')
        grdimage('yphase_mask.grd -JX8i -Cyphase.cpt -X.2i -Y.5i -P -K > yphase_mask.ps')
        psscale('-Ryphase_mask.grd -J -DJTC+w5i/0.2i+h -Cyphase.cpt -Bxa0.1+l"Phase" -By+lrad -O >> yphase_mask.ps')
        psconvert('-Tf -P -A -Z yphase_mask.ps')

        print(' ')
        print('GEOCODE: masked y phase map: yphase_mask.pdf ... ...')

    if check_file_report('unwrap_mask.grd') is True:
        grdimage('unwrap_mask.grd -JX6.5i -Bxaf+lRange -Byaf+lAzimuth -BWSen -Cunwrap.cpt -X1.3i -Y3i -P -K > unwrap_mask.ps')
        psscale('-Runwrap_mask.grd -J -DJTC+w5i/0.2i+h+e -Cunwrap.cpt -Bxaf+l"Unwrapped phase" -By+lrad -O >> unwrap_mask.ps')
        psconvert('-Tf -P -A -Z unwrap_mask.ps')
        print('GEOCODE: Unwrapped masked phase map: unwrap_mask.pdf ... ...')

    if check_file_report('phasefilt_mask.grd') is True:
        grdimage('phasefilt_mask.grd -JX6.5i -Bxaf+lRange -Byaf+lAzimuth -BWSen -Cphase.cpt -X1.3i -Y3i -P -K > phasefilt_mask.ps')
        psscale('-Rphasefilt_mask.grd -J -DJTC+w5i/0.2i+h -Cphase.cpt -Bxa1.57+l"Phase" -By+lrad -O >> phasefilt_mask.ps')
        psconvert('-Tf -P -A -Z phasefilt_mask.ps')
        print('GEOCODE: Filtered masked phase map: phasefilt_mask.pdf')

    print(' ')
    print('GEOCODE: line-of-sight displacement ... ...')

    if check_file_report('unwrap_mask.grd') is True:
        wavel = grep_value('*.PRM', 'wavelength', 3)
        grdmath(f'unwrap_mask.grd {wavel} MUL -79.58 MUL = los.grd')
        # cmd = 'gmt grdmath unwrap_mask.grd ' + \
        #     str(wavel)+' MUL -79.58 MUL = los.grd'
        # run(cmd)  # FIXME: modify to use wrappers
        grdgradient('los.grd -Nt.9 -A0. -Glos_grad.grd')

        cmd_grdinfo = ["gmt", "grdinfo", "-C", "-L2", "los.grd"]
        tmp_output = subprocess.check_output(
            cmd_grdinfo, universal_newlines=True)
        tmp_values = tmp_output.split()
        limitU = float(tmp_values[11])+float(tmp_values[12])*2.
        limitU = round(limitU, 1)
        limitL = float(tmp_values[11])-float(tmp_values[12])*2.
        limitL = round(limitL, 1)

        makecpt("-Cpolar -Z -T"+str(limitL) +"/"+str(limitU)+"/1 -D > los.cpt")
        grdimage('los.grd -Ilos_grad.grd -Clos.cpt -Bxaf+lRange -Byaf+lAzimuth -BWSen -JX6.5i -X1.3i -Y3i -P -K > los.ps')
        
        psscale('-Rlos.grd -J -DJTC+w5i/0.2i+h+e -Clos.cpt -Bxaf+l"LOS displacement [range decrease @~\256@~]" -By+lmm -O >> los.ps')
        psconvert('-Tf -P -A -Z los.ps')
        print('GEOCODE: Line-of-sight map: los.pdf ... ...')

    print(' ')
    print('GEOCODE: now reproject the phase to lon/lat space ... ...')
    print('GEOCODE: geocode ... ...')
    print('GEOCODE: project correlation, phase, unwrapped and amplitude back to lon lat coordinates ... ...')

    remarked = ''  # FIXME: This variable is never used
    run('proj_ra2ll.py trans.dat corr.grd corr_ll.grd')  # FIXME: import these
    grdedit('-D//"dimensionless"/1///"$PWD:t geocoded correlation"/"$remarked"  corr_ll.grd')

    run('proj_ra2ll.py trans.dat phasefilt.grd   phasefilt_ll.grd')
    grdedit('-D//"radians"/1///"$PWD:t wrapped phase after filtering"/"$remarked"  phasefilt_ll.grd')
    run('proj_ra2ll.py trans.dat phase_mask.grd  phase_mask_ll.grd')
    grdedit('-D//"radians"/1///"$PWD:t wrapped phase after masking"/"$remarked"  phase_mask_ll.grd')
    run('proj_ra2ll.py trans.dat display_amp.grd display_amp_ll.grd')
    grdedit('-D//"dimensionless"/1///"PWD:t amplitude"/"$remarked"  display_amp_ll.grd')

    if check_file_report('xphase_mask.grd') is True:
        run('proj_ra2ll.py trans.dat xphase_mask.grd xphase_mask_ll.grd')
        grdedit('-D//"radians"/1///"$PWD:t xphase"/"$remarked"  xphase_mask_ll.grd')
        run('proj_ra2ll.py trans.dat yphase_mask.grd yphase_mask_ll.grd')
        grdedit('-D//"radians"/1///"$PWD:t yphase"/"$remarked"  yphase_mask_ll.grd')

    if check_file_report('unwrap_mask.grd') is True:
        run('proj_ra2ll.py trans.dat unwrap_mask.grd unwrap_mask_ll.grd')
        grdedit('-D//"radians"/1///"PWD:t unwrapped, masked phase"/"$remarked"  unwrap_mask_ll.grd')

    if check_file_report('unwrap.grd') is True:
        run('proj_ra2ll.py trans.dat unwrap.grd unwrap_ll.grd')
        grdedit('-D//"radians"/1///"PWD:t unwrapped phase"/"$remarked"  unwrap_ll.grd')

    if check_file_report('phasefilt_mask.grd') is True:
        run('proj_ra2ll.py trans.dat phasefilt_mask.grd phasefilt_mask_ll.grd')
        grdedit('-D//"phase in radians"/1///"PWD:t wrapped phase masked filtered"/"$remarked"   phasefilt_mask_ll.grd')

    print(' ')
    print('GEOCODE: now image for google earth ... ...')
    print('GEOCODE: make the MKL files for Google Earth ... ...')

    run('grd2kml.py display_amp_ll display_amp.cpt')
    run('grd2kml.py corr_ll corr.cpt')
    run('grd2kml.py phase_mask_ll phase.cpt')
    run('grd2kml.py phasefilt_mask_ll phase.cpt')

    if check_file_report('xphase_mask_ll.grd') is True:
        run('grd2kml.py xphase_mask_ll xphase.cpt')
        run('grd2kml.py yphase_mask_ll yphase.cpt')

    if check_file_report('unwrap_mask_ll.grd') is True:
        run('grd2kml.py unwrap_mask_ll unwrap.cpt')

    if check_file_report('phasefilt_mask_ll.grd') is True:
        run('grd2kml.py phasefilt_mask_ll phase.cpt')

    if check_file_report('unwrap_mask_ll.grd') is True:
        # constant is negative to make LOS = -1 * range change
        # constant is (1000 mm) / (4 * pi)
        grdmath('unwrap_mask_ll.grd $wavel MUL -79.58 MUL = los_ll.grd')
        grdedit('-D//"mm"/1///"$PWD:t LOS displacement"/"equals negative range" los_ll.grd')
        run('grd2kml.py los_ll los.cpt')

    print("GEOCODE - END ... ...")
# NOTE: given the number of calls to check_file_report, code could be condensed by using a list of files to check,
# and iterating over that list. You could then to store the results in a dictionary, and use that to determine
# which files to process. This would also allow you to easily add new files to the list of files to check.

def _main_func(description):
    geocode()


if __name__ == "__main__":
    _main_func(__doc__)  # FIXME: Allow imports
