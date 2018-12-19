#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""gscan config file format."""

import os
import sys

from parsec import ParsecError
from parsec.config import ParsecConfig
from parsec.upgrade import upgrader

from cylc.cfgvalidate import (
    cylc_config_validate, CylcConfigValidator as VDR, DurationFloat)


USER_FILE = os.path.join(os.environ['HOME'], '.cylc', 'gscan.rc')

# Nested dict of spec items.
# Spec value is [value_type, default, allowed_2, allowed_3, ...]
# where:
# - value_type: value type (compulsory).
# - default: the default value (optional).
# - allowed_2, ...: the only other allowed values of this setting (optional).
SPEC = {
    'activate on startup': [VDR.V_BOOLEAN],
    'columns': [VDR.V_STRING_LIST, ['suite', 'status']],
    'suite listing update interval': [VDR.V_INTERVAL, DurationFloat(60)],
    'suite status update interval': [VDR.V_INTERVAL, DurationFloat(15)],
    'window size': [VDR.V_INTEGER_LIST, [300, 200]],
    'hide main menubar': [VDR.V_BOOLEAN, False],
}


class GScanConfig(ParsecConfig):
    """Configuration for "gscan"."""

    COL_GROUP = "Group"
    COL_HOST = "Host"
    COL_OWNER = "Owner"
    COL_SUITE = "Suite"
    COL_TITLE = "Title"
    COL_UPDATED = "Updated"
    COL_STATUS = "Status"
    COL_VERSION = "Version"
    COLS_DEFAULT = (COL_SUITE.lower(), COL_STATUS.lower())
    COLS = [col.lower() for col in (
        COL_GROUP, COL_HOST, COL_OWNER, COL_SUITE, COL_TITLE, COL_UPDATED,
        COL_STATUS, COL_VERSION)]

    _INST = None

    @classmethod
    def get_inst(cls):
        """Return the singleton instance."""
        if cls._INST is None:
            cls._INST = cls(SPEC, validator=cylc_config_validate)
            if os.access(USER_FILE, os.F_OK | os.R_OK):
                try:
                    cls._INST.loadcfg(USER_FILE, upgrader.USER_CONFIG)
                except ParsecError:
                    LOG.error('bad %s %s', upgrader.USER_CONFIG, USER_FILE)
                    raise
            cls._INST.check()
        return cls._INST

    def check(self):
        """Custom configuration check."""
        cfg = self.get(sparse=True)
        if 'columns' in cfg:
            for column in cfg['columns']:
                if column not in self.COLS:
                    sys.stderr.write(
                        "WARNING: illegal column name '%s'\n" % column)
                    cfg['columns'].remove(column)
            if not cfg['columns']:
                sys.stderr.write(
                    'WARNING: at least one column must be specified,' +
                    ' defaulting to "%s, %s"\n' % self.COLS_DEFAULT)
                cfg['columns'] = list(self.COLS_DEFAULT)
