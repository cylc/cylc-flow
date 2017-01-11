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

import os
import sys

from parsec import ParsecError
from parsec.validate import validator as vdr
from parsec.config import config

"""gscan config file format."""

USER_FILE = os.path.join(os.environ['HOME'], '.cylc', 'gscan.rc')

SPEC = {
    'columns': vdr(vtype='string_list', default=['suite', 'status']),
    'activate on startup': vdr(vtype='boolean', default=False)
}


class gscanconfig(config):

    def check(self):
        cfg = self.get(sparse=True)
        if 'columns' in cfg:
            for column in cfg['columns']:
                if column not in ['host', 'suite', 'title', 'updated',
                                  'status']:
                    print >> sys.stderr, ("WARNING: illegal column name "
                                          "'" + column + "'")
                    cfg['columns'].remove(column)
            if len(cfg['columns']) < 1:
                print >> sys.stderr, ('WARNING: at least one column must be '
                                      'specified, defaulting to "suite, '
                                      'status"')
                cfg['columns'] = ['suite', 'status']


gsfg = None
if not gsfg:
    gsfg = gscanconfig(SPEC)
    if os.access(USER_FILE, os.F_OK | os.R_OK):
        try:
            gsfg.loadcfg(USER_FILE, 'user config')
        except ParsecError as exc:
            sys.stderr.write('ERROR: bad gscan config %s:\n' % USER_FILE)
            raise
    gsfg.check()
