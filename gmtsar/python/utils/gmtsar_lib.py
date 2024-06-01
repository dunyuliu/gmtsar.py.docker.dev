#! /usr/bin/env python3
"""
gmtsar_lib.py is part of pyGMTSAR. 
It hosts commonly used functions similar to CSH.
Dunyu Liu, 20230202. Martin Hawks, 20240518

check_file_report
grep_value
replace_strings
file_shuttle
"""

import os
import re
import subprocess
import shutil
from make_config import write_commented_config, read_config

def init_config():
    """
    Initialize the config file.
    """
    if not os.path.exists('config.yaml'):
        write_commented_config('config.yaml')
        print('config.yaml is generated')
    config = read_config('config.yaml')
    return config

def check_file_report(fn):
    """
    Check if a file exists.
    If not, print error message.
    """
    exist = True
    if os.path.isfile(fn) is False:
        exist = False
        print(" no file " + fn)
        # sys.exit()
    return exist


def catch_output_cmd(cmd_list, choose_split=False, split_id=-999, digit_id=-100000):
    """
    catch_output_cmd takes in cmd_list and return the string
    """
    tmp = subprocess.os.system(
        cmd_list, stdout=subprocess.PIPE).stdout.decode('utf-8').strip()

    if choose_split is True:  # if choose_split:

        if split_id == -999:
            out = tmp.split()  # return a list
        else:
            out = tmp.split()[split_id-1]  # return a value

            if digit_id != -100000:
                out = tmp.split()[split_id-1][digit_id-1]
    else:
        out = tmp
        # If choose_split==False, default return is a string.
    return out


def intFloatOrString(val):
    """
    intFloatOrString will convert a string to an integer or float if possible.
    Otherwise, it will return the string.
    """
    try:
        return float(val)
    except ValueError:
        return ''


def grep_value(fn, s, i):
    """
    grep_value performs similar functions to unix grep.
    Given a file name - fn, and a character string - s, find the ith value.
    The character should be unique in file fn.
    """
    with open(fn, 'r') as f:
        for line in f.readlines():
            if re.search(s, line):
                print(line)
                val = line.split()[i-1]
    return intFloatOrString(val)


def replace_strings(fn, s0, s1):  # FIXME: I think re.sub does this already. Is there a reason it is not in use?
    """
    replace_strings will replace str s0 in file fn,
    with the string s1, and update fn.
    """
    with open(f"{fn}") as f:
        lines = f.readlines()
        txt = f.read()
    fixed = re.sub(s0, s1, txt)
    with open(fn, 'w') as f:
        f.write(fixed)

    updated_lines = []
    for line in lines:
        if s0 in line:
            line = f"{s1}\n"
        updated_lines.append(line)

    with open(f"{fn}", "w") as f:
        f.writelines(updated_lines)


def append_new_line(fn, s0):
    """
    append the string s0 as a new line at the end of file named fn.
    """
    with open(fn, "a+") as f:
        f.seek(0)
        data = f.read(100)
        if len(data) > 0:
            f.write("\n")
        f.write(s0)


def file_shuttle(fn0, fn1, opt):
    """
    copy/move fn0 and paste it to fn1.
    """
    if opt == "cp":
        print("cp " + fn0 + " " + fn1)
        os.system("cp " + fn0 + " " + fn1)
    elif opt == "mv":
        print("mv " + fn0 + " " + fn1)
        os.system("mv " + fn0 + " " + fn1)
    elif opt == "link":
        print("ln -sf " + fn0 + " " + fn1)
        os.system("ln -sf " + fn0 + " " + fn1)


def delete(fn):  # FIXME: Identify what file types this is being called on and use more specific rm functions
    """
    delete file named fn. Currently supports only directory trees,
    find usages and fix to be filetype specific
    """
    shutil.rmtree(fn)

def assign_arg(arg: list, txt):
    """
    arg is the list that contains arguments from a terminal input.
    the function will search for string specified in 'str', and
    return the value next to it in arg.
    """
    if txt in arg:
        val = arg[arg.index(txt)+1]
        return intFloatOrString(val)
    return 0

def run(cmd):
    """
    os.system and print the command specified in cmd.
    """
    print(" ")
    print(cmd)
    os.system(cmd)

def renameMasterAlignedForS1tops(master0, aligned0):
    """
    Rename master and aligned for SAT==S1_TOPS
    """
    print('Renaming master and aligned for SAT==S1_TOPS')
    master = 'S1_'+master0[15:15+8]+'_'+master0[24:24+6]+'_F'+master0[6:7]
    aligned = 'S1_'+aligned0[15:15+8]+'_'+aligned0[24:24+6]+'_F'+aligned0[6:7]
    return master, aligned

# Below are wrappers for some of the gmt and gmtsar c code functions
# TODO: interface these with ctypes or use pygmt when avaliable

def grd2xyz(cmd_str):
    """
    grd2xyz is a wrapper for the gmt grd2xyz command.
    """
    os.system(f"gmt grd2xyz {cmd_str}")

def xyz2grd(cmd_str):
    """
    xyz2grd is a wrapper for the gmt xyz2grd command.
    """
    os.system(f"gmt xyz2grd {cmd_str}")

def gmtconvert(cmd_str):
    """
    gmtconvert is a wrapper for the gmt convert command.
    """
    os.system(f"gmt gmtconvert {cmd_str}")

def gmtsurface(cmd_str):
    """
    gmtsurface is a wrapper for the gmt surface command.
    """
    os.system(f"gmt gmtsurface {cmd_str}")

def grdcut(cmd_str):
    """
    grdcut is a wrapper for the gmt grdcut command.
    """
    os.system(f"gmt grdcut {cmd_str}")

def triangulate(cmd_str):
    """
    triangulate is a wrapper for the gmt triangulate command.
    """
    os.system(f"gmt triangulate {cmd_str}")

def blockmean(cmd_str):
    """
    blockmean is a wrapper for the gmt blockmean command.
    """
    os.system(f"gmt blockmean {cmd_str}")

def surface(cmd_str):
    """
    surface is a wrapper for the gmt surface command.
    """
    os.system(f"gmt surface {cmd_str}")

def grdfill(cmd_str):
    """
    grdfill is a wrapper for the gmt grdfill command.
    """
    os.system(f"gmt grdfill {cmd_str}")

def grdmath(cmd_str):
    """
    grdmath is a wrapper for the gmt grdmath command.
    """
    os.system(f"gmt grdmath {cmd_str}")

def grd2cpt(cmd_str):
    """
    grd2cpt is a wrapper for the gmt grd2cpt command.
    """
    os.system(f"gmt grd2cpt {cmd_str}")

def grdimage(cmd_str):
    """
    grdimage is a wrapper for the gmt grdimage command.
    """
    os.system(f"gmt grdimage {cmd_str}")

def psscale(cmd_str):
    """
    psscale is a wrapper for the gmt psscale command.
    """
    os.system(f"gmt psscale {cmd_str}")

def psconvert(cmd_str):
    """
    psconvert is a wrapper for the gmt psconvert command.
    """
    os.system(f"gmt psconvert {cmd_str}")

def gmtset(cmd_str):
    """
    gmtset is a wrapper for the gmt set command.
    """
    os.system(f"gmt set {cmd_str}")

def make_gaussian_filter(cmd_str):
    """
    make_gaussian_filter is a wrapper for the make_gaussian_filter.c
    file in the gmtsar code. TODO: interface with ctypes
    """
    os.system(f"gmt makecpt {cmd_str}")

def conv(cmd_str):
    """
    conv is a wrapper for the gmtsar conv.c file. TODO: interface with ctypes
    """
    os.system(f"gmt conv {cmd_str}")

def makecpt(cmd_str):
    """
    makecpt is a wrapper for the gmt makecpt command.
    """
    os.system(f"gmt makecpt {cmd_str}")

def grdedit(cmd_str):
    """
    grdedit is a wrapper for the gmt grdedit command.
    """
    os.system(f"gmt grdedit {cmd_str}")

def grdlandmask(cmd_str):
    """
    grdlandmask is a wrapper for the gmt grdlandmask command.
    """
    os.system(f"gmt grdlandmask {cmd_str}")

def split_spectrum(cmd_str):
    """
    split_spectrum is a wrapper for the gmtsar split_spectrum command
    TODO: interface with ctypes
    """
    os.system(f"split_spectrum {cmd_str}")

def SAT_baseline(cmd_str):
    """
    SAT_baseline is a wrapper for the gmtsar SAT_baseline command
    TODO: interface with ctypes
    """
    os.system(f"SAT_baseline {cmd_str}")

def xcorr(cmd_str):
    """
    xcorr is a wrapper for the gmtsar xcorr command
    TODO: interface with ctypes
    """
    os.system(f"xcorr {cmd_str}")

def resamp(cmd_str):
    """
    resamp is a wrapper for the gmtsar resamp command
    TODO: interface with ctypes
    """
    os.system(f"resamp {cmd_str}")

def align_tops_csh(cmd_str):
    """
    align_tops_csh is a wrapper for the gmtsar align_tops.csh command
    script, which has yet to be implimented in python.
    """
    os.system(f"align_tops.csh {cmd_str}")

def cut_slc(cmd_str):
    """
    cut_slc is a wrapper for the gmtsar cut_slc command
    TODO: interface with ctypes
    """
    os.system(f"cut_slc {cmd_str}")

def offset_topo(cmd_str):
    """
    offset_topo is a wrapper for the gmtsar offset_topo command
    TODO: interface with ctypes
    """
    os.system(f"offset_topo {cmd_str}")

def estimate_ionosphereic_phase_csh(cmd_str):
    """
    estimate_ionosphereic_phase_csh is a wrapper for the gmtsar
    estimate_ionosphereic_phase.csh command
    script, which has yet to be implimented in python.
    """
    os.system(f"estimate_ionosphereic_phase.csh {cmd_str}")

def snaphu_interp_csh(cmd_str):
    """
    snaphu_interp_csh is a wrapper for the gmtsar snaphu_interp.csh command
    script, which has yet to be implimented in python.
    """
    os.system(f"snaphu_interp.csh {cmd_str}")

def merge_unwrap_geocode_tops_csh(cmd_str):
    """
    merge_unwrap_geocode_tops_csh is a wrapper for the csh script 
    of the same name. This script has yet to be implimented in python
    """
    os.system(f"merge_unwrap_geocode_top.csh {cmd_str}")

def ALOS_pre_process(cmd_str):
    """
    wrapper for the ALOS_pre_process.c code implimented in gmtsar;
    TODO: interface with ctypes   
    """
    os.system(f'ALOS_pre_process {cmd_str}')

def make_raw_csk(cmd_str):
    """
    Wrapper for the make_raw_csk.c program implimented in gmtdar;
    TODO: interface with ctypes
    """
    os.system(f'make_raw_csk {cmd_str}')

def calc_dop_orb(cmd_str):
    """
    Wrapper for the calc_dop_orb.c program implimented in gmtsar;
    TODO: interface with ctypes
    """
    os.system(f'calc_dop_orb {cmd_str}')

def ERS_pre_process(cmd_str):
    """
    Wrapper for the ERS_pre_process csh script, which has yet to be implimented
    in python
    """
    os.system(f'ERS_pre_process {cmd_str}')

def update_prm(cmd_str):
    """
    Wrapper for the update_prm.c code implimented in gmtsar.
    NOTE: this function is has a very similar name to the updatePrm function.
    One of these names should be changed
    TODO: interface with ctypes
    """
    os.system(f'update_PRM {cmd_str}')

def ENVI_pre_process(cmd_str):
    """
    Wrapper for the ENVI_pre_process csh code which has yet to be implimented in python
    """
    os.system(f'ENVI_pre_process {cmd_str}')

def grdsample(cmd_str):
    """
    Wrapper for the gmt grdsample command
    """
    os.system(f'gmt grdsample {cmd_str}')

def phasefilt(cmd_str):
    """
    Wrapper for the gmtsar phasefilt c code.
    TODO: impliment with ctypes
    """
    os.system(f'phasefilt {cmd_str}')

def grdgradient(cmd_str):
    """
    wrapper function for gmt grdgradient function
    """
    os.system(f'gmt grdgradient {cmd_str}')

def grdinfo(cmd_str):
    """
    wrapper function for gmt grdinfo function
    """
    os.system(f'gmt grdinfo {cmd_str}')

def slc2amp_csh(cmd_str):
    """
    Wrapper for the slc2amp.csh script in gmtsar
    """
    os.system(f'slc2amp.csh {cmd_str}')

def ALOS_pre_process_SLC(cmd_str):
    """
    Wrapper for the ALOS_pre_process_SLC.c code in gmtsar
    """
    os.system(f'ALOS_pre_process_SLC {cmd_str}')

def make_slc_csk(cmd_str):
    """
    Wrapper for the make_slc_csk.c code in gmtsar
    """
    os.system(f'make_slc_csk {cmd_str}')

def make_slc_tsx(cmd_str):
    """
    Wrapper for the make_slc_tsx.c code in gmtsar
    """
    os.system(f'make_slc_tsx {cmd_str}')

def extend_orbit(cmd_str):
    """
    Wrapper for the extend_orbit.c code in gmtsar
    """
    os.system(f'extend_orbit {cmd_str}')

def make_slc_rs2(cmd_str):
    """
    Wrapper for the make_slc_rs2.c code in gmtsar
    """
    os.system(f'make_slc_rs2 {cmd_str}')

def make_slc_gf3(cmd_str):
    """
    Wrapper for the make_slc_gf3.c code in gmtsar
    """
    os.system(f'make_slc_gf3 {cmd_str}')

def make_slc_lt1(cmd_str):
    """
    Wrapper for the make_slc_lt1.c code in gmtsar
    """
    os.system(f'make_slc_lt1 {cmd_str}')

def make_slc_s1a(cmd_str):
    """
    Wrapper for the make_slc_s1a.c code in gmtsar
    """
    os.system(f'make_slc_s1a {cmd_str}')

def ENVI_SLC_pre_process_csh(cmd_str):
    """
    Wrapper for the ENVI_SLC_pre_process.csh script in gmtsar
    """
    os.system(f'ENVI_SLC_pre_process {cmd_str}')

def grdtrack(cmd_str):
    """
    Wrapper for the gmt grdtrack command
    """
    os.system(f'gmt grdtrack {cmd_str}')

def esarp(cmd_str):
    """
    Wrapper for the esarp.c command in gmtsar
    """
    os.system(f'esarp {cmd_str}')

def nearest_grid(cmd_str):
    """
    Wrapper for the nearest_grid.c command in gmtsar
    """
    os.system(f'nearest_grid {cmd_str}')
