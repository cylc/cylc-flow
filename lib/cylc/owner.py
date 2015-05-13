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

"""In analogy with cylc.hostname.is_remote_host(), determine if a
username is "remote"."""

import os
import pwd
from cylc.suite_host import get_hostname

user = os.environ.get( 'USER', pwd.getpwuid(os.getuid()).pw_name )
user_at_host = "%s@%s" % (user, get_hostname())

def is_remote_user(name):
    """Return True if name is different than the current username.
    Return False if name is None.
    """
    return name and name != user
