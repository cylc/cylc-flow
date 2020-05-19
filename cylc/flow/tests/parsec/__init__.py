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

import pytest

from cylc.flow.parsec.config import (
    ParsecConfig,
    ConfigNode as Conf
)
from cylc.flow.parsec.validate import (
    CylcConfigValidator as VDR
)


@pytest.fixture
def config(tmp_path):
    """Returns a function for parsing Parsec configurations."""
    def _inner(spec, conf):
        """Parse conf against spec and return the result.

        Arguments:
            spec (cylc.flow.parsec.config.ConfigNode):
                The spec to parse the config against.
            conf (str):
                Multiline string containing the configuration.

        Returns:
            cylc.flow.parsec.ParsecConfig
        """
        filepath = tmp_path / 'cfg.rc'
        with open(filepath, 'w+') as filehandle:
            filehandle.write(conf)
        cfg = ParsecConfig(spec)
        cfg.loadcfg(filepath)
        return cfg
    return _inner


@pytest.fixture
def sample_spec():
    """An example cylc.flow.parsec.config.ConfigNode."""
    with Conf('myconf') as myconf:
        with Conf('section1'):
            Conf('value1', VDR.V_STRING, '')
            Conf('value2', VDR.V_STRING, 'what?')
        with Conf('section2'):
            Conf('enabled', VDR.V_BOOLEAN, False)
        with Conf('section3'):
            Conf('title', VDR.V_STRING)
            with Conf('entries'):
                Conf('key', VDR.V_STRING)
                Conf('value', VDR.V_INTEGER_LIST)
    return myconf
