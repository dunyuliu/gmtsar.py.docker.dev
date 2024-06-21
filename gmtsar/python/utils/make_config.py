"""
A new version of pop_config which writes yaml file instead of python file,
allowing code to be more readable and maintainable, and avoiding the need to
import files that may not exist

Martin Hawks 01/06/2024
"""

import yaml
from defaults import DEFAULT_CONFIG, DEFAULT_COMENTED_CONFIG

def write_commented_config(filename):
    """
    Writes the default commented configuration to the specified file.

    Args:
        filename (str): The name of the file to write the configuration to.

    Returns:
        None
    """
    with open(filename, 'w') as f:
        f.write(DEFAULT_COMENTED_CONFIG)

def write_config(filename):
    """
    Write the default configuration to a YAML file.

    Args:
        filename (str): The name of the file to write the configuration to.

    Returns:
        None
    """
    with open(filename, 'w') as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)

def read_config(filename):
    """
    Reads a configuration file and returns the parsed configuration.

    Args:
        filename (str): The path to the configuration file.

    Returns:
        dict: The parsed configuration.

    """
    with open(filename, 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    return config

def default_pyconfig():
    """
    Sets default values for the parameters that are sometimes missing from the normal
    config file.
    """
    dummy_vars = ['spec_div', 'spec_mode', 'switch_land', 'range_dec', 'azimuth_dec', 'SLC_factor', 'shift_topo', 'proc_stage']
    defaults = {
        'spec_div': 0,
        'spec_mode': -999,
        'switch_land': -999, 
        'range_dec': -999,
        'azimuth_dec': -999,
        'SLC_factor': -999,
        'shift_topo': 0,
        'proc_stage': 1
    }
    for i in dummy_vars:
        if i not in globals():
            globals()[i] = defaults[i]
