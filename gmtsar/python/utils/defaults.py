"""
This file stores the default values for the configuration file, in both
a string format which includes comments for readability, and a dictionary
format which can be used to write the configuration file in YAML format.

adapted from config files in the orginal GMTSAR code,
based on the version by Dunyu Liu
Martin Hawks 01/06/2024
"""

DEFAULT_COMENTED_CONFIG = """
#
# This is the default configuration file for p2p_processing
#
# all the comments or explanations are marked by '#'
# The parameters in this configuration file is distinguished by their first word so
# user should follow the naming of each parameter.
# the parameter name, ':' sign, parameter value should be separated by space "  ".
# leave the parameter value blank if using default value.
#
# DO NOT DIRECTLY COMMENT PARAMTERS WITH '#' !!!
# THIS WILL DUPLICATE PARAMETERS AND CAUSE TROUBLE !!!
#

processing_stage:
#####################
# processing stage  #
#####################
# 1 - start from preprocess
# 2 - start from align SLC images
# 3 - start from make topo_ra
# 4 - start from make and filter interferograms
# 5 - start from unwrap phase
# 6 - start from geocode
  proc_stage: 1
  skip_stage: -999
  skip_1: 0
  skip_2: 0
  skip_3: 0
  skip_4: 0
  skip_5: 0
  skip_6: 0

# to work on both use 0, on only aligned image use 1 (assuming master image is done)
# to work on only master image use 2
  skip_master: 0

preprocess:
##################################
#   parameters for preprocess    #
#   - pre_proc.csh               #
##################################
# num of patches
  num_patches: -999

  # earth radius
  earth_radius: -999

  # near_range
  near_range: -999

  # Doppler centroid
  fd1: -999




# ---------------------------------- #
#   parameters for ERS processing    #

ERS_processing:

  S1_TOPS:
    spec_div: 0
    spec_mode: 0

  ALOS_SLC:
    SLC_factor: 0.02

  ALOS2:
    SLC_factor: 2.0

  ALOS2_SCAN:
    SLC_factor: 2.0

# ---------------------------------- #
#  end parameters for ERS processing    #



################################################
#   parameters for focus and align SLC images  #
#   - align.csh                                #
################################################
# region to cut in radar coordinates (leave it blank if process the whole image)
# example 300/5900/0/25000
SLC_align:
  region_cut: -999

#
#####################################
#   parameters for make topo_ra     #
#   - dem2topo_ra.csh               #
#####################################
make_topo_ra:
# subtract topo_ra from the phase
#  (1 -- yes; 0 -- no)
  topo_phase: 1
# if above parameter: 1 then one should have put dem.grd in topo/

# interpolation approach, 0 for surface, 1 for triangulation
  topo_interp_mode: 0

# topo_ra shift (1 -- yes; 0 -- no)
# for ALOS_SLC, ALOS, ERS, shift_topo: 1

  ALOS_SLC:
    shift_topo: 1

  ALOS:
    shift_topo: 1

  ERS:
    shift_topo: 1

  ALOS2:
    shift_topo: 0

  ALOS2_SCAN:
    shift_topo: 0

  S1_STRIP:
    shift_topo: 0

  S1_TOPS:
    shift_topo: 0

  CSK_RAW:
    shift_topo: 0

  CSK_SLC:
    shift_topo: 0

  TSX:
    shift_topo: 0

  RS2:
    shift_topo: 0
# END Satellite specific parameters

make_filter_intfs:
####################################################
#   parameters for make and filter interferograms  #
#   - intf.csh                                     #
#   - filter.csh                                   #
####################################################
# switch the master and aligned when doing intf.
# put '1' if assume master as repeat and aligned as reference
# put '0' if assume master as reference and aligned as repeat [Default]
# phase: repeat phase - reference phase
  switch_master: 0
  switch_land: -999


# filters
# look at the filter/ folder to choose other filters
# for tops processing, to force the decimation factor
# recommended range decimation to be 8, azimuth decimation to be 2

  ALOS2_SCAN:
    filter_wavelength: 400
    dec_factor: 4
    range_dec: 4
    azimuth_dec: 8

  RS2:
    filter_wavelength: 100
    dec_factor: 1

  TSX:
    filter_wavelength: 100
    dec_factor: 1

  CSK_RAW:
    filter_wavelength: 200
    dec_factor: 2

  CSK_SLC:
    filter_wavelength: 200
    dec_factor: 2

  S1_TOPS:
    filter_wavelength: 200
    dec_factor: 2
    range_dec: 8
    azimuth_dec: 2

  S1_STRIP:
    filter_wavelength: 200
    dec_factor: 2

  ERS:
    filter_wavelength: 200
    dec_factor: 2

  ENVI:
    filter_wavelength: 200
    dec_factor: 2

  ALOS:
    filter_wavelength: 20
    dec_factor: 2

  ALOS_SLC:
    filter_wavelength: 200
    dec_factor: 2

  ALOS2:
    filter_wavelength: 200
    dec_factor: 2

# decimation of images is controlled by the dec_factor parameter.
# decimation control the size of the amplitude and phase images. It is either 1 or 2.
# Set the decimation to be 1 if you want higher resolution images.
# Set the decimation to be 2 if you want images with smaller file size.
#


#
# compute phase gradient, make decimation to 1 above and filter wavelength small for better quality
#
  compute_phase_gradient: 0
#
# make ionospheric phase corrections using split spectrum method
  correct_iono: 0
  iono_filt_rng: 1.0
  iono_filt_azi: 1.0
  iono_dsamp: 1
#
# set the following parameter to skip ionospheric phase estimation
  iono_skip_est: 1
#
unwrapping:
#####################################
#   parameters for unwrap phase     #
#   - snaphu.csh                    #
#####################################
# correlation threshold for snaphu.csh (0~1)
# set it to be 0 to skip unwrapping.
  threshold_snaphu: 0

# interpolate masked or low coherence pixels with their nearest neighbors, 1 means interpolate,
# others or blank means using original phase, see snaphu.csh and snaphu_interp.csh for details
# this could be very slow in case a large blank area exist
  near_interp: 0

# mask the wet region (Lakes/Oceans) before unwrapping (1 -- yes; else -- no)
  mask_water: 1

#
# Allow phase discontinuity in unrapped phase. This is needed for interferograms having sharp phase jumps.
# defo_max: 0 - used for smooth unwrapped phase such as interseismic deformation
# defo_max: 65 - will allow a phase jump of 65 cycles or 1.82 m of deformation at C-band
#
  defomax: 0

geocode:
#####################################
#   parameters for geocode          #
#   - geocode.csh                   #
#####################################
# correlation threshold for geocode.csh (0< threshold <=1), set 0 to skip
  threshold_geocode: .10

#####################################
#   Other parameters                #
#####################################
misc:
  S1_TOPS:
    det_stitch: 0

  ALOS2_SCAN:
    det_stitch: 0
"""
DEFAULT_CONFIG = {
    'processing_stage': {'proc_stage': 1, 'skip_stage': -999, 'skip_1': 0, 'skip_2': 0,
                         'skip_3': 0, 'skip_4': 0, 'skip_5': 0, 'skip_6': 0, 'skip_master': 0},
    'preprocess': {'num_patches': -999, 'earth_radius': -999, 'near_range': -999, 'fd1': -999},
    'ERS_processing': {'S1_TOPS': {'spec_div': 0, 'spec_mode': 0},
                       'ALOS_SLC': {'SLC_factor': 0.02},
                       'ALOS2': {'SLC_factor': 2.0},
                       'ALOS2_SCAN': {'SLC_factor': 2.0}
                       },
    'SLC_align': {'region_cut': -999},
    'make_topo_ra': {'topo_phase': 1, 'topo_interp_mode': 0,
                     'ALOS_SLC': {'shift_topo': 1},
                     'ALOS': {'shift_topo': 1},
                     'ERS': {'shift_topo': 1},
                     'ALOS2': {'shift_topo': 0},
                     'ALOS2_SCAN': {'shift_topo': 0},
                     'S1_STRIP': {'shift_topo': 0},
                     'S1_TOPS': {'shift_topo': 0},
                     'CSK_RAW': {'shift_topo': 0},
                     'CSK_SLC': {'shift_topo': 0},
                     'TSX': {'shift_topo': 0},
                     'RS2': {'shift_topo': 0}},
    'make_filter_intfs': {'switch_master': 0, 'switch_land': -999,
                          'ALOS2_SCAN': {'filter_wavelength': 400, 'dec_factor': 4, 'range_dec': 4, 'azimuth_dec': 8},
                          'RS2': {'filter_wavelength': 100, 'dec_factor': 1},
                          'TSX': {'filter_wavelength': 100, 'dec_factor': 1},
                          'CSK_RAW': {'filter_wavelength': 200, 'dec_factor': 2},
                          'CSK_SLC': {'filter_wavelength': 200, 'dec_factor': 2},
                          'S1_TOPS': {'filter_wavelength': 200, 'dec_factor': 2, 'range_dec': 8, 'azimuth_dec': 2},
                          'S1_STRIP': {'filter_wavelength': 200, 'dec_factor': 2},
                          'ERS': {'filter_wavelength': 200, 'dec_factor': 2},
                          'ENVI': {'filter_wavelength': 200, 'dec_factor': 2},
                          'ALOS': {'filter_wavelength': 20, 'dec_factor': 2},
                          'ALOS_SLC': {'filter_wavelength': 200, 'dec_factor': 2},
                          'ALOS2': {'filter_wavelength': 200, 'dec_factor': 2},
                          'compute_phase_gradient': 0, 'correct_iono': 0, 'iono_filt_rng': 1.0,
                          'iono_filt_azi': 1.0, 'iono_dsamp': 1, 'iono_skip_est': 1},
    'unwrapping': {'threshold_snaphu': 0, 'near_interp': 0, 'mask_water': 1, 'defomax': 0},
    'geocode': {'threshold_geocode': 0.1},
    'misc': {'S1_TOPS': {'det_stitch': 0}, 'ALOS2_SCAN': {'det_stitch': 0}
    }
}
