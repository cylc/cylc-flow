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

import sys

from cylc.cfgspec.globalcfg import GLOBAL_CFG

def prompt( reason, force=False ):
    if force or GLOBAL_CFG.get( ['disable interactive command prompts'] ):
        return
    response = raw_input( reason + ' (y/n)? ' )
    if response == 'y':
        return
    else:
        sys.exit(0)
