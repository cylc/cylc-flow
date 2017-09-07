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

"""Package for network interfaces to cylc suite server objects."""

# Dummy passphrase for client access from users without the suite passphrase.
NO_PASSPHRASE = 'the quick brown fox'


# Ordered privilege levels for authenticated users.
PRIV_IDENTITY = 'identity'
PRIV_DESCRIPTION = 'description'
PRIV_STATE_TOTALS = 'state-totals'
PRIV_FULL_READ = 'full-read'
PRIV_SHUTDOWN = 'shutdown'
PRIV_FULL_CONTROL = 'full-control'
PRIVILEGE_LEVELS = [
    PRIV_IDENTITY,
    PRIV_DESCRIPTION,
    PRIV_STATE_TOTALS,
    PRIV_FULL_READ,
    PRIV_SHUTDOWN,  # (Not used yet - for the post-passhprase era.)
    PRIV_FULL_CONTROL,
]
