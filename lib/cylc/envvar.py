#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

""" environment variable utility functions """

import os
import re


class EnvVarError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


def check_varnames(env):
    """ check a bunch of putative environment names for legality,
    returns a list of bad names (empty implies success)."""
    bad = []
    for varname in env:
        if not re.match('^[a-zA-Z_][\w]*$', varname):
            bad.append(varname)
    return bad


def expandvars(item, owner=None):
    if owner:
        homedir = os.path.expanduser('~' + owner)
    else:
        homedir = os.environ['HOME']
    # first replace '$HOME' with actual home dir
    item = item.replace('$HOME', homedir)
    # now expand any other environment variable or tilde-username
    item = os.path.expandvars(os.path.expanduser(item))
    return item
