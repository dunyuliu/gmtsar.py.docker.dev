#! /usr/bin/env python3
"""
p2p_processing is part of pyGMTSAR. 
It is migrated from p2p_processing.csh.
Dunyu Liu, 20230202.

p2p_processing contains python functions to automatically perform two-path processing on raw(1.0)/SLC(1.1) data
Syntax: p2p_processing SAT Image1 Image2
"""

import sys
import os
import subprocess
import glob
import shutil
from gmtsar_lib import *


def P2P1Preprocess(SAT: str, master, aligned, skip_master, cmdAppendix):

    print('P2P 1: PREPROCESS - START')
    print('P2P 1: Processing images '+master+' '+aligned)

    def assert_existence(file):
        """
        checks to ensure the existence of a critical processing file
        and raises an exception if it does not exist.
        """
        if not os.path.exists(f'raw/{file}'):
            raise FileNotFoundError(f"File raw/{file} not found.")

    needed_files = {  # Dictionary of files needed for each satellite
        'ALOS': [''],
        'ENVI_SLC': ['.N1', '.E1', '.E2'],
        'ERS': ['.dat', '.ldr'],
        'CSK': ['.h5'],
        'RS2': ['.xml', '.tif'],
        'TSX': ['.xml', '.cos'],
        'GF3': ['.xml', '.tiff'],
        'S1_TOPS': ['.xml', '.tiff', '.EOF'],
        'S1_STRIP': ['.xml', '.tiff'],
        'ENVI': ['.baq']
        }
    check = 'ALOS' if SAT.startswith('ALOS') else SAT
    check = 'CSK' if SAT.startswith('CSK') else check
    files = needed_files.get(check, False)
    envi_or = SAT == 'ENVI_SLC'
    if files and not envi_or:  # if files are critical, check for their existence based on the satellite
        for file in files:
            assert_existence(master + file)
            assert_existence(aligned + file)
    elif envi_or:  # if the satellite is ENVI_SLC, any one set of the file extensions is sufficient
        exist = [os.path.exists(f'raw/{master}{file}') and os.path.exists(f'raw/{aligned}{file}') for file in files]
        if not any(exist):
            raise FileNotFoundError(f"Files raw/{master} and raw/{aligned} not found.")
    if SAT == 'S1_TOPS':  # Rename master and aligned files for S1_TOPS, if necessary
        file_master, file_aligned = renameMasterAlignedForS1tops(master, aligned)
    else:
        file_master, file_aligned = master, aligned

    for ext in ['.PRM', '.SLC', '.LED']:  # Remove existing files if necessary
        if skip_master in [0, 2]:
            run(f'rm -f raw/{file_master}{ext}')
        if skip_master in [0, 1]:
            run(f'rm -f raw/{file_aligned}{ext}')

    os.chdir("raw")  # cd raw") didn't work.
    os.system('pwd')
    print('P2P 1: entering directory raw/')
    run('pre_proc.py '+SAT + ' '+master+' '+aligned+' '+cmdAppendix)

    print('P2P 1: exiting directory raw/')
    os.chdir('..')
    print('P2P 1: PREPROCESS - END')



def P2P2Clean(master, aligned, skip_master, iono):

    print('P2P 2: if stage<=2 and skip_2 == 0')
    arg2 = sys.argv[2]  # TODO: replace with variable name
    arg3 = sys.argv[3]  # TODO: replace with variable name
    argv_extentions = ['tiff', 'xml', 'EOF']
    tertiaty_extentions = ['PRM*', 'SLC', 'LED']
    directories = ['SLC', 'SLC_L', 'SLC_H']
    if skip_master != 0:  # Check if skip_master is not 0
        iono_check = iono == 1
        mapping = {  # Define a mapping for the different cases
            (1, True): (aligned, arg3),
            (1, False): (aligned, None),
            (2, True): (master, arg2),
            (2, False): (master, None),
        }
        pairs = mapping[(skip_master, iono_check)]
        for directory in directories:  # Iterate over the combinations and remove the files
            for index in range(3):
                run(f"rm -f {directory}/{pairs[0]}.{tertiaty_extentions[index]}")
                if pairs[1]:
                    run(f"rm -f {directory}/{pairs[1]}.{argv_extentions[index]}")
    else:  # If skip_master is 0, remove all files
        for directory in directories:
            for index in range(3):
                run(f"rm -f {directory}/{master}.{tertiaty_extentions[index]}")
                run(f"rm -f {directory}/{aligned}.{tertiaty_extentions[index]}")
                if iono == 1:
                    run(f"rm -f {directory}/{arg2}.{argv_extentions[index]}")
                    run(f"rm -f {directory}/{arg3}.{argv_extentions[index]}")


def P2P2FocusAlign(SAT, master, aligned, skip_master, iono):

    print('P2P 2: focus and align SLC images')
    print("P2P 2: ALIGN.CSH - START")
    print('P2P 2: entering directory SLC/')

    if SAT != 'S1_TOPS':

        print("P2P 2: if SAT is not S1_TOPS")
        if SAT == "ERS" or SAT == "ENVI" or SAT == "ALOS" or SAT == "CSK_RAW":
            if skip_master == 0 or skip_master == 2:
                run("cp ../raw/" + master + ".PRM .")
                run("ln -sf ../raw/" + master + ".raw .")
                run("ln -sf ../raw/" + master + ".LED .")

            if skip_master == 0 or skip_master == 1:
                run("cp ../raw/" + aligned + ".PRM .")
                run("ln -sf ../raw/" + aligned + ".raw .")
                run("ln -sf ../raw/" + aligned + ".LED .")

                if iono == 1:
                    # set chirp extension to zero for ionospheric phase estimation.
                    replace_strings(master+".PRM", "fd1", "fd1 = 0.0000")
                    replace_strings(master+".PRM", "chirp_ext",
                                    "chirp_ext = 0")

                    replace_strings(aligned+".PRM", "fd1", "fd1 = 0.0000")
                    replace_strings(
                        aligned+".PRM", "chirp_ext", "chirp_ext = 0")
        else:
            run("cp ../raw/" + master + ".PRM .")
            run("ln -sf ../raw/" + master + ".SLC .")
            run("ln -sf ../raw/" + master + ".LED .")

            run("cp ../raw/" + aligned + ".PRM .")
            run("ln -sf ../raw/" + aligned + ".SLC .")
            run("ln -sf ../raw/" + aligned + ".LED .")

        if SAT == "ERS" or SAT == "ENVI" or SAT == "ALOS" or SAT == "CSK_RAW":

            print('P2P 2: calling sarp.py for SAT==ERS/ENVI/ALOS/CSK_RAW')
            if skip_master == 0 or skip_master == 2:
                run("sarp.py " + master + ".PRM")
            if skip_master == 0 or skip_master == 1:
                run("sarp.py " + aligned + ".PRM")

        if iono == 1:
            print(" ")
            print("P2P 2: if iono == 1")
            print(" ")
            if skip_master == 0 or skip_master == 2:
                file_path = f"../raw/ALOS_fbd2fbs_log_{aligned}"
                if check_file_report(file_path) is True:
                    split_spectrum(master + ".PRM 1 > params1")
                else:
                    split_spectrum(master + ".PRM > params1")

                file_shuttle('SLCH', '../SLC_H/'+master+'.SLC', 'mv')
                file_shuttle('SLCL', '../SLC_L/'+master+'.SLC', 'mv')
                os.chdir("../SLC_L")
                wl1 = grep_value("../SLC/params1", "low_wavelength", 3)
                cmd = "cp ../SLC/" + master + ".PRM ."
                run(cmd)
                cmd = "ln -sf ../raw" + master + ".LED ."
                run(cmd)
                replace_strings(master+".PRM", "wavelength",
                                "radar_wavelength = "+wl1)

                os.chdir("../SLC_H")
                wh1 = grep_value("../SLC/params1", "low_wavelength", 3)
                cmd = "cp ../SLC/" + master + ".PRM ."
                run(cmd)
                cmd = "ln -sf ../raw" + master + ".LED ."
                run(cmd)
                replace_strings(master+".PRM", "wavelength",
                                "radar_wavelength = "+wh1)
                os.chdir("../SLC")

            if skip_master == 0 or skip_master == 1:
                file_path = f"../raw/ALOS_fbd2fbs_log_{aligned}"
                if check_file_report(file_path):
                    split_spectrum(aligned + ".PRM 1 > params2")
                else:
                    split_spectrum(aligned + ".PRM > params2")

                cmd = "mv SLCH ../SLC_H/" + aligned + ".SLC"
                run(cmd)
                cmd = "mv SLCL ../SLC_L/" + aligned + ".SLC"
                run(cmd)

                os.chdir("../SLC_L")
                wl2 = grep_value("../SLC/params2", "low_wavelength", 3)
                cmd = "cp ../SLC/" + aligned + ".PRM ."
                run(cmd)
                cmd = "ln -sf ../raw" + aligned + ".LED ."
                run(cmd)
                replace_strings(aligned+".PRM", "wavelength",
                                "radar_wavelength = "+wl2)

                os.chdir("../SLC_H")
                wh2 = grep_value("../SLC/params2", "low_wavelength", 3)
                cmd = "cp ../SLC/" + aligned + ".PRM ."
                run(cmd)
                cmd = "ln -sf ../raw" + aligned + ".LED ."
                run(cmd)
                replace_strings(aligned+".PRM", "wavelength",
                                "radar_wavelength = "+wh2)
        # endif (iono == 1)
        #
        if skip_master == 0 or skip_master == 1:
            file_shuttle(aligned+'.PRM', aligned+'.PRM0', 'cp')
            SAT_baseline(master + ".PRM " +
                aligned + ".PRM0 >> " + aligned + ".PRM")

            if SAT == "ALOS2_SCAN":
                xcorr(master + ".PRM " + aligned +
                    ".PRM -xsearch 32 -ysearch 256 -nx 32 -ny 128")
                # set amedian = `sort -n tmp.dat | awk ' { a[i++]=$1; } END { print a[int(i/2)]; }'`
                # set amax = `echo $amedian | awk '{print $1+3}'`
                # set amin = `echo $amedian | awk '{print $1-3}'`
                # awk '{if($4 > '$amin' && $4 < '$amax') print $0}' < freq_xcorr.dat > freq_alos2.dat
                # fitoffset 2 3 freq_alos2.dat 10 >> $aligned.PRM
            elif SAT == "ERS" or SAT == "ENVI" or SAT == "ALOS" or SAT == "CSK_RAW":
                xcorr(master + ".PRM " + aligned +
                    ".PRM -xsearch 128 -ysearch 128 -nx 20 -ny 50")
                run("fitoffset.py 3 3 freq_xcorr.dat 18 >> " + aligned + ".PRM")
            else:
                xcorr(master + ".PRM " + aligned +
                    ".PRM -xsearch 128 -ysearch 128 -nx 20 -ny 50")
                run("fitoffset.py 2 2 freq_xcorr.dat 18 >> " + aligned + ".PRM")

            resamp(master + ".PRM " + aligned + ".PRM " +
                aligned + ".PRMresamp " + aligned + ".SLCresamp 4")
            delete(aligned + ".SLC")
            file_shuttle(aligned+'.SLCresamp', aligned+'.SLC', 'mv')
            file_shuttle(aligned+'.PRMresamp', aligned+'.PRM', 'cp')

            if iono == 1:
                print(" ")
                print("P2P 2: if iono == 1")
                print(" ")
                os.chdir("../SLC_L")
                cmd = "cp " + aligned + ".PRM " + aligned + ".PRM0"
                run(cmd)

                if SAT == "ALOS2_SCAN":
                    cmd = "ln -sf ../SLC/freq_alos2.dat"
                    run(cmd)
                    cmd = "fitoffset 3 3 freq_xcorr.dat 18 >>" + aligned + ".PRM"
                    run(cmd)
                elif (SAT == "ERS" or SAT == "ENVI" or SAT == "ALOS" or SAT == "CSK_RAW" or SAT == "TSX"):
                    cmd = "ln -sf ../SLC/freq_xcorr.dat"
                    run(cmd)
                    cmd = "fitoffset 3 3 freq_xcorr.dat 18 >>" + aligned + ".PRM"
                    run(cmd)
                else:
                    cmd = "ln -sf ../SLC/freq_alos2.dat"
                    run(cmd)
                    cmd = "fitoffset 2 2 freq_xcorr.dat 18 >>" + aligned + ".PRM"
                    run(cmd)

                cmd = "resamp "+master+".PRM "+aligned+".PRM " + \
                    aligned+".PRMresamp "+aligned+".SLCresamp 4"
                run(cmd)
                delete(aligned + ".SLC")
                file_shuttle(aligned+".SLCresamp", aligned+".SLC", "mv")
                file_shuttle(aligned+".PRMresamp", aligned+".PRM", "cp")

                os.chdir("../SLC_H")
                file_shuttle(aligned+".PRM ", aligned+".PRM0", "cp")
                if SAT == "ALOS2_SCAN":
                    cmd = "ln -sf ../SLC/freq_alos2.dat"
                    run(cmd)
                    cmd = "fitoffset 3 3 freq_xcorr.dat 18 >>" + aligned + ".PRM"
                    run(cmd)
                elif (SAT == "ERS" or SAT == "ENVI" or SAT == "ALOS" or SAT == "CSK_RAW"):
                    cmd = "ln -sf ../SLC/freq_xcorr.dat"
                    run(cmd)
                    cmd = "fitoffset 3 3 freq_xcorr.dat 18 >>" + aligned + ".PRM"
                    run(cmd)
                else:
                    cmd = "ln -sf ../SLC/freq_alos2.dat"
                    run(cmd)
                    cmd = "fitoffset 2 2 freq_xcorr.dat 18 >>" + aligned + ".PRM"
                    run(cmd)

                cmd = "resamp "+master+".PRM "+aligned+".PRM " + \
                    aligned+".PRMresamp "+aligned+".SLCresamp 4"
                run(cmd)
                delete(aligned + ".SLC")
                file_shuttle(aligned+".SLCresamp", aligned+".SLC", "mv")
                file_shuttle(aligned+".PRMresamp", aligned+".PRM", "cp")
                os.chdir("../SLC")

    elif SAT == "S1_TOPS":
        if skip_master == 0 or skip_master == 2:
            file_shuttle("../raw/"+master+".PRM", ".", "cp")
            file_shuttle('../raw/'+master+'.SLC', '.', 'link')
            file_shuttle('../raw/'+master+'.LED', '.', 'link')

        if skip_master == 0 or skip_master == 1:
            file_shuttle("../raw/"+aligned+".PRM", ".", "cp")
            file_shuttle('../raw/'+aligned+'.SLC', '.', 'link')
            file_shuttle('../raw/'+aligned+'.LED', '.', 'link')

        if iono == 1:
            if (skip_master == 0 or skip_master == 2):
                file_shuttle("../raw/"+sys.argv[1]+".tiff", ".", "link")
                cmd = "split_spectrum "+master+".PRM > params1"
                run(cmd)
                file_shuttle("high.tiff", "../SLC_H/" +
                             sys.argv[1]+".tiff", "mv")
                file_shuttle("low.tiff", "../SLC_L/"+sys.argv[1]+".tiff", "mv")

            if (skip_master == 0 or skip_master == 1):
                file_shuttle("../raw/"+sys.argv[2]+".tiff", ".", "link")
                cmd = "split_spectrum "+aligned+".PRM > params2"
                run(cmd)
                file_shuttle("high.tiff", "../SLC_H/" +
                             sys.argv[2]+".tiff", "mv")
                file_shuttle("low.tiff", "../SLC_L/"+sys.argv[2]+".tiff", "mv")

            os.chdir("../SLC_L")
            if (skip_master == 0 or skip_master == 2):
                file_shuttle("../raw/"+sys.argv[1]+".xml", ".", "link")
                file_shuttle("../raw/"+sys.argv[1]+".EOF", ".", "link")
                file_shuttle("../topo/dem.grd", ".", "link")
            if (skip_master == 0 or skip_master == 1):
                file_shuttle("../raw/"+sys.argv[2]+".xml", ".", "link")
                file_shuttle("../raw/"+sys.argv[2]+".EOF", ".", "link")
                file_shuttle("../raw/a.grd", ".", "link")
                file_shuttle("../raw/r.grd", ".", "link")
                file_shuttle("../raw/offset*dat", ".", "link")

            if skip_master == 0:
                align_tops_csh(sys.argv[1]+" "+sys.argv[1] +
                    ".EOF "+sys.argv[2]+" "+sys.argv[2]+".EOF dem.grd 1")
            elif skip_master == 1:
                cmd = "align_tops.csh " + \
                    sys.argv[1]+" 0 "+sys.argv[2] + \
                    " "+sys.argv[2]+".EOF dem.grd 1"
                run(cmd)
            elif skip_master == 2:
                cmd = "align_tops.csh " + \
                    sys.argv[1]+" "+sys.argv[1] + \
                    ".EOF "+sys.argv[2]+" 0 dem.grd 1"
                run(cmd)

            if (skip_master == 0 or skip_master == 2):
                wl1 = grep_value("low_wavelength", "../SLC/params1", 3)
                replace_strings(master+".PRM", "wavelength",
                                "radar_wavelength = "+wl1)
            if (skip_master == 0 or skip_master == 1):
                wl2 = grep_value("low_wavelength", "../SLC/params2", 3)
                replace_strings(aligned+".PRM", "wavelength",
                                "radar_wavelength = "+wl2)

            # repeat everything for ../SLC_H
            os.chdir("../SLC_H")
            if (skip_master == 0 or skip_master == 2):
                file_shuttle("../raw/"+sys.argv[1]+".xml", ".", "link")
                file_shuttle("../raw/"+sys.argv[1]+".EOF", ".", "link")
                file_shuttle("../topo/dem.grd", ".", "link")
            elif (skip_master == 0 or skip_master == 1):
                file_shuttle("../raw/"+sys.argv[2]+".xml", ".", "link")
                file_shuttle("../raw/"+sys.argv[2]+".EOF", ".", "link")
                file_shuttle("../raw/a.grd", ".", "link")
                file_shuttle("../raw/r.grd", ".", "link")
                file_shuttle("../raw/offset*.dat", ".", "link")

            if skip_master == 0:
                cmd = "align_tops.csh " + \
                    sys.argv[1]+" "+sys.argv[1]+".EOF " + \
                    sys.argv[2]+" "+sys.argv[2]+".EOF dem.grd 1"
                run(cmd)
            elif skip_master == 1:
                cmd = "align_tops.csh " + \
                    sys.argv[1]+" 0 "+sys.argv[2] + \
                    " "+sys.argv[2]+".EOF dem.grd 1"
                run(cmd)
            elif skip_master == 2:
                cmd = "align_tops.csh " + \
                    sys.argv[1]+" "+sys.argv[1] + \
                    ".EOF "+sys.argv[2]+" 0 dem.grd 1"
                run(cmd)

            if (skip_master == 0 or skip_master == 2):
                wl1 = grep_value("low_wavelength", "../SLC/params1", 3)
                replace_strings(master+".PRM", "wavelength",
                                "radar_wavelength = "+wl1)
            if (skip_master == 0 or skip_master == 1):
                wl2 = grep_value("low_wavelength", "../SLC/params2", 3)
                replace_strings(aligned+".PRM", "wavelength",
                                "radar_wavelength = "+wl2)

            os.chdir("../SLC")


def P2P2RegionCut(master, aligned, skip_master, iono, config):
    region_cut = config['region_cut']
    print("P2P 2: region_cut !=-999 ")
    print("P2P 2: cutting SLC image to " + str(region_cut))
    if skip_master == 0 or skip_master == 2:
        cut_slc(master + ".PRM junk1 " + str(region_cut))
        run("mv junk1.PRM " + master + ".PRM")
        run("mv junk1.SLC " + master + ".SLC")

    if skip_master == 0 or skip_master == 1:
        cut_slc(aligned + ".PRM junk2 " + str(region_cut))
        run("mv junk2.PRM " + aligned + ".PRM")
        run("mv junk2.SLC " + aligned + ".SLC")

    if iono == 1:
        print('P2P 2: iono = 1')
        print('P2P 2: entering SLC_L')
        os.chdir("../SLC_L")
        if (skip_master == 0 or skip_master == 2):
            cut_slc(master+".PRM junk1 "+str(region_cut))
            file_shuttle("junk1.PRM", master+".PRM", "mv")
            file_shuttle("junk1.SLC", master+".SLC", "mv")
        if (skip_master == 0 or skip_master == 1):
            cut_slc(aligned+".PRM junk2 "+str(region_cut))
            file_shuttle("junk2.PRM", master+".PRM", "mv")
            file_shuttle("junk2.SLC", master+".SLC", "mv")

        # redo everything for ../SLC_H
        print('P2P 2: entering SLC_H')
        os.chdir("../SLC_H")
        if (skip_master == 0 or skip_master == 2):
            cut_slc(master+".PRM junk1 "+str(region_cut))
            file_shuttle("junk1.PRM", master+".PRM", "mv")
            file_shuttle("junk1.SLC", master+".SLC", "mv")
        if (skip_master == 0 or skip_master == 1):
            cut_slc(aligned+".PRM junk2 "+str(region_cut))
            file_shuttle("junk2.PRM", master+".PRM", "mv")
            file_shuttle("junk2.SLC", master+".SLC", "mv")


def P2P3MakeTopo(master, topo_phase, topo_interp_mode, shift_topo):
    print('P2P 3: start from make topo_ra')
    run("cleanup.py topo")

    print('P2P 3: make topo_ra if there is dem.grd')
    if topo_phase == 1:
        print(" ")
        print('P2P 3: topo_phase=1')
        print("P2P 3: DEM2TOPO_RA.CSH - START")
        print("P2P 3: USER SHOULD PROVIDE DEM FILE")

        print('P2P 3: entering directory topo/')
        os.chdir("topo")
        file_shuttle('../SLC/'+master+'.PRM', 'master.PRM', 'cp')
        run("ln -sf ../raw/" + master + ".LED .")

        if check_file_report('dem.grd') is True:
            if topo_interp_mode == 1:
                run("dem2topo_ra.py master.PRM dem.grd 1")
            else:
                run("dem2topo_ra.py master.PRM dem.grd")
        else:
            print("no DEM file found: dem.grd")
            sys.exit(1)

        print('P2P 3: exiting directory topo/')
        os.chdir('..')
        print('P2P 3: DEM2TOPO_RA.CSH - END')
        print('P2P 3: shift topo_ra')
        if shift_topo == 1:
            print('P2P 3: OFFSET_TOPO - START')
            print('P2P 3: entering directory SLC/')
            os.chdir('SLC')
            grdinfo("../topo/topo_ra.grd > tmp.txt")
            rng = grep_value("tmp.txt", "x_inc", 7)
            slc2amp_csh(master+'.PRM '+str(rng)+' amp-'+master+'.grd') # TODO: This should invoke the python verson of slc2amp
            print('P2P 3: exiting SLC/')
            os.chdir("..")

            print('P2P 3: entering topo/')
            os.chdir("topo")
            file_shuttle("../SLC/amp-"+master+".grd", ".", "link")
            offset_topo('amp-'+master+'.grd topo_ra.grd 0 0 7 topo_shift.grd')
            print('P2P 3: exiting topo/')
            os.chdir("..")
            print("P2P 3: OFFSET_TOPO - END")
        elif shift_topo == 0:
            print("P2P 3: NO TOPO_RA SHIFT ")
        else:
            print("P2P 3: wrong parameter: shift_topo " + shift_topo)
            sys.exit(1)

    elif topo_phase == 0:
        print("P2P 3: NO TOPO_RA is SUBSTRACTED")
    else:
        print("P2P 3: wrong parameter: topo_phase " + topo_phase)
        sys.exit(1)


def switchMasterAligned(switch_master, master, aligned):
    print('P2P 4: select the master based on switch_master')
    if switch_master == 0:
        ref = master
        rep = aligned
    elif switch_master == 1:
        ref = aligned
        rep = master
    else:
        sys.exit('P2P 4: wrong parameter: switch_master ' + switch_master)
    return ref, rep


def P2P4MakeFilterInterferograms(ref, rep, topo_phase, shift_topo, range_dec, azimuth_dec,
                                 dec, filt, compute_phase_gradient, iono, iono_dsamp, config):  # FIXME: use variable name other than 'filter' as it is a reserved keyword.

    iono_skip_est = config['iono_skip_est']
    mask_water = config['mask_water']
    # switch_land = config
    iono_filt_rng = config['iono_filt_rng']
    switch_land = -999  # FIXME: This should be in the config file
    iono_filt_azi = config['iono_filt_azi']
    print('P2P 4: start from make and filter interferograms')
    run('mkdir -p intf')  # FIXME: use os
    run('cleanup.py intf')

    print('P2P 4: INTF.CSH, FILTER.CSH - START')
    print('P2P 4: entering intf/')
    os.chdir('intf')
    intfSubDirName = getIntfSubDirName(ref, rep)
    run('mkdir -p '+intfSubDirName)  # FIXME: use os
    os.chdir(intfSubDirName)

    run('ln -sf ../../SLC/'+ref + '.LED .')
    run('ln -sf ../../SLC/'+rep + '.LED .')
    run('ln -sf ../../SLC/'+ref + '.SLC .')
    run('ln -sf ../../SLC/'+rep + '.SLC .')
    run('cp ../../SLC/' + ref + '.PRM .')
    run('cp ../../SLC/' + rep + '.PRM .')

    if topo_phase == 1:
        if shift_topo == 1:
            run('ln -s ../../topo/topo_shift.grd .')
            run('intf.py ' + ref + '.PRM ' + rep + '.PRM -topo topo_shift.grd')
            runFilter(ref, rep, filt, dec, range_dec,
                      azimuth_dec, compute_phase_gradient)
        else:
            run('ln -s ../../topo/topo_ra.grd .')
            run('intf.py ' + ref + '.PRM ' + rep + '.PRM -topo topo_ra.grd')
            runFilter(ref, rep, filt, dec, range_dec,
                      azimuth_dec, compute_phase_gradient)
    else:
        print('P2P 4: NO TOPOGRAPHIC PHASE REMOVAL PORFORMED')
        run('intf.py '+ref+'.PRM '+rep+'.PRM')
        runFilter(ref, rep, filt, dec, range_dec,
                  azimuth_dec, compute_phase_gradient)

    os.chdir('../..')

    if iono == 1:
        if os.path.exists('iono_phase'):
            shutil.rmtree('iono_phase')  # NOTE: Where is shutil imported from?
        os.makedirs('iono_phase')
        os.chdir('iono_phase')
        directories = ['intf_o', 'intf_h', 'intf_l', 'iono_correction']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        new_incx = int(range_dec) * int(iono_dsamp)
        new_incy = int(azimuth_dec) * int(iono_dsamp)
        os.chdir('intf_h')
        files = glob.glob('../../SLC_H/*.SLC')
        for file in files:
            file_shuttle(file, '.', 'link')

        files = glob.glob('../../SLC_H/*.LED')
        for file in files:
            file_shuttle(file, '.', 'link')

        files = glob.glob('../../SLC_H/*.PRM')
        for file in files:
            file_shuttle(file, '.', 'cp')

        files = glob.glob('../../SLC/params*')
        for file in files:
            file_shuttle(file, '.', 'cp')

        if topo_phase == 1:
            if shift_topo == 1:
                file_shuttle('../../topo/topo_shift.grd', '.', 'link')
                run('intf.py '+ref+'.PRM '+rep+'.PRM -topo topo_shift.grd')
                print('p2p calling filter on line 669')
                run('filter.py '+ref+'.PRM '+rep+'.PRM 500 ' +
                    dec+' '+new_incx+' '+new_incy)
            else:
                file_shuttle('../../topo/topo_ra.grd', '.', 'link')

                run('intf.py '+ref+'.PRM '+rep+'.PRM -topo topo_ra.grd')
                print('p2p calling filter on line 676')
                run('filter.py '+ref+'.PRM '+rep+'.PRM 500 ' +
                    dec+' '+new_incx+' '+new_incy)
        else:
            print('NO TOPOGRAPHIC PHASE REMOVAL PORFORMED')
            run('intf.py '+ref+'.PRM '+rep+'.PRM')
            print('p2p calling filter on line 682')
            run('filter.py '+ref+'.PRM '+rep+'.PRM 500 ' +
                dec+' '+new_incx+' '+new_incy)

        file_shuttle('phase.grd', 'phasefilt.grd', 'cp')

        if iono_skip_est == 0: # FIXME: Switch land is not in the config file, should this be switch_master?
            if mask_water == 1 or switch_land == 1: 
                output = subprocess.check_output(
                    'gmt grdinfo phase.grd -I-', shell=True)
                rcut = output[2:20].decode('utf-8')

                os.chdir('../../topo')
                run('landmask.py' + rcut)  #FIXME: use imports
                os.chdir('../iono_phase/intf_h')
                file_shuttle('../../topo/landmask_ra.grd', '.', 'link')

            snaphu_interp_csh('0.05 0')
        os.chdir('..')
        os.chdir('intf_h')
        files = glob.glob('../../SLC_L/*.SLC')
        for file in files:  # FIXME: multiple loops through files... possibly optimiziable?
            file_shuttle(file, '.', 'link')

        files = glob.glob('../../SLC_L/*.LED')
        for file in files:
            file_shuttle(file, '.', 'link')

        files = glob.glob('../../SLC_L/*.PRM')
        for file in files:
            file_shuttle(file, '.', 'cp')

        files = glob.glob('../../SLC/params*')
        for file in files:
            file_shuttle(file, '.', 'cp')

        if topo_phase == 1:
            if shift_topo == 1:
                file_shuttle('../../topo/topo_shift.grd', '.', 'link')

                cmd = 'intf.py '+ref+'.PRM '+rep+'.PRM -topo topo_shift.grd'
                run(cmd)

                cmd = 'filter.py '+ref+'.PRM '+rep+'.PRM 500 '+dec+' '+new_incx+' '+new_incy
                print('p2p calling filter on line 727')
                run(cmd)

            else:
                file_shuttle('../../topo/topo_ra.grd', '.', 'link')

                cmd = 'intf.py '+ref+'.PRM '+rep+'.PRM -topo topo_ra.grd'
                run(cmd)

                cmd = 'filter.py '+ref+'.PRM '+rep+'.PRM 500 '+dec+' '+new_incx+' '+new_incy
                print('p2p calling filter on line 737')
                run(cmd)
            # endif (shift_topo == 1)

        else:
            print('P2P 4: NO TOPOGRAPHIC PHASE REMOVAL PORFORMED')

            cmd = 'intf.py '+ref+'.PRM '+rep+'.PRM'
            run(cmd)

            cmd = 'filter.py '+ref+'.PRM '+rep+'.PRM 500 '+dec+' '+new_incx+' '+new_incy
            print('p2p calling filter on line 748')
            run(cmd)
        # endif (topo_phase == 1)
        # FIXME: Above run commands should use wrappers
        file_shuttle('phase.grd', 'phasefilt.grd', 'cp')

        if iono_skip_est == 0:
            if mask_water == 1 or switch_land == 1:
                file_shuttle('../../topo/landmask_ra.grd', '.', 'link')
            # endif (mask_water == 1 or switch_land == 1)

            cmd = 'snaphu_interp.csh 0.05 0'
            run(cmd)

        os.chdir('..')
        # endif iono_skip_est == 0

        # redo everything for intf_o

        os.chdir('intf_o')
        files = glob.glob('../../SLC/*.SLC')
        for file in files:
            file_shuttle(file, '.', 'link')

        files = glob.glob('../../SLC/*.LED')
        for file in files:
            file_shuttle(file, '.', 'link')

        files = glob.glob('../../SLC/*.PRM')
        for file in files:
            file_shuttle(file, '.', 'cp')

        if topo_phase == 1:
            if shift_topo == 1:
                file_shuttle('../../topo/topo_shift.grd', '.', 'link')

                cmd = 'intf.py '+ref+'.PRM '+rep+'.PRM -topo topo_shift.grd'
                run(cmd)

                cmd = 'filter.py '+ref+'.PRM '+rep+'.PRM 500 '+dec+' '+new_incx+' '+new_incy
                print('p2p calling filter on line 788')
                run(cmd)

            else:
                file_shuttle('../../topo/topo_ra.grd', '.', 'link')

                cmd = 'intf.py '+ref+'.PRM '+rep+'.PRM -topo topo_ra.grd'
                run(cmd)

                cmd = 'filter.py '+ref+'.PRM '+rep+'.PRM 500 '+dec+' '+new_incx+' '+new_incy
                print('p2p calling filter on line 798')
                run(cmd)
            # endif (shift_topo == 1)

        else:
            print('NO TOPOGRAPHIC PHASE REMOVAL PORFORMED')

            cmd = 'intf.py '+ref+'.PRM '+rep+'.PRM'
            run(cmd)

            cmd = 'filter.py '+ref+'.PRM '+rep+'.PRM 500 '+dec+' '+new_incx+' '+new_incy
            print('p2p calling filter on line 809')
            run(cmd)
        # endif (topo_phase == 1)

        file_shuttle('phase.grd', 'phasefilt.grd', 'cp')

        if iono_skip_est == 0:
            if mask_water == 1 or switch_land == 1:
                file_shuttle('../../topo/landmask_ra.grd', '.', 'link')
            # endif (mask_water == 1 or switch_land == 1)

            cmd = 'snaphu_interp.csh 0.05 0'
            run(cmd)

        os.chdir('../iono_correction')

        # endif iono_skip_est == 0

        if iono_skip_est == 0:
            cmd = 'estimate_ionospheric_phase.csh ../intf_h ../intf_l ../intf_o ../../intf/'+intfSubDirName \
                + ' '+iono_filt_rng+' '+iono_filt_azi
            run(cmd)
            os.chdir('../../intf/'+intfSubDirName)
            file_shuttle('phasefilt.grd', 'phasefilt_non_corrected.grd', 'mv')
            grdsample('../../iono_phase/iono_correction/ph_iono_orig.grd -Rphasefilt_non_corrected.grd -Gph_iono.grd')
            grdmath('phasefilt_non_corrected.grd ph_iono.grd SUB PI ADD 2 PI MUL MOD PI SUB = phasefilt.grd')
            grdimage('phasefilt.grd -JX6.5i -Bxaf+lRange -Byaf+lAzimuth -BWSen -Cphase.cpt -X1.3i -Y3i -P -K > phasefilt.ps')
            psscale('-Rphasefilt.grd -J -DJTC+w5i/0.2i+h -Cphase.cpt -Bxa1.57+l"Phase" -By+lrad -O >> phasefilt.ps')
            psconvert('-Tf -P -A -Z phasefilt.ps')

        os.chdir('../../')
    print('INTF.CSH, FILTER.CSH - END')


def runFilter(ref, rep, filt, dec, range_dec, azimuth_dec, compute_phase_gradient):  # FIXME: use variable name other than 'filter' as it is a reserved keyword.
    if range_dec == -999 and azimuth_dec == -999:  # FIXME: f strings could condense this and preform implicit type conversion
        print("p2p calling Filter on line 844")
        run('filter.py '+ref+'.PRM '+rep+'.PRM '+str(filt) +
            ' '+str(dec)+' '+str(compute_phase_gradient))
    else:
        print('p2p calling Filter on line 848')
        run('filter.py '+ref+'.PRM '+rep+'.PRM '+str(filt)+' '+str(dec)+' ' +
            str(range_dec)+' '+str(azimuth_dec)+' '+str(compute_phase_gradient))


def getIntfSubDirName(ref, rep):
    ref_id = int(float(grep_value("../raw/"+ref+".PRM", "SC_clock_start", 3)))  # NOTE: casting to float simply cuts off the decimal, is this intended? (If not, use round() first)
    rep_id = int(float(grep_value("../raw/"+rep+".PRM", "SC_clock_start", 3)))
    intfSubDirName = str(ref_id)+'_'+str(rep_id)
    return intfSubDirName


def P2P5Unwrap(ref, rep, threshold_snaphu, mask_water, switch_land, near_interp, config):
    defomax = config['defomax']
    if threshold_snaphu != 0:
        print('P2P 5: threshold_snaphu != 0')
        print('P2P 5: entering intf/')
        os.chdir("intf")
        intfSubDirName = getIntfSubDirName(ref, rep)
        os.chdir(intfSubDirName)

        print('P2P 5: landmask')
        if mask_water == 1 or switch_land == 1:
            r_cut = "gmt grdinfo phase.grd -I- | cut -c3-20"
            os.chdir("../../topo")
            if check_file_report('landmask_ra.grd') is False:  # FIXME: This is not defined - should be a string?
                run("landmask.py " + r_cut)  # FIXME: use imports
            os.chdir("../intf")
            os.chdir(intfSubDirName)
            run("ln -sf ../../topo/landmask_ra.grd .")
        print('P2P 5: SNAPHU.CSH - START')
        print('P2P 5: threshold_snaphu = ', threshold_snaphu)
        if near_interp == 1:
            snaphu_interp_csh(str(threshold_snaphu) + " " + str(defomax))
        else:
            run("snaphu.csh " + str(threshold_snaphu) + " " + str(defomax))  # FIXME: This is implmented in python
        print('P2P 5: SNAPHU.CSH - END')
        os.chdir("../..")
    else:
        print('P2P 5: SKIP UNWRAP PAHSE')


def P2P6Geocode(ref, rep, threshold_geocode, topo_phase):
    if threshold_geocode != 0:
        print('P2P 6: threshold_geocode != 0')
        print('P2P 6: entering intf/')
        os.chdir("intf")
        intfSubDirName = getIntfSubDirName(ref, rep)
        os.chdir(intfSubDirName)

        print('P2P 6: GEOCODE.CSH - START')

        if check_file_report("rain.grd") is True:
            delete("rain.grd")
        if check_file_report("ralt.grd") is True:
            delete("ralt.grd")
        if check_file_report('trans.dat') is True:
            delete('trans.dat')
        if topo_phase == 1:
            run('ln -sf ../../topo/trans.dat .')
            print('threshold_geocode: ', threshold_geocode)
            run('geocode.py ' + str(threshold_geocode))
        else:
            print('P2P 6: topo_ra is needed to geocode')
            sys.exit(1)

        print('P2P 6: GEOCODE.CSH - END')
        os.chdir('../..')
    else:
        print('P2P 6: SKIP_GEOCODE')


def p2p_processing(debug):
    """
    Usage: p2p_processing SAT master_image aligned_image [Python configuration_file] ')
    Example: p2p_processing ALOS IMG-HH-ALPSRP055750660-H1.0__A IMG-HH-ALPSRP049040660-H1.0__A [config.alos.py]')
        Put the data and orbit files in the raw folder, put DEM in the topo folder')
        The SAT needs to be specified, choices with in ERS, ENVI, ALOS, ALOS_SLC, ALOS2, ALOS2_SCAN')
        S1_STRIP, S1_TOPS, ENVI_SLC, CSK_RAW, CSK_SLC, TSX, RS2, GF3')

        Make sure the files from the same date have the same stem, e.g. aaaa.tif aaaa.xml aaaa.cos aaaa.EOF, etc')

        If [Python the configuration file] flag is left blank, the program will generate a default one using p2p_config')
        with default parameters ')
    """
    #
    # check the number of arguments
    n = len(sys.argv)
    # If using p2p_processing A B C D, then a total of 5 input parameters are expected.
    SAT = sys.argv[1]
    if n != 4 and n != 5:
        print(p2p_processing.__doc__)
        sys.exit('ERROR: the number of arguments is not correct.')
    config_file = sys.argv[4] if n == 5 else None

    print('P2P 0: the satellite is ', SAT)
    print('P2P 0: check if a customized configuration file config.py exists ... ...')
    if n == 5:
        if check_file_report(sys.argv[4]) is False:
            print('P2P 0: WARNING: the 4th arg config.py is required but missing ... ...')
            print('P2P 0: WARNING: a default config.py is being generated ... ...')
            run('pop_config.py ' + SAT)
        elif check_file_report(sys.argv[4]) is True:
            print(
                'P2P 0: a customized config.py is provided and will be used to tune GMTSAR workflow ... ...')
    elif n == 4:
        print('P2P 0: no config.py is provided ... ...')
        print('P2P 0: and a default one will be generated by p2p_config ... ...')
        run('pop_config.py ' + SAT)

    print('P2P 0: read in parameters from the config.py ... ...')
    sys.path.insert(0, os.getcwd())
    if config_file:
        config = init_config(SAT, config_file)
    else:
        config = init_config(SAT)
    proc_stage = config['proc_stage']
    skip_stage = config['skip_stage']
    skip_master = config['skip_master']
    skip_1 = config['skip_1']
    skip_2 = config['skip_2']
    skip_3 = config['skip_3']
    skip_4 = config['skip_4']
    skip_5 = config['skip_5']
    skip_6 = config['skip_6']
    num_patches = config['num_patches']
    earth_radius = config['earth_radius']
    near_range = config['near_range']
    fd1 = config['fd1']
    region_cut = config['region_cut']
    topo_phase = config['topo_phase']
    topo_interp_mode = config['topo_interp_mode']
    switch_master = config['switch_master']
    filter_wavelength = config['filter_wavelength']
    compute_phase_gradient = config['compute_phase_gradient']
    correct_iono = config['correct_iono']
    iono_filt_rng = config['iono_filt_rng']
    iono_filt_azi = config['iono_filt_azi']
    iono_dsamp = config['iono_dsamp']
    iono_skip_est = config['iono_skip_est']
    threshold_snaphu = config['threshold_snaphu']
    near_interp = config['near_interp']
    mask_water = config['mask_water']
    defomax = config['defomax']
    threshold_geocode = config['threshold_geocode']
    spec_div = config['spec_div']
    spec_mode = config['spec_mode']
    dec_factor = config['dec_factor']
    shift_topo = config['shift_topo']
    range_dec = config['range_dec']
    azimuth_dec = config['azimuth_dec']
    SLC_factor = config['SLC_factor']
    switch_land = config['switch_land']

    print('P2P 0: proc_stage   =', proc_stage)
    print('P2P 0: skip_stage   =', skip_stage)
    print('P2P 0: skip_master  =', skip_master)
    print('P2P 0: num_patches  =', num_patches)
    print('P2P 0: earth_radius =', earth_radius)
    print('P2P 0: near_range   =', near_range)
    print('P2P 0: fd1          =', fd1)
    print('P2P 0: region_cut   =', region_cut)
    print('P2P 0: topo_phase   =', topo_phase)
    print('P2P 0: topo_interp_mode =', topo_interp_mode)
    print('P2P 0: shift_topo   =', shift_topo)
    print('P2P 0: switch_master=', switch_master)
    print('P2P 0: filter_wavelength =', filter_wavelength)
    print('P2P 0: dec_factor   =', dec_factor)
    print('P2P 0: compute_phase_gradient =', compute_phase_gradient)
    print('P2P 0: correct_iono =', correct_iono)
    print('P2P 0: iono_filt_rng=', iono_filt_rng)
    print('P2P 0: iono_filt_azi=', iono_filt_azi)
    print('P2P 0: iono_dsamp   =', iono_dsamp)
    print('P2P 0: iono_skip_est=', iono_skip_est)
    print('P2P 0: threshold_snaphu=', threshold_snaphu)
    print('P2P 0: near_interp  =', near_interp)
    print('P2P 0: mask_water   =', mask_water)
    print('P2P 0: defomax      =', defomax)
    print('P2P 0: threshold_geocode', threshold_geocode)

    stage = proc_stage
    s_stage = skip_stage

    print('P2P 0: loading skip_stage flags skip_i (i=1-6) from config.py ... ...')
    print('P2P 0: for example, skip_1 = 1(0) for skipping(processing) this stage ... ...')
    print('P2P 0: skip_1 = ', skip_1)
    print('P2P 0: skip_2 = ', skip_2)
    print('P2P 0: skip_3 = ', skip_3)
    print('P2P 0: skip_4 = ', skip_4)
    print('P2P 0: skip_5 = ', skip_5)
    print('P2P 0: skip_6 = ', skip_6)

    if s_stage != -999:

        print('P2P 0: skipping stages are ', s_stage, ' ... ...')

    if skip_master == 2:
        skip_4 = 1
        skip_5 = 1
        skip_6 = 1
        print('P2P 0: skipping stages 4, 5, and 6 as skip_master is set to 2 ...')

    filt = filter_wavelength
    iono = correct_iono
    dec = dec_factor
    master = sys.argv[2]
    aligned = sys.argv[3]

    print('P2P 0: non-conventional configuration parameters are loaded ... ...')
    print('P2P 0: spec_div    =', spec_div)
    print('P2P 0: spec_mode   =', spec_mode)
    print('P2P 0: switch_land =', switch_land)
    print('P2P 0: range_dec   =', range_dec)
    print('P2P 0: azimuth_dec =', azimuth_dec)
    print('P2P 0: SLC_factor  =', SLC_factor)
    print('P2P 0: Finished loading configuration parameters.')

    print('P2P 0: combining preprocess paramters to cmdAppendix.')
    cmdAppendix = ' '
    if earth_radius != -999:
        cmdAppendix += ' -radius ' + str(earth_radius)
    if num_patches != -999:
        cmdAppendix += ' -npatch ' + str(num_patches)
    if SLC_factor != -999:
        cmdAppendix += ' -SLC_factor ' + str(SLC_factor)
    if spec_div != 0:
        cmdAppendix += ' -ESD ' + str(spec_mode)
    if skip_master != -999:
        cmdAppendix += ' -skip_master ' + str(skip_master)
    print('P2P 0: commadline appendix is ', cmdAppendix)

    if SAT == 'S1_TOPS':
        print('P2O 0: Modify threshold_geocode=0, threshold_snaphu=0, iono_skip_est=1')
        threshold_geocode = 0
        threshold_snaphu = 0
        iono_skip_est = 1

    if stage == 1 and skip_1 == 0:
        P2P1Preprocess(SAT, master, aligned, skip_master, cmdAppendix)
    if debug == 1:
        input('Press Enter to continue to Phase 2...')

    if (stage <= 2 and skip_2 == 0):
        print('P2P 2: start from focus and align SLC images')
        run('mkdir -p SLC')  # FIXME: use os

        if iono == 1:
            print('P2P 2: creating SLC_L and SLC_H for iono==1')
            run('mkdir -p SLC_L SLC_H')  # FIXME: use os
        if SAT == 'S1_TOPS':
            master, aligned = renameMasterAlignedForS1tops(master, aligned)
        print('master, aligned should be modified for SAT==S1_TOPS', master, aligned)
        P2P2Clean(master, aligned, skip_master, iono)
        os.chdir('SLC')
        P2P2FocusAlign(SAT, master, aligned, skip_master, iono)
        if region_cut != -999:
            P2P2RegionCut(master, aligned, skip_master, iono, config)
        os.chdir('..')
        print('P2P 2: ALIGN.CSH - END')
    if debug == 1:
        input('Press Enter to continue to Phase 3...')

    if stage <= 3 and skip_3 == 0:
        P2P3MakeTopo(master, topo_phase, topo_interp_mode, shift_topo)
    if debug == 1:
        input('Press Enter to continue to Phase 4...')

    ref, rep = switchMasterAligned(switch_master, master, aligned)

    if stage <= 4 and skip_4 == 0:
        P2P4MakeFilterInterferograms(ref, rep, topo_phase, shift_topo, range_dec, azimuth_dec,
                                     dec, filt, compute_phase_gradient, iono, iono_dsamp, config)
    if debug == 1:
        input('Press Enter to continue to Phase 5...')

    if stage <= 5 and skip_5 == 0:
        P2P5Unwrap(ref, rep, threshold_snaphu,
                   mask_water, switch_land, near_interp, config)
    if debug == 1:
        input('Press Enter to continue to Phase 6...')

    if stage <= 6 and skip_6 == 0:
        P2P6Geocode(ref, rep, threshold_geocode, topo_phase)
    print('P2P 7: p2p_processing FINISHED')


def _main_func(description):
    debug = 0
    p2p_processing(debug=debug)

if __name__ == '__main__':
    _main_func(__doc__)
