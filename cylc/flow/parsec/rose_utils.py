# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Cylc support for reading and interpreting ``rose-suite.conf`` workflow
configuration files.
"""

import os
import shlex

from pathlib import Path

# from cylc.flow import LOG


def get_rose_vars(dir_=None, opts=None):
    """Load Jinja2 Vars from rose-suite.conf in dir_

    Args:
        dir_(string or Pathlib.path object):
            Search for a ``rose-suite.conf`` file in this location.
        opts:
            Some sort of options object or string - To be used to allow CLI
            specification of optional configuaration.

    Returns:
        A dictionary of sections of rose-suite.conf.
        For each section either a dictionary or None is returned.
        E.g.
            {
                'env': {'MYVAR': 42},
                'empy:suite.rc': None,
                'jinja2:suite.rc': {
                    'myJinja2Var': {'yes': 'it is a dictionary!'}
                },
                'fileinstall': {} # TODO - update this once implemented.
            }

    TODO:
        - Once the CLI for the ``rose suite-run`` replacement command is
          ready plumb in the the equivelent of
          ``rose suite-run --opt-conf-key=""``.
        - Consider allowing ``[jinja2:flow.conf]`` as an alias for
          consistency with cylc.
    """
    config = {
        'env': None,
        'empy:suite.rc': None,
        'jinja2:suite.rc': None,
        'fileinstall': None
    }
    # Return None if dir_ does not exist
    if dir_ is None:
        return config

    # Return None if rose-suite.conf do not exist.
    if isinstance(dir_, str):
        dir_ = Path(dir_)
    top_level_file = dir_ / 'rose-suite.conf'
    if not top_level_file.is_file():
        return config

    from metomi.rose.config_tree import ConfigTreeLoader

    opt_conf_keys = []
    # get optional config key set as environment variable:
    opt_conf_keys_env = os.getenv("ROSE_SUITE_OPT_CONF_KEYS")
    if opt_conf_keys_env:
        opt_conf_keys += shlex.split(opt_conf_keys_env)
    # ... or as command line options
    if 'opt_conf_keys' in dir(opts) and opts.opt_conf_keys:
        opt_conf_keys += opts.opt_conf_keys

    # Optional definitions
    redefinitions = []
    if 'defines' in dir(opts) and opts.defines:
        redefinitions = opts.defines

    # Load the actual config tree
    config_tree = ConfigTreeLoader().load(
        str(dir_),
        'rose-suite.conf',
        opt_keys=opt_conf_keys,
        defines=redefinitions
    )

    # For each of the template language sections...
    for section in ['jinja2:suite.rc', 'empy:suite.rc']:
        if section in config_tree.node.value:
            config[section] = dict(
                [
                    (item[0][1], item[1].value) for
                    item in config_tree.node.value[section].walk()
                ]
            )
    return config
