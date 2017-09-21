#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
from parsec.config import config
from parsec.validate import coercers, validator as vdr
from cylc.cfgspec.utils import (coerce_interval, DurationFloat)


coercers['interval'] = coerce_interval
USER_FILE = os.path.join(os.environ['HOME'], '.cylc', 'gscan.rc')

SPEC = {
    'activate on startup': vdr(vtype='boolean', default=False),
    'columns': vdr(vtype='string_list', default=['suite', 'status']),
    'full update interval': vdr(vtype='interval', default=DurationFloat(300)),
    'part update interval': vdr(vtype='interval', default=DurationFloat(15)),
    'window size': vdr(vtype='integer_list', default=[300, 200]),
}


class GScanConfig(config):
    """Configuration for "gscan"."""

    COL_GROUP = "Group"
    COL_HOST = "Host"
    COL_OWNER = "Owner"
    COL_SUITE = "Suite"
    COL_TITLE = "Title"
    COL_UPDATED = "Updated"
    COL_STATUS = "Status"
    COLS_DEFAULT = (COL_SUITE.lower(), COL_STATUS.lower())
    COLS = [col.lower() for col in (
        COL_GROUP, COL_HOST, COL_OWNER, COL_SUITE, COL_TITLE, COL_UPDATED,
        COL_STATUS)]

    def check(self):
        """Custom configuration check."""
        cfg = self.get(sparse=True)
        if 'columns' in cfg:
            for column in cfg['columns']:
                if column not in self.COLS:
                    print >> sys.stderr, (
                        "WARNING: illegal column name '%s'" % column)
                    cfg['columns'].remove(column)
            if not cfg['columns']:
                print >> sys.stderr, (
                    'WARNING: at least one column must be specified,' +
                    ' defaulting to "%s, %s"' % self.COLS_DEFAULT)
                cfg['columns'] = list(self.COLS_DEFAULT)


gsfg = None
if not gsfg:
    gsfg = GScanConfig(SPEC)
    if os.access(USER_FILE, os.F_OK | os.R_OK):
        try:
            gsfg.loadcfg(USER_FILE, 'user config')
        except ParsecError as exc:
            sys.stderr.write('ERROR: bad gscan config %s:\n' % USER_FILE)
            raise
    gsfg.check()
