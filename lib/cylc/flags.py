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

"""Some global flags used in cylc"""

# Set pflag = True to stimulate task dependency negotiation whenever a
# task changes state in such a way that others could be affected. The
# flag should only be turned off again after use in scheduler.py, to
# ensure that dependency negotation occurs when required.
pflag = False

# Set iflag = True to simulate an update of the suite state summary
# structure accessed by gcylc and commands.
iflag = False

# verbose mode
verbose = False

# debug mode
debug = False

# TODO - run mode should be a flag

# utc mode
utc = False
