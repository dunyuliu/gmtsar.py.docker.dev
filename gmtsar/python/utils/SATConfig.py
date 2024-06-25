"""
Class to read and write configuration files,
and store configuration information.
"""

from pathlib import Path
import yaml
from defaults import DEFAULT_CONFIG, DEFAULT_COMENTED_CONFIG


class SATConfig:
    """
    Stores all information pertaining to the config
    files, and provides methods to read and write them.
    also initilizes the default values when not provided.
    """

    LOCATIONS = {  # The location of each parameter in the config file
        'proc_stage': 'processing_stage', 'skip_stage': 'processing_stage', 'skip_1': 'processing_stage',
        'skip_2': 'processing_stage', 'skip_3': 'processing_stage', 'skip_4': 'processing_stage',
        'skip_5': 'processing_stage', 'skip_6': 'processing_stage', 'skip_master': 'processing_stage',
        'num_patches': 'preprocess', 'earth_radius': 'preprocess', 'near_range': 'preprocess', 'fd1': 'preprocess',
        'spec_div': 'ERS_processing', 'spec_mode': 'ERS_processing', 'SLC_factor': 'ERS_processing',
        'region_cut': 'SLC_align', 'topo_phase': 'make_topo_ra', 'topo_interp_mode': 'make_topo_ra',
        'shift_topo': 'make_topo_ra', 'switch_master': 'make_filter_intfs', 'switch_land': 'make_filter_intfs',
        'filter_wavelength': 'make_filter_intfs', 'dec_factor': 'make_filter_intfs', 'range_dec': 'make_filter_intfs',
        'azimuth_dec': 'make_filter_intfs', 'compute_phase_gradient': 'make_filter_intfs',
        'correct_iono': 'make_filter_intfs', 'iono_filt_rng': 'make_filter_intfs', 'iono_filt_azi': 'make_filter_intfs',
        'iono_dsamp': 'make_filter_intfs', 'iono_skip_est': 'make_filter_intfs', 'threshold_snaphu': 'unwrapping',
        'near_interp': 'unwrapping', 'mask_water': 'unwrapping', 'defomax': 'unwrapping',
        'threshold_geocode': 'geocode'
    }

    SAT_PARAMS = {  # The parameters that are specific to each satellite
        'proc_stage': False, 'skip_stage': False, 'skip_1': False, 'skip_2': False, 'skip_3': False, 'skip_4': False,
        'skip_5': False, 'skip_6': False, 'skip_master': False, 'num_patches': False, 'earth_radius': False,
        'near_range': False, 'fd1': False, 'spec_div': True, 'spec_mode': True, 'SLC_factor': True,
        'region_cut': False, 'topo_phase': False, 'topo_interp_mode': False, 'shift_topo': True,
        'switch_master': False, 'switch_land': False, 'filter_wavelength': True, 'dec_factor': True,
        'range_dec': True, 'azimuth_dec': True, 'compute_phase_gradient': False, 'correct_iono': False,
        'iono_filt_rng': False, 'iono_filt_azi': False, 'iono_dsamp': False, 'iono_skip_est': False,
        'threshold_snaphu': False, 'near_interp': False, 'mask_water': False, 'defomax': False,
        'threshold_geocode': False
    }

    def __init__(self, sat) -> None:
        """
        Initializes the configuration parser.

        Args:
            sat (str): The satellite being used.
        """
        self.sat = sat  # The satellite being used
        self.config = None  # The parsed configuration
        self.default_config = DEFAULT_CONFIG
        self.pyconf = False  # True if the config file is a python file

    @staticmethod
    def write_commented_config(filename) -> None:
        """
        Writes the default commented configuration to the specified file.

        Args:
            filename (str): The name of the file to write the configuration to.

        Returns:
            None
        """
        with open(filename, 'w') as f:
            f.write(DEFAULT_COMENTED_CONFIG)

    @staticmethod
    def write_raw_config(filename: str) -> None:
        """
        Write the default configuration to a YAML file. Does not include comments.
        This is recomended only if you are familiar with the configuration file and
        its structure.

        Args:
            filename (str): The name of the file to write the configuration to.

        Returns:
            None
        """
        with open(filename, 'w') as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)

    def read_config(self, filename: str) -> dict:
        """
        Reads a configuration file and returns the parsed configuration.

        Args:
            filename (str): The path to the configuration file.

        Returns:
            dict: The parsed configuration.
        """
        if not Path(filename).exists():
            print(
                f'Configuration file {filename} not found, creating new configuration file {filename.split(".")[0]}.yaml'
                )
            self.write_commented_config(filename.split('.')[0] + '.yaml')
            filename = filename.split('.')[0] + '.yaml'
        if filename.split('.')[-1] != 'yaml':
            self.pyconf = True
            self.config = self._read_pyconfig(filename)
            return self.config
        with open(filename, 'r') as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
            self.config = self.parse_yaml(config)
        return self.config

    def _read_pyconfig(self, filename: str):
        """
        Reads a python configuration file and returns the parsed configuration.
        WARNING: This method uses the exec function to read the configuration file.
        This can be a security risk if the file is not trusted. Please use yaml files
        whenever possible.

        Args:
            filename (str): The path to the configuration file.

        Returns:
            dict: The parsed configuration.
        """
        print('WARNING: using config.py is depreciated for security reasons. Please use config.yaml instead.')
        with open(filename, 'r') as f:
            exec(f.read())
        local_vars = locals()
        det_stitch = False
        for param, path in SATConfig.LOCATIONS.items():
            if param == 'det_stitch':
                det_stitch = True
            if param not in local_vars:
                if SATConfig.SAT_PARAMS[param]:
                    local_vars.update({param: self.default_config[path][self.sat][param]})
                else:
                    local_vars.update({param: self.default_config[path][param]})
        if self.sat == 'S1_TOPS' or self.sat == 'ALOS2_SCAN':
            if not det_stitch:
                local_vars['det_stitch'] = self.default_config['misc'][self.sat]['det_stitch']
        return local_vars

    def parse_yaml(self, config: dict) -> dict:
        """
        Converts the yaml configuration to a python dictionary,
        where the parameters are mapped directly to their satellite
        specific values.

        Args:
            config (dict): The parsed configuration.

        Returns:
            dict: The parsed configuration with satellite specific values.
        """
        parsed_config = {}
        det_stich = False
        for param, path in SATConfig.LOCATIONS.items():
            if param == 'det_stitch':
                det_stich = True
            if SATConfig.SAT_PARAMS[param]:
                parsed_config[param] = config.get(
                    path, {}).get(
                        self.sat, {}).get(
                            param, self.default_config[path][self.sat].get(param, KeyError(
                                f'Could not find [{path}][{self.sat}][{param}] in config file {config}, or in default config file.'
                                ))
                            )
            else:
                parsed_config[param] = config.get(path, {}).get(param, self.default_config[path][param])
        if self.sat == 'S1_TOPS' or self.sat == 'ALOS2_SCAN':
            if not det_stich:
                parsed_config['det_stitch'] = self.default_config['misc'][self.sat]['det_stitch']
        return parsed_config

    def __getitem__(self, name: str) :
        if name in self.config:
            return self.config[name]
        raise KeyError(f'Parameter {name} not found in configuration file')

    def __setitem__(self, name: str, value) -> None:
        if name in self.config:
            self.config[name] = value
        else:
            raise KeyError(f'Parameter {name} not found in configuration file. Does not support adding new parameters')
