"""
A new version of pop_config which writes yaml file instead of python file,
allowing code to be more readable and maintainable, and avoiding the need to
import files that may not exist

Martin Hawks 01/06/2024
"""

import yaml
from defaults import DEFAULT_CONFIG, DEFAULT_COMENTED_CONFIG

def write_commented_config(filename):
    with open(filename, 'w') as f:
        f.write(DEFAULT_COMENTED_CONFIG)

def write_config(filename):
    with open(filename, 'w') as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)

def read_config(filename):
    with open(filename, 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    return config
